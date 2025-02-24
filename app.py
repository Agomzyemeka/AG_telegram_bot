from fastapi import FastAPI, HTTPException, Depends, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, validator
import httpx
import os
import json
from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
import re

app = FastAPI()
security = HTTPBearer()

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database model for storing integrations
class Integration(Base):
    __tablename__ = "integrations"
    
    id = Column(Integer, primary_key=True)
    github_repo = Column(String, index=True)
    chat_id = Column(String)
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    api_key = Column(String, unique=True)

Base.metadata.create_all(bind=engine)  # Create tables

# Pydantic model for handling GitHub webhook payload
class GitHubWebhook(BaseModel):
    repository: str
    workflow: str
    status: str
    actor: str
    run_id: str
    run_number: str
    ref: str

    @validator("repository")
    def validate_repository(cls, v):
        if not re.match(r"^[a-zA-Z0-9-_]+/[a-zA-Z0-9-_]+$", v):
            raise ValueError("Invalid repository format. Expected format: username/repository_name")
        return v

# Telegram bot class to send messages
class TelegramBot:
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

    async def send_message(self, chat_id: str, message: str):
        async with httpx.AsyncClient() as client:
            response = await client.post(self.api_url, json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            })
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail="Failed to send Telegram message")

bot = TelegramBot()

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Store user states and temporary data for Telegram onboarding
USER_STATES = {}
USER_DATA = {}

@app.post("/telegram_webhook")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    """Handles incoming Telegram messages and guides user setup"""
    data = await request.json()

    if "message" not in data:
        return {"status": "ignored"}

    chat_id = str(data["message"]["chat"]["id"])
    text = data["message"].get("text", "").strip()

    if chat_id not in USER_STATES:
        USER_STATES[chat_id] = "start"
        USER_DATA[chat_id] = {"chat_id": chat_id}

    state = USER_STATES[chat_id]

    if text == "/start":
        USER_STATES[chat_id] = "waiting_for_repo"
        return await bot.send_message(chat_id, "Welcome to *AG Telegram Bot*!\n\nEnter your GitHub repository in the format: `username/repository_name`.\n\nExample: `agomzy/awesome-project`")

    elif state == "waiting_for_repo":
        if not re.match(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$", text):
            return await bot.send_message(chat_id, "❌ Invalid format! Enter your repository as `username/repository_name`.\nExample: `agomzy/awesome-project`")
        if not await github_repo_exists(text):
            return await bot.send_message(chat_id, "❌ Repository not found! Check the repository name and try again.")
        USER_DATA[chat_id]["github_repo"] = text
        USER_STATES[chat_id] = "waiting_for_api_key"
        return await bot.send_message(chat_id, "Great! Now, enter your API Key or type 'none' to generate one.")

    elif state == "waiting_for_api_key":
        if text.lower() == "none":
            api_key = os.urandom(16).hex()
            USER_DATA[chat_id]["api_key"] = api_key
            message = (
                f"🔗 *GitHub Integration Setup Complete*\n\n"
                f"Your GitHub repository `{USER_DATA[chat_id]['github_repo']}` has been connected to this chat.\n"
                f"You will receive notifications for workflow runs here.\n\n"
                f"Your API Key: `{api_key}`\n"
                f"Add this key to your GitHub repository secrets as `API_TOKEN` in *Settings > Secrets and variables > Actions*"
            )
            await bot.send_message(chat_id, message)
        else:
            USER_DATA[chat_id]["api_key"] = text

        USER_STATES[chat_id] = "done"

        # Save integration to database
        new_integration = Integration(
            github_repo=USER_DATA[chat_id]["github_repo"],
            chat_id=chat_id,
            api_key=USER_DATA[chat_id]["api_key"]
        )
        db.add(new_integration)
        db.commit()

        del USER_STATES[chat_id]
        del USER_DATA[chat_id]

        return await bot.send_message(chat_id, "✅ Integration complete! You will now receive GitHub notifications here.")

    return {"status": "ok"}

@app.post("/notifications/github")
async def handle_github_webhook(
    webhook: GitHubWebhook,
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db)
):
    """Handles GitHub webhook notifications"""
    integration = db.query(Integration).filter_by(api_key=credentials.credentials).first()
    if not integration:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if integration.github_repo != webhook.repository:
        raise HTTPException(status_code=403, detail="Repository mismatch")

    message = (
        f"🔔 *GitHub Workflow Update*\n\n"
        f"*Repository:* `{webhook.repository}`\n"
        f"*Workflow:* `{webhook.workflow}`\n"
        f"*Status:* `{webhook.status}`\n"
        f"*Triggered by:* `{webhook.actor}`\n"
        f"*Run:* #{webhook.run_number}\n"
        f"*Branch:* `{webhook.ref}`\n\n"
        f"[View Run](https://github.com/{webhook.repository}/actions/runs/{webhook.run_id})"
    )

    await bot.send_message(integration.chat_id, message)

    return {"status": "success", "message": "Notification sent"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)

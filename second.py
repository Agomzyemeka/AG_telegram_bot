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
import logging

#I am testing bot notification
#I am testing bot notification
#I am testing bot notification

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize FastAPI app and security
app = FastAPI()
security = HTTPBearer()

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# Fix PostgreSQL URL format for SQLAlchemy 2.0
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database model for storing integrations
class Integration(Base):
    __tablename__ = "integrations"
    
    id = Column(Integer, primary_key=True, index=True)
    github_repo = Column(String, index=True)
    chat_id = Column(String)
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    api_key = Column(String, unique=True)

# Create database tables
Base.metadata.create_all(bind=engine)

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
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")

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
                logging.error(f"Failed to send message to {chat_id}. Response: {response.text}")
                raise HTTPException(status_code=500, detail="Failed to send Telegram message")

bot = TelegramBot()

async def github_repo_exists(repo_name: str) -> bool:
    """Checks if the given GitHub repository exists with authentication"""
    github_api_url = f"https://api.github.com/repos/{repo_name}"
    github_token = os.getenv("GITHUB_TOKEN")  # Store token in environment variable
    
    logging.info(f"GITHUB_TOKEN is set: {bool(github_token)}")  # ✅ Add this line

    headers = {}
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    async with httpx.AsyncClient() as client:
        response = await client.get(github_api_url, headers=headers)

    logging.info(f"Checked GitHub repo: {repo_name}, Status: {response.status_code}")
    
    return response.status_code == 200


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

    logging.info(f"Received message: {text} from chat_id: {chat_id} (State: {state})")

    if text == "/start":
        USER_STATES[chat_id] = "waiting_for_repo"
        return await bot.send_message(chat_id, "Welcome to *AG Telegram Bot*!\n\nEnter your GitHub repository in the format: `username/repository_name`.\n\nExample: `agomzy/awesome-project`")

    elif state == "waiting_for_repo":
        repo_name = text  # Extract user input
        if not re.match(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$", repo_name):
            return await bot.send_message(chat_id, "❌ Invalid format! Enter your repository as `username/repository_name`.\nExample: `agomzy/awesome-project`")
            
        if not await github_repo_exists(repo_name):
            return await bot.send_message(chat_id, "❌ Repository not found! Check the repository name and try again.")
            
        USER_DATA[chat_id]["github_repo"] = repo_name
        USER_STATES[chat_id] = "waiting_for_api_key"
        return await bot.send_message(chat_id, "Great! Now, enter your API Key or type 'none' to generate one.")

    elif state == "waiting_for_api_key":
        if text.lower() == "none":
            api_key = os.urandom(16).hex()
            USER_DATA[chat_id]["api_key"] = api_key
        else:
            USER_DATA[chat_id]["api_key"] = text

        # Save integration to the database
        new_integration = Integration(
            github_repo=USER_DATA[chat_id]["github_repo"],
            chat_id=chat_id,
            api_key=USER_DATA[chat_id]["api_key"]
        )
        db.add(new_integration)
        db.commit()

        # Send confirmation message
        message = (
            f"✅ *GitHub Integration Complete!*\n\n"
            f"Your repository `{USER_DATA[chat_id]['github_repo']}` is now connected.\n"
            f"*API Key:* `{USER_DATA[chat_id]['api_key']}`\n\n"
            f"🔹 *How to Add API Key to GitHub Secrets:*\n"
            f"1. Go to your repository on GitHub.\n"
            f"2. Navigate to *Settings* > *Secrets and variables* > *Actions*.\n"
            f"3. Click *New repository secret*.\n"
            f"4. Name it `API_TOKEN` and paste the API Key above.\n"
            f"5. Save and you're done!"
        )
        await bot.send_message(chat_id, message)

        # Cleanup user data
        del USER_STATES[chat_id]
        del USER_DATA[chat_id]

        return await bot.send_message(chat_id, "✅ Integration complete! You will now receive GitHub notifications here.")

    return {"status": "ok"}

@app.post("/notifications/github")
async def handle_github_webhook(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(security),  # Allow None (for ping)
    db: Session = Depends(get_db)
):
    """Handles GitHub webhook notifications"""

    # ✅ Extract event type from headers
    event_type = request.headers.get("X-GitHub-Event", "").lower()

    # ✅ Get the JSON payload
    try:
        data = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # ✅ Allow "ping" event through WITHOUT authentication
    if event_type == "ping":
        return {"status": "ok", "message": "Ping received successfully"}

    # ✅ Enforce authentication for all other events
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # ✅ Validate API key
    integration = db.query(Integration).filter_by(api_key=credentials.credentials).first()
    if not integration:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # ✅ Parse webhook payload into Pydantic model
    try:
        webhook = GitHubWebhook(**data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid payload: {str(e)}")

    # ✅ Validate repository match
    if integration.github_repo != webhook.repository:
        raise HTTPException(status_code=403, detail="Repository mismatch")

    # ✅ Format message for Telegram
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
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))

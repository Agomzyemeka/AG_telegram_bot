from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import httpx
import os
from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime

# Hello
app = FastAPI()
security = HTTPBearer()

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Integration(Base):
    __tablename__ = "integrations"
    
    id = Column(Integer, primary_key=True)
    github_repo = Column(String, index=True)
    chat_id = Column(String)
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    api_key = Column(String, unique=True)

Base.metadata.create_all(bind=engine)  # Create tables

class GitHubWebhook(BaseModel):
    repository: str
    workflow: str
    status: str
    actor: str
    run_id: str
    run_number: str
    ref: str

class IntegrationRequest(BaseModel):
    github_repo: str
    chat_id: str

class TelegramBot:
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        
    async def send_message(self, chat_id: str, message: str):
        async with httpx.AsyncClient() as client:
            telegram_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            params = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            
            response = await client.post(telegram_url, json=params)
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail="Failed to send Telegram message")

bot = TelegramBot()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/setup")
async def setup_integration(
    request: IntegrationRequest,
    db: Session = Depends(get_db)
):
    """Setup a new integration for a GitHub repository with Telegram"""
    # Generate unique API key
    api_key = os.urandom(16).hex()
    
    # Create new integration
    integration = Integration(
        github_repo=request.github_repo,
        telegram_chat_id=request.chat_id,
        api_key=api_key
    )
    
    db.add(integration)
    db.commit()
    
    # Send test message to Telegram
    welcome_message = (
        f"🔗 *GitHub Integration Setup Complete*\n\n"
        f"Your GitHub repository `{request.github_repo}` has been connected to this chat.\n"
        f"You will receive notifications for workflow runs here.\n\n"
        f"Your API Key: `{api_key}`\n"
        f"Add this key to your GitHub repository secrets as `API_TOKEN`"
    )
    
    await bot.send_message(request.chat_id, welcome_message)
    
    return {
        "status": "success",
        "api_key": api_key,
        "message": "Integration setup complete. Add the API key to your GitHub repository secrets."
    }

@app.post("/notifications/github")
async def handle_github_webhook(
    webhook: GitHubWebhook,
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db)
):
    # Find integration by API key
    integration = db.query(Integration).filter_by(api_key=credentials.credentials).first()
    if not integration:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Verify repository matches
    if integration.github_repo != webhook.repository:
        raise HTTPException(status_code=403, detail="Repository mismatch")
    
    # Format message
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
    
    # Send to Telegram
    await bot.send_message(integration.chat_id, message)
    
    return {"status": "success", "message": "Notification sent"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
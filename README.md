# AG Telegram Bot - GitHub Actions Notifier  

AG Telegram Bot (`agomzy_telegram_bot`) is a FastAPI-based application that integrates GitHub Actions/Events with Telegram, allowing users to receive real-time notifications from their connected repositories.  

The bot can be added to developer group chats to give real time updates/notifications to members of the team. 

## Features  
✅ Receive GitHub Event notifications on Telegram.  
✅ Secure authentication using API keys.  
✅ Validate GitHub repository format and existence.  
✅ Easy setup with `/start or Hi or Hello`command.  
✅ Stores integration details in a database.  

---

## 🚀 Getting Started  

### 1️⃣ Clone the Repository  
```sh
git clone https://github.com/yourusername/your-repo.git
cd your-repo
```

### 2️⃣ Set Up the Environment  
Create a `.env` file and add the following environment variables:  

```env
DATABASE_URL=your_database_url
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
GITHUB_TOKEN=your_github_token
PORT=8000
```

### 3️⃣ Install Dependencies  
```sh
pip install -r requirements.txt
```

### 4️⃣ Run the Application  
```sh
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## 🔧 API Endpoints  

### 📌 Telegram Webhook  
**Endpoint:** `/telegram_webhook`  
- Handles user interactions for setting up GitHub repository notifications.  
- Users enter their repository in the format: `username/repository_name`.  
- API key validation is required for secure integration.  

### 📌 GitHub Notifications Webhook  
**Endpoint:** `/notifications/github`  
- Receives workflow event notifications from GitHub.  
- Sends formatted messages to the corresponding Telegram chat.  

---

## 🛠️ Setting Up GitHub Webhook  

1. Go to your GitHub repository settings.  
2.  Navigate to **Webhooks** and add:  
   - **Payload URL:** `https://your-server-url.com/notifications/github`  
   - **Content Type:** `application/json`  
   - **Secret:** Your API token  

---

## 📝 Example Usage  

1️⃣ Start the bot in Telegram by sending:  
```
"/start" or "Hi" or "Hello"
```
2️⃣ Enter your GitHub repository name in the format:  
```
agomzy/awesome-project
```
3️⃣ If the repository exists, you'll be prompted to enter an API key or generate one.  
4️⃣ Once setup is complete, you'll receive GitHub event notifications in your Telegram chat.  

---

## 📌 Technologies Used  
- **FastAPI** for backend logic.  
- **SQLAlchemy** for database management.  
- **HTTPX** for async HTTP requests.  
- **Telegram Bot API** for notifications.  
- **GitHub Webhooks** for repository event tracking.  

---

## 🔐 Security Measures  
- **API Key Authentication** ensures only authorized users receive notifications.  
- **Input Validation** prevents incorrect repository formats and invalid data.  
- **Database Encryption (optional)** can be added for securing sensitive data.  

---

## 🤝 Contributing  
Want to improve this project? Follow these steps:  
1. Fork the repository.  
2. Create a feature branch (`git checkout -b feature-branch`).  
3. Commit changes (`git commit -m "Added new feature"`).  
4. Push to GitHub (`git push origin feature-branch`).  
5. Submit a pull request.  

---

## 📩 Contact  
For any issues or feature requests, feel free to reach out:  
📧 Email: [your-email@example.com](mailto:emyagomoh54321@gmail.com)  
💬 Telegram: [AG Telegram Bot](https://t.me/agomzy_telegram_bot)  

---

### 📜 License  
This project is open-source and available under the [MIT License](LICENSE).

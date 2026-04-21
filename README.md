# Omni Copilot 🤖

A production-ready unified AI assistant that connects to Google Drive, Docs, Gmail, Calendar, Slack, Notion, and Zoom via natural language.

## Features
- **Multi-step Agent**: Powered by LangGraph to dynamically build plans and call multiple tools sequentially.
- **Cross-App Queries**: Example: "Summarize today's Slack messages and email them to my manager."
- **Sensitive Action Confirmations**: Requires human-in-the-loop approval before sending emails, messages, or creating events.
- **Real-time Streaming UI**: Next.js frontend rendering SSE state changes from the LangGraph agent in real time.
- **OAuth 2.0 Integrations**: Connect seamlessly to Google, Slack, and Notion from the UI.

---

### 📧 Gmail Intelligence
- **Inbox Insights**: Fetch and summarize your latest emails instantly.
- **Smart Replies**: Generate context-aware replies or drafts with one command.
- **One-Click Sending**: Send emails directly through chat.

### 📂 Google Drive & Docs
- **File Discovery**: List and access your most recent files.
- **Document Summarization**: Summarize selected or recent documents on demand.
- **Content Generation**: Create new Docs from prompts (notes, reports, etc.).

### 📅 Google Calendar
- **Smart Scheduling**: Create events using natural language.
- **Auto Meet Links**: Generate Google Meet links automatically.
- **Daily Overview**: Get a summary of your schedule anytime.

### 💬 Slack Integration
- **Message Retrieval**: Fetch recent messages or conversations.
- **Channel Summaries**: Summarize activity in channels.
- **Send Messages**: Post messages directly from chat.

### 🧠 Notion Integration
- **Page Access**: Read and summarize Notion pages.
- **Content Creation**: Create and update pages via AI.
- **Workspace Awareness**: Pull insights from your shared pages.

### ⏰ Productivity Tools
- **Intelligent Reminders**: Set time-sensitive notifications that trigger real desktop/browser alerts.
- **File Analysis**: Upload documents/images and ask the AI specific questions using OCR and advanced reasoning.

---

## 🛠️ Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend** | Python, FastAPI, LangGraph, LangChain,SQLAlchemy, PostgreSQL |
| **AI Engine** | Groq, Google Gemini, OpenAI (Fallback). |
| **Integrations** | Google Workspace (Mail, Calendar, Drive, Docs), Slack, Notion, Zoom |
| **Task Queue** | APScheduler (Reminders & Cleanup) |
| **Frontend** | React 19, Tailwind CSS 4, Axios |
| **UI Components** | Lucide React, React Markdown |

---

## 🚀 Setup Instructions

### 1. Database Setup
Ensure PostgreSQL is running.
```bash
createdb omni_copilot
psql -d omni_copilot -f database/migrations/001_init.sql
```

### 2. Backend Setup
Create and configure your `.env` file along with all the OAuth credentials.
```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate | Mac/Linux: source venv/bin/activate
pip install -r requirements.txt

# Run the FastAPI server
uvicorn app.main:app --reload
```

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
---

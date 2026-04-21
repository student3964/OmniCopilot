# Omni Copilot 🤖

A production-ready unified AI assistant that connects to Google Drive, Docs, Gmail, Calendar, Slack, Notion, and Zoom via natural language.

## Features
- **Multi-step Agent**: Powered by LangGraph to dynamically build plans and call multiple tools sequentially.
- **Cross-App Queries**: Example: "Summarize today's Slack messages and email them to my manager."
- **Sensitive Action Confirmations**: Requires human-in-the-loop approval before sending emails, messages, or creating events.
- **Real-time Streaming UI**: Next.js frontend rendering SSE state changes from the LangGraph agent in real time.
- **OAuth 2.0 Integrations**: Connect seamlessly to Google, Slack, and Notion from the UI.

---

## 🚀 Setup Instructions

### 1. Database Setup
Ensure PostgreSQL is running.
```bash
createdb omni_copilot
psql -d omni_copilot -f database/migrations/001_init.sql
```

### 2. Backend Setup
Create and configure your `.env` file based on `.env.example`.
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

Visit [http://localhost:3000](http://localhost:3000)

---

## 🔐 OAuth Configuration Guide

### Google (Drive, Docs, Mail, Calendar)
1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create OAuth Client ID (Web Application)
3. Set Authorized Redirect URI: `http://localhost:8000/api/auth/google/callback`

### Slack
1. Go to [Slack API Apps](https://api.slack.com/apps)
2. Create New App → From scratch 
3. Setup OAuth & Permissions
4. Add Scopes (Bot + User): `channels:history`, `chat:write`, `search:read`, etc.
5. Set Redirect URL: `http://localhost:8000/api/auth/slack/callback`

### Notion
1. Go to [Notion Integrations](https://www.notion.so/my-integrations)
2. Create New Integration (Public integration type)
3. Set Redirect URI: `http://localhost:8000/api/auth/notion/callback`

---

## 🧠 Sample Queries to Test

- **Information Retrieval**: "What are the names of the last 3 files added to my Google Drive?"
- **Cross-Platform**: "Find the Slack message where John discussed the marketing plan, and create a Notion page with a summary."
- **Communication (needs confirmation)**: "Draft an email to boss@company.com summarizing my meetings for tomorrow from Google Calendar."
- **Multi-step Execution**: "What did I do in Slack today? Summarize it and send it to me on Slack as a DM."


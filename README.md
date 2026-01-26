# Jira-Confluence Agentic AI System 🤖

A security-first, agentic AI system that integrates with Jira and Confluence (read-only) to provide delivery intelligence and decision support for engineering teams.

## 🌟 Features

- **🔐 Security-First Design**: Read-only access to Jira and Confluence, environment-based configuration, secure API key handling
- **🤖 Agentic AI**: Powered by LangChain and OpenAI, with autonomous decision-making capabilities
- **💬 Conversational Interface**: Simple, intuitive chat UI with conversation history
- **📊 Delivery Intelligence**: Analyze project metrics, sprint progress, and team performance
- **🔍 Smart Search**: Search and analyze Jira issues and Confluence documentation
- **🐳 Docker Ready**: Easy deployment locally or in the cloud via Docker containers
- **💾 Persistent Memory**: Remembers previous conversations for contextual interactions

## 🏗️ Architecture

```
┌─────────────────┐
│   Frontend UI   │ (HTML/CSS/JS)
│  (Chat Interface)│
└────────┬────────┘
         │ REST API
┌────────▼────────┐
│   FastAPI App   │
├─────────────────┤
│  AI Agent       │ (LangChain + OpenAI)
│  ├─ Jira Tool   │
│  ├─ Confluence  │
│  └─ Analytics   │
├─────────────────┤
│  SQLite DB      │ (Conversation History)
└─────────────────┘
         │
    ┌────┴────┐
┌───▼──┐  ┌──▼────┐
│ Jira │  │Conflue│
│(Read)│  │ nce   │
└──────┘  └───────┘
```

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose (recommended)
- OR Python 3.11+ (for local development)
- OpenAI API key
- Jira account with API token
- Confluence account with API token

### Option 1: Docker Deployment (Recommended)

1. **Clone the repository**
   ```bash
   git clone https://github.com/louisphilippebosse/jira-confluence-agentic-rl.git
   cd jira-confluence-agentic-rl
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

3. **Build and run with Docker Compose**
   ```bash
   docker-compose up --build
   ```

4. **Access the application**
   - Open your browser to `http://localhost:8000`
   - Start chatting with your AI assistant!

### Option 2: Local Development

1. **Clone and setup**
   ```bash
   git clone https://github.com/louisphilippebosse/jira-confluence-agentic-rl.git
   cd jira-confluence-agentic-rl
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

5. **Run the application**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

6. **Access the application**
   - Open `http://localhost:8000`

## ⚙️ Configuration

### Required Environment Variables

Create a `.env` file based on `.env.example`:

```env
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Jira Configuration (Read-Only)
JIRA_URL=https://your-domain.atlassian.net
JIRA_USERNAME=your_email@example.com
JIRA_API_TOKEN=your_jira_api_token

# Confluence Configuration (Read-Only)
CONFLUENCE_URL=https://your-domain.atlassian.net/wiki
CONFLUENCE_USERNAME=your_email@example.com
CONFLUENCE_API_TOKEN=your_confluence_api_token

# Application Configuration
DATABASE_URL=sqlite:///./data/conversations.db
SECRET_KEY=your_secret_key_here_change_in_production
ENVIRONMENT=production

# Security Settings
ALLOWED_ORIGINS=http://localhost:8000,http://localhost:3000
MAX_CONVERSATION_HISTORY=50
```

### Getting API Tokens

**Jira & Confluence API Token:**
1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Give it a label and copy the token
4. Use your email as username and the token as password

**OpenAI API Key:**
1. Go to https://platform.openai.com/api-keys
2. Create a new API key
3. Copy and save it securely

## 📖 Usage Examples

### Ask about Project Status
```
"Show me all open issues in project ABC"
"What's the completion rate for project XYZ?"
```

### Analyze Sprint Progress
```
"Analyze delivery metrics for sprint 'Sprint 23'"
"What are the blockers in our current sprint?"
```

### Search Documentation
```
"Search Confluence for API integration guide"
"Find documentation about authentication"
```

### Get Insights
```
"What are the top priority issues assigned to me?"
"Summarize the status of all projects"
```

## 🔐 Security Features

1. **Read-Only Access**: All integrations are read-only by design
2. **Environment Variables**: Sensitive data stored in environment variables
3. **CORS Protection**: Configurable allowed origins
4. **No Data Persistence**: No Jira/Confluence data is stored permanently
5. **API Key Security**: Keys never exposed to frontend
6. **Secure by Default**: Production-ready configuration

## 🏗️ Project Structure

```
jira-confluence-agentic-rl/
├── app/
│   ├── api/              # API endpoints
│   │   └── chat.py       # Chat API
│   ├── models/           # Data models
│   │   ├── database.py   # Database models
│   │   └── schemas.py    # Pydantic schemas
│   ├── services/         # Business logic
│   │   ├── ai_agent_service.py    # AI agent
│   │   ├── jira_service.py        # Jira integration
│   │   └── confluence_service.py  # Confluence integration
│   ├── static/           # Frontend assets
│   │   ├── app.js        # Frontend logic
│   │   └── style.css     # Styles
│   ├── templates/        # HTML templates
│   │   └── index.html    # Main UI
│   ├── config.py         # Configuration
│   └── main.py           # Application entry point
├── data/                 # Database storage
├── Dockerfile            # Docker configuration
├── docker-compose.yml    # Docker Compose config
├── requirements.txt      # Python dependencies
├── .env.example          # Example environment config
└── README.md            # This file
```

## 🛠️ Development

### Running Tests
```bash
# Add tests in tests/ directory
pytest
```

### Code Quality
```bash
# Format code
black app/

# Lint
flake8 app/
```

### Adding New Features

1. **New AI Tools**: Add to `app/services/ai_agent_service.py`
2. **New API Endpoints**: Add to `app/api/`
3. **New Services**: Add to `app/services/`

## 🐳 Docker Deployment

### Build Image
```bash
docker build -t jira-confluence-ai .
```

### Run Container
```bash
docker run -p 8000:8000 --env-file .env jira-confluence-ai
```

### Deploy to Cloud

The Docker image can be deployed to:
- **AWS ECS/Fargate**
- **Google Cloud Run**
- **Azure Container Instances**
- **Any Kubernetes cluster**

Example for Cloud Run:
```bash
gcloud run deploy jira-confluence-ai \
  --image gcr.io/your-project/jira-confluence-ai \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

## 📊 API Documentation

Once running, access interactive API documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Key Endpoints

- `POST /api/chat` - Send a message to the AI
- `GET /api/conversation/{session_id}` - Get conversation history
- `GET /api/sessions` - List all sessions
- `DELETE /api/conversation/{session_id}` - Delete a conversation
- `GET /health` - Health check

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📝 License

MIT License - see LICENSE file for details

## 🆘 Troubleshooting

### Connection Issues
- Verify your Jira/Confluence URLs are correct
- Check API tokens are valid
- Ensure network access to Atlassian services

### OpenAI Errors
- Verify API key is valid
- Check you have sufficient credits
- Ensure API key has proper permissions

### Database Issues
- Ensure `data/` directory exists and is writable
- Check DATABASE_URL is correctly configured

## 📞 Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check existing documentation
- Review logs for error messages

## 🎯 Roadmap

- [ ] Multi-user support with authentication
- [ ] Advanced analytics dashboards
- [ ] Custom report generation
- [ ] Integration with more tools (GitHub, Slack)
- [ ] Voice interface support
- [ ] Mobile app

---

Built with ❤️ using FastAPI, LangChain, and OpenAI
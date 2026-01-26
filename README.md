# Jira-Confluence Agentic AI System 🤖

A security-first, agentic AI system that integrates with Jira and Confluence (read-only) to provide delivery intelligence and decision support for engineering teams. Features **Knowledge Graph RAG** with NetworkX and **local LLM support** via Ollama.

## 🌟 Key Features

- **🔐 Security-First Design**: Read-only access to Jira and Confluence, environment-based configuration, secure API key handling
- **🤖 Agentic AI**: Powered by LangChain with support for OpenAI or Ollama (local)
- **🕸️ Knowledge Graph RAG**: NetworkX-powered graph database for relationship-aware insights
- **🏠 Fully Local Option**: Run completely offline with Ollama (no external API calls)
- **💬 Conversational Interface**: Simple, intuitive chat UI with conversation history
- **📊 Delivery Intelligence**: Analyze project metrics, sprint progress, and team performance
- **🔍 Smart Search**: Search and analyze Jira issues and Confluence documentation
- **⚡ UV Support**: Ultra-fast package installation with UV
- **🐳 Docker Ready**: Easy deployment locally or in the cloud via Docker containers
- **💾 Persistent Memory**: Remembers previous conversations for contextual interactions

## 🆕 What's New

- ✨ **NetworkX Knowledge Graph**: Build relationship networks between issues, users, and documentation
- ✨ **Ollama Integration**: Run AI completely local with Llama 3.2, Mistral, or other models
- ✨ **UV Package Manager**: Install dependencies 20x faster than pip
- ✨ **Knowledge Graph API**: Query relationships, find paths, analyze network structure
- ✨ **Flexible LLM Provider**: Switch between OpenAI and Ollama with a single config change

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
│  AI Agent       │ (LangChain + OpenAI/Ollama)
│  ├─ Jira Tool   │
│  ├─ Confluence  │
│  └─ Analytics   │
├─────────────────┤
│ Knowledge Graph │ (NetworkX)
│  ├─ Entities    │ (Issues, Users, Pages)
│  └─ Relations   │ (assigned_to, documents)
├─────────────────┤
│  SQLite DB      │ (Conversation History)
└─────────────────┘
         │
    ┌────┴────┐
┌───▼──┐  ┌──▼────┐
│ Jira │  │Confluence│
│(Read)│  │  (Read)  │
└──────┘  └───────┘
```

## 🚀 Quick Start

### Prerequisites

**Choose Your Setup:**

**Option A: Fully Local (Recommended for Privacy)**
- Python 3.11+
- UV (optional but recommended)
- Ollama (for local LLM)
- Jira & Confluence access

**Option B: Cloud LLM**
- Python 3.11+
- UV (optional but recommended)  
- OpenAI API key
- Jira & Confluence access

**Option C: Docker**
- Docker and Docker Compose
- OpenAI API key OR Ollama
- Jira & Confluence access

### Option 1: Quick Setup with UV + Ollama (Fastest & Most Private)

```bash
# 1. Install UV (ultra-fast package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install Ollama (local LLM)
# macOS: brew install ollama
# Linux: curl -fsSL https://ollama.ai/install.sh | sh
# Or visit: https://ollama.ai/download

# 3. Start Ollama and pull a model
ollama serve  # In one terminal
ollama pull llama3.2:latest  # In another terminal

# 4. Clone and setup project
git clone https://github.com/louisphilippebosse/jira-confluence-agentic-rl.git
cd jira-confluence-agentic-rl

# 5. Create virtual environment and install dependencies with UV (super fast!)
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r requirements.txt

# 6. Configure environment
cp .env.example .env
# Edit .env - set LLM_PROVIDER=ollama and add your Jira/Confluence credentials

# 7. Run the application
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 8. Open browser to http://localhost:8000
```

**Done! You now have a fully local, private AI assistant!** 🎉

### Option 2: Setup with OpenAI

```bash
# 1. Install UV (optional but recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone and setup
git clone https://github.com/louisphilippebosse/jira-confluence-agentic-rl.git
cd jira-confluence-agentic-rl

# 3. Install dependencies
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

# 4. Configure for OpenAI
cp .env.example .env
# Edit .env - set LLM_PROVIDER=openai and add your OpenAI API key

# 5. Run
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Option 3: Docker Deployment

```bash
# 1. Clone and configure
git clone https://github.com/louisphilippebosse/jira-confluence-agentic-rl.git
cd jira-confluence-agentic-rl
cp .env.example .env
# Edit .env with your credentials

# 2. Build and run
docker-compose up --build

# 3. Access at http://localhost:8000
```

### Option 4: Using Makefile

```bash
# Quick setup with UV
make dev-uv

# Or with pip
make dev

# Run the application
make run
```

## 📖 Detailed Documentation

- **[UV Guide](UV_GUIDE.md)** - Fast package installation with UV
- **[Ollama Guide](OLLAMA_GUIDE.md)** - Local LLM setup and configuration
- **[Knowledge Graph Guide](KNOWLEDGE_GRAPH.md)** - Understanding and using the knowledge graph
- **[Security Policy](SECURITY.md)** - Security best practices
- **[Contributing](CONTRIBUTING.md)** - How to contribute

## ⚙️ Configuration

### Required Environment Variables

Create a `.env` file based on `.env.example`:

```env
# LLM Provider Selection (openai or ollama)
LLM_PROVIDER=ollama

# Ollama Configuration (for local LLM)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:latest

# OpenAI Configuration (only if LLM_PROVIDER=openai)
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

# Knowledge Graph Configuration
ENABLE_KNOWLEDGE_GRAPH=true
KNOWLEDGE_GRAPH_PATH=./data/knowledge_graph.gpickle
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
│   │   ├── chat.py       # Chat API
│   │   └── knowledge_graph.py  # Knowledge Graph API
│   ├── models/           # Data models
│   │   ├── database.py   # Database models
│   │   └── schemas.py    # Pydantic schemas
│   ├── services/         # Business logic
│   │   ├── ai_agent_service.py          # AI agent with RAG
│   │   ├── jira_service.py              # Jira integration
│   │   ├── confluence_service.py        # Confluence integration
│   │   └── knowledge_graph_service.py   # NetworkX graph
│   ├── static/           # Frontend assets
│   │   ├── app.js        # Frontend logic
│   │   └── style.css     # Styles
│   ├── templates/        # HTML templates
│   │   └── index.html    # Main UI
│   ├── config.py         # Configuration
│   └── main.py           # Application entry point
├── data/                 # Database & graph storage
├── Dockerfile            # Docker configuration
├── docker-compose.yml    # Docker Compose config
├── pyproject.toml        # UV/pip configuration
├── requirements.txt      # Python dependencies
├── .env.example          # Example environment config
├── Makefile             # Common commands
├── UV_GUIDE.md          # UV package manager guide
├── OLLAMA_GUIDE.md      # Ollama setup guide
├── KNOWLEDGE_GRAPH.md   # Knowledge graph documentation
├── SECURITY.md          # Security policy
├── CONTRIBUTING.md      # Contributing guidelines
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

#### Chat & Conversation
- `POST /api/chat` - Send a message to the AI
- `GET /api/conversation/{session_id}` - Get conversation history
- `GET /api/sessions` - List all sessions
- `DELETE /api/conversation/{session_id}` - Delete a conversation

#### Knowledge Graph  
- `GET /api/kg/stats` - Get knowledge graph statistics
- `GET /api/kg/entity/{entity_id}` - Get specific entity
- `GET /api/kg/entity/{entity_id}/related` - Get related entities
- `POST /api/kg/search` - Search entities
- `GET /api/kg/central` - Get most central entities (PageRank)
- `GET /api/kg/path/{source_id}/{target_id}` - Find shortest path

#### System
- `GET /health` - Health check
- `GET /` - Web UI

### Example API Usage

```bash
# Check health and configuration
curl http://localhost:8000/health

# Get knowledge graph stats
curl http://localhost:8000/api/kg/stats

# Get entity details
curl http://localhost:8000/api/kg/entity/JIRA-123

# Find relationships
curl http://localhost:8000/api/kg/entity/JIRA-123/related

# Chat with AI
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Show me open issues in project ABC"}'
```

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
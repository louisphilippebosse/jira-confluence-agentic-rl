# Jira-Confluence Agentic AI System ���

> A security-first, agentic AI system that integrates with Jira and Confluence to provide delivery intelligence and decision support for engineering teams.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Development](#development)
- [Security](#security)

## Features

��� **Security-First** - Read-only access, environment-based configuration  
��� **Agentic AI** - LangChain with OpenAI or Ollama (local)  
���️ **Knowledge Graph** - NetworkX-powered RAG with auto-updates  
��� **Fully Local** - Run offline with Ollama  
��� **Conversational** - Intuitive chat UI with history  
��� **Delivery Intelligence** - Project metrics and sprint analysis  

## Quick Start

### Option 1: React Frontend (Recommended)

```bash
# 1. Install Ollama: https://ollama.ai/download
ollama serve && ollama pull llama3.2:latest

# 2. Setup project
git clone <repo> && cd jira-confluence-agentic-rl
python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env - set LLM_PROVIDER=ollama, add Jira/Confluence credentials

# 4. Run Backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 5. Run Frontend (new terminal)
cd frontend && npm install && npm run dev
# Open: http://localhost:3000
```

### Option 2: Classic UI (Legacy)

```bash
# Same steps 1-3 above, then:

# 4. Run
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --log-level debug
# Open: http://localhost:8000
```

## Architecture

```
React Frontend (Port 3000)
    ↓ API Proxy
FastAPI Backend (Port 8000)
    ├─ AI Agent (LangChain)
    │   ├─ Jira Tool → Knowledge Graph ✓
    │   ├─ Confluence Tool → Knowledge Graph ✓
    │   └─ Child Issues Support
    ├─ Knowledge Graph (NetworkX)
    │   • Lazy load (creates if missing)
    │   • Auto-update on every query
    └─ SQLite (Conversation History)
```

### Frontend (NEW!)

- **React + TypeScript + Vite** - Modern, fast development
- **Component-based** - Reusable, testable UI
- **Context Dropdown** - Perfect design, no CSS issues
- **Hot reload** - Instant updates during development
- See [frontend/README.md](frontend/README.md) for details

### 🎯 Skill-Based Architecture (NEW!)

The system now uses **Anthropic's Skills framework** for dynamic capability discovery:

```
User Query → Skill Registry → Skill Orchestrator → Synthesized Answer
                ↓                    ↓
         Find relevant         Execute skills
         skills by LLM        (Jira, Confluence, KG)
```

**Available Skills:**
- 📦 **jira-search** - Search issues with JQL or keywords
- 📦 **confluence-search** - Find pages in personal/team spaces
- 📦 **knowledge-graph-query** - Semantic search cached data
- 📦 **multi-source-synthesizer** - Combine results intelligently

**Benefits:**
- ✅ Extensible: Add skills without code changes
- ✅ Multi-source: Automatically combines Jira + Confluence + KG
- ✅ Adaptive: LLM selects best strategy dynamically

**Try it:**
```bash
# List available skills
curl http://localhost:8000/api/skills

# Execute skill-based query
curl -X POST http://localhost:8000/api/skills/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Find Docker issues"}'
```

See [SKILLS_IMPLEMENTATION.md](SKILLS_IMPLEMENTATION.md) for full details.

### Key Files

- [app/services/core/skill_registry.py](app/services/core/skill_registry.py) - Skill discovery
- [app/services/core/skill_orchestrator.py](app/services/core/skill_orchestrator.py) - Orchestration
- [app/services/core/ai_agent_service.py](app/services/core/ai_agent_service.py) - Legacy AI agent
- [app/services/data/knowledge_graph_service.py](app/services/data/knowledge_graph_service.py) - Auto-loading graph
- [app/services/integrations/jira_service.py](app/services/integrations/jira_service.py) - Jira integration
- [skills/](skills/) - Skill definitions (jira-search, confluence-search, etc.)

## Configuration

```env
# LLM Provider
LLM_PROVIDER=ollama  # or 'openai'
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:latest

# Jira/Confluence (Read-Only)
JIRA_URL=https://your-domain.atlassian.net
JIRA_USERNAME=your_email@example.com
JIRA_API_TOKEN=your_token

# Knowledge Graph (auto-creates if missing)
ENABLE_KNOWLEDGE_GRAPH=true
KNOWLEDGE_GRAPH_PATH=./data/knowledge_graph.gpickle
```

Get tokens: https://id.atlassian.com/manage-profile/security/api-tokens

## Usage

### Example Queries

```
"Show me child issues of ACTHUB-9"
"Tell me about read 12 books in 2025 - how many done, in progress, todo?"
"What are the in-progress items?"
"Analyze project XYZ delivery metrics"
```

### Knowledge Graph CLI

```bash
python kg_cli.py stats      # View statistics
python kg_cli.py populate   # Load from Jira/Confluence
python kg_cli.py search ACTHUB-9
```

## API Documentation

- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Key Endpoints

```bash
POST /api/chat              # Chat with AI
GET  /api/kg/stats          # Graph stats
GET  /api/kg/entity/{id}    # Entity details
```

## Development

```bash
# Tests
pytest

# Code quality
black app/ && flake8 app/
```

## Security

✅ Read-only access  
✅ Environment-based config  
✅ No permanent data storage  
✅ CORS protection  

See [SECURITY.md](SECURITY.md) for details.

## Documentation

- [Quick Start](QUICK_START.md)
- [UV Guide](UV_GUIDE.md)
- [Ollama Guide](OLLAMA_GUIDE.md)
- [Knowledge Graph](KNOWLEDGE_GRAPH.md)
- [MCP Server](MCP_AND_TOOLS_GUIDE.md)

## License

MIT - see [LICENSE](LICENSE)

---

**Built with FastAPI, LangChain, NetworkX, Ollama**

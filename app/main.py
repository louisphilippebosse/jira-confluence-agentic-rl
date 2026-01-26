from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
import logging

from app.config import settings
from app.models.database import init_db
from app.api import chat, knowledge_graph

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Jira-Confluence Agentic AI",
    description="Security-first AI system for delivery intelligence with Knowledge Graph RAG",
    version="1.0.0"
)

# CORS middleware for security
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# Include API routers
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(knowledge_graph.router, prefix="/api/kg", tags=["knowledge-graph"])


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info("Starting application...")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    if settings.llm_provider == "ollama":
        logger.info(f"Ollama URL: {settings.ollama_base_url}, Model: {settings.ollama_model}")
    logger.info(f"Knowledge Graph: {'Enabled' if settings.enable_knowledge_graph else 'Disabled'}")
    init_db()
    logger.info("Database initialized")


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main UI"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "environment": settings.environment,
        "llm_provider": settings.llm_provider,
        "knowledge_graph_enabled": settings.enable_knowledge_graph
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

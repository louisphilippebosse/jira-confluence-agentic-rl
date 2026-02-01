from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import settings
from app.models.database import init_db
from app.api import api_router

# Configure logging - Set to DEBUG for detailed logs
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Set specific loggers to appropriate levels
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

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

# Include the unified API router
app.include_router(api_router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info("Starting application...")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    if settings.llm_provider == "ollama":
        logger.info(f"Ollama URL: {settings.ollama_base_url}, Model: {settings.ollama_model}")
    logger.info(f"Knowledge Graph: {'Enabled' if settings.enable_knowledge_graph else 'Disabled'}")
    logger.info(f"Nano-GraphRAG: {'Enabled' if settings.enable_nano_graphrag else 'Disabled'}")
    init_db()
    logger.info("Database initialized")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import settings
from app.models.database import init_db
from app.api import chat, knowledge_graph, feedback, agents, approvals, rl_metrics

# Configure logging - Set to DEBUG for detailed logs
logging.basicConfig(
    level=logging.DEBUG,  # Change to DEBUG for verbose logging
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Output to console
    ]
)
logger = logging.getLogger(__name__)

# Set specific loggers to appropriate levels
logging.getLogger('httpx').setLevel(logging.WARNING)  # Reduce HTTP noise
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

# Include API routers
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(knowledge_graph.router, prefix="/api/kg", tags=["knowledge-graph"])
app.include_router(feedback.router, prefix="/api/feedback", tags=["feedback"])
app.include_router(agents.router, prefix="/api", tags=["agents"])
app.include_router(approvals.router, tags=["approvals"])  # Already has /api/approvals prefix in router
app.include_router(rl_metrics.router, prefix="/api/rl", tags=["rl-metrics"])


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

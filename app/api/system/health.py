"""
Health API - Application health check endpoints
"""
from fastapi import APIRouter
import logging

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check():
    """Application health check"""
    return {
        "status": "healthy",
        "environment": settings.environment,
        "llm_provider": settings.llm_provider,
        "knowledge_graph_enabled": settings.enable_knowledge_graph,
        "nano_graphrag_enabled": settings.enable_nano_graphrag
    }


@router.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with service status"""
    health = {
        "status": "healthy",
        "services": {}
    }
    
    # Check Ollama
    try:
        import requests
        resp = requests.get(f"{settings.ollama_base_url}/api/tags", timeout=5)
        health["services"]["ollama"] = {
            "status": "up" if resp.status_code == 200 else "degraded",
            "url": settings.ollama_base_url
        }
    except Exception as e:
        health["services"]["ollama"] = {"status": "down", "error": str(e)}
    
    # Check Knowledge Graph
    try:
        from app.services.graphrag.knowledge_graph_service import knowledge_graph_service
        stats = knowledge_graph_service.get_graph_stats()
        health["services"]["knowledge_graph"] = {
            "status": "up" if knowledge_graph_service.enabled else "disabled",
            "nodes": stats.get("total_nodes", 0),
            "edges": stats.get("total_edges", 0)
        }
    except Exception as e:
        health["services"]["knowledge_graph"] = {"status": "error", "error": str(e)}
    
    # Check nano-graphrag
    try:
        from app.services.graphrag.nano_graphrag_service import nano_graphrag_service
        health["services"]["nano_graphrag"] = {
            "status": "up" if nano_graphrag_service.enabled else "disabled"
        }
    except Exception as e:
        health["services"]["nano_graphrag"] = {"status": "error", "error": str(e)}
    
    # Overall status
    down_services = [s for s, v in health["services"].items() if v.get("status") == "down"]
    if down_services:
        health["status"] = "degraded"
    
    return health

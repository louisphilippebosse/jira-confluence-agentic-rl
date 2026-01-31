"""
Knowledge Graph Maintenance API - Refresh and admin operations
"""
import subprocess
import os
import json
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

KG_STATUS_FILE = "./data/kg_refresh_status.json"


def run_kg_refresh():
    """Run Knowledge Graph refresh in background"""
    status = {"progress": 0, "stage": "Starting..."}
    _write_status(status)
    
    try:
        status["stage"] = "Repopulating KG"
        _write_status(status)
        subprocess.run(["python", "-m", "app.maintenance.repopulate_kg"], check=True)
        
        status["progress"] = 50
        status["stage"] = "Building communities"
        _write_status(status)
        subprocess.run(["python", "-m", "app.maintenance.build_communities"], check=True)
        
        status["progress"] = 100
        status["stage"] = "Done"
        _write_status(status)
        logger.info("✅ KG refresh completed successfully")
        
    except Exception as e:
        status["stage"] = f"Error: {str(e)}"
        _write_status(status)
        logger.error(f"❌ KG refresh failed: {e}")


def _write_status(status: dict):
    """Write status to file"""
    os.makedirs(os.path.dirname(KG_STATUS_FILE), exist_ok=True)
    with open(KG_STATUS_FILE, "w") as f:
        json.dump(status, f)


@router.post("/refresh")
def refresh_kg(background_tasks: BackgroundTasks):
    """Start Knowledge Graph refresh in background"""
    background_tasks.add_task(run_kg_refresh)
    logger.info("🔄 KG refresh started in background")
    return {"status": "started", "message": "Knowledge Graph refresh initiated"}


@router.get("/status")
def kg_status():
    """Get Knowledge Graph refresh status"""
    if not os.path.exists(KG_STATUS_FILE):
        return {"progress": 0, "stage": "Not started"}
    with open(KG_STATUS_FILE, "r") as f:
        return json.load(f)


@router.post("/clear")
async def clear_kg():
    """Clear the Knowledge Graph (requires confirmation)"""
    try:
        from app.services.graphrag.knowledge_graph_service import knowledge_graph_service
        
        # Clear the graph
        knowledge_graph_service.graph.clear()
        knowledge_graph_service.save_graph()
        
        logger.info("🗑️ Knowledge Graph cleared")
        return {"status": "cleared", "message": "Knowledge Graph has been cleared"}
        
    except Exception as e:
        logger.error(f"Error clearing KG: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/health")
async def kg_health():
    """Check Knowledge Graph health and connectivity"""
    try:
        from app.services.graphrag.knowledge_graph_service import knowledge_graph_service
        from app.services.graphrag.nano_graphrag_service import nano_graphrag_service
        
        stats = knowledge_graph_service.get_graph_stats()
        graphrag_stats = nano_graphrag_service.get_stats() if nano_graphrag_service.enabled else None
        
        return {
            "legacy_kg": {
                "enabled": knowledge_graph_service.enabled,
                "nodes": stats.get("total_nodes", 0),
                "edges": stats.get("total_edges", 0)
            },
            "nano_graphrag": graphrag_stats,
            "status": "healthy" if knowledge_graph_service.enabled else "disabled"
        }
        
    except Exception as e:
        logger.error(f"Error checking KG health: {e}")
        return {"status": "error", "error": str(e)}

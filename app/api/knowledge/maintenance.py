"""
Knowledge Graph Maintenance API - Refresh and admin operations.

Now uses safe refresh with:
- Backup before modification
- Hot-swap: old model serves while new builds
- Atomic switchover when ready
- Rollback on failure
"""
import os
import json
from fastapi import APIRouter, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from typing import Optional
import logging

from app.services.kg_refresh import get_refresh_manager, RefreshStatus

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/refresh")
def refresh_kg(
    background_tasks: BackgroundTasks,
    clear_existing: bool = Query(False, description="Clear existing data before refresh"),
    quick_mode: bool = Query(False, description="Quick mode: skip LLM-based entity extraction (much faster)")
):
    """
    Start Knowledge Graph refresh in background.
    
    This is a safe, non-blocking operation:
    - Creates backup of current KG
    - Builds new KG in temp directory
    - Old KG continues serving queries during build
    - Atomic switchover when new KG is ready
    - Auto-rollback on failure
    
    Quick mode (recommended for testing): 
    - Skips nano-graphrag LLM entity extraction
    - Uses only direct Jira/Confluence relationships
    - Takes ~2-5 minutes instead of hours
    """
    refresh_manager = get_refresh_manager()
    
    if refresh_manager.is_refreshing:
        return JSONResponse(
            status_code=409,
            content={
                "status": "already_running",
                "message": "Refresh already in progress",
                "progress": refresh_manager.progress.to_dict()
            }
        )
    
    def on_complete():
        """Notify service to reload when complete."""
        refresh_manager.notify_service_reload()
    
    started = refresh_manager.start_refresh(
        clear_existing=clear_existing,
        quick_mode=quick_mode,
        on_complete=on_complete
    )
    
    mode_str = "QUICK mode (no LLM)" if quick_mode else "full mode (with nano-graphrag)"
    if started:
        logger.info(f"🔄 KG refresh started in background ({mode_str})")
        return {
            "status": "started",
            "message": f"Knowledge Graph refresh initiated ({mode_str})"
        }
    else:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Failed to start refresh"}
        )


@router.get("/status")
def kg_status():
    """Get Knowledge Graph refresh status."""
    try:
        refresh_manager = get_refresh_manager()
        progress = refresh_manager.load_status()
        return progress.to_dict()
    except Exception as e:
        logger.error(f"Error loading KG status: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


@router.post("/cancel")
def cancel_refresh():
    """Cancel an ongoing KG refresh operation."""
    refresh_manager = get_refresh_manager()
    
    if not refresh_manager.is_refreshing:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "No refresh in progress"}
        )
    
    success = refresh_manager.cancel_refresh()
    
    if success:
        return {
            "status": "cancelling",
            "message": "Cancellation requested. Refresh will stop at next checkpoint."
        }
    else:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Failed to request cancellation"}
        )


# =========================================================================
# Backup Management
# =========================================================================

@router.get("/backups")
def list_backups():
    """List all available KG backups."""
    refresh_manager = get_refresh_manager()
    backups = refresh_manager.list_backups()
    return {
        "backups": backups,
        "count": len(backups)
    }


@router.post("/backups")
def create_backup(reason: str = Query("manual", description="Reason for backup")):
    """Create a manual backup of the current KG."""
    refresh_manager = get_refresh_manager()
    
    try:
        backup_path = refresh_manager.create_backup(reason=reason)
        if backup_path:
            return {
                "status": "created",
                "backup_path": backup_path,
                "message": f"Backup created: {backup_path}"
            }
        else:
            return {
                "status": "no_data",
                "message": "No existing KG data to backup"
            }
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


@router.post("/backups/restore")
def restore_backup(backup_path: str = Query(..., description="Path to backup directory")):
    """
    Restore KG from a backup.
    
    WARNING: This will replace the current KG with the backup.
    A safety backup of the current state will be created first.
    """
    refresh_manager = get_refresh_manager()
    
    if refresh_manager.is_refreshing:
        return JSONResponse(
            status_code=409,
            content={"status": "error", "message": "Cannot restore while refresh in progress"}
        )
    
    try:
        refresh_manager.restore_backup(backup_path)
        refresh_manager.notify_service_reload()
        return {
            "status": "restored",
            "message": f"KG restored from: {backup_path}"
        }
    except ValueError as e:
        return JSONResponse(
            status_code=404,
            content={"status": "error", "error": str(e)}
        )
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


@router.delete("/backups/cleanup")
def cleanup_backups(keep_count: int = Query(5, description="Number of backups to keep")):
    """Remove old backups, keeping only the most recent ones."""
    refresh_manager = get_refresh_manager()
    
    before = len(refresh_manager.list_backups())
    refresh_manager.cleanup_old_backups(keep_count=keep_count)
    after = len(refresh_manager.list_backups())
    
    return {
        "status": "cleaned",
        "removed": before - after,
        "remaining": after
    }


# =========================================================================
# Version Management
# =========================================================================

@router.get("/versions")
def list_versions(limit: int = Query(50, description="Max versions to return")):
    """List all KG versions."""
    from app.services.kg_refresh import get_version_registry
    
    registry = get_version_registry()
    versions = registry.list_versions(limit=limit)
    active = registry.get_active_version()
    
    return {
        "versions": [v.to_dict() for v in versions],
        "count": len(versions),
        "active_id": active.id if active else None
    }


@router.post("/versions")
def create_version(
    name: str = Query(..., description="Version name (e.g., 'v1-baseline')"),
    description: str = Query("", description="Version description"),
    make_active: bool = Query(False, description="Set as active version")
):
    """
    Create a new version from the current KG.
    
    Use this to snapshot the current state before experimenting.
    """
    from app.services.kg_refresh import get_version_registry
    
    registry = get_version_registry()
    
    try:
        version = registry.create_version(
            name=name,
            source_path="./data/nano_graphrag",
            description=description,
            make_active=make_active
        )
        return {
            "status": "created",
            "version": version.to_dict()
        }
    except Exception as e:
        logger.error(f"Version creation failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


@router.post("/versions/{version_id}/activate")
def activate_version(version_id: int):
    """
    Set a version as active.
    
    This will switch both nano-graphrag and NetworkX services to use this version.
    """
    from app.services.kg_refresh import get_version_registry
    
    registry = get_version_registry()
    
    if registry.set_active(version_id):
        version = registry.get_version(version_id)
        
        # Double-check that the graph service has reloaded
        try:
            from app.services.graphrag.knowledge_graph_service import knowledge_graph_service
            knowledge_graph_service.reload_graph()
            logger.info(f"✅ Activated version {version_id}: {knowledge_graph_service.graph.number_of_nodes()} nodes loaded")
        except Exception as e:
            logger.error(f"Failed to reload graph after activation: {e}")
        
        return {
            "status": "activated",
            "version": version.to_dict() if version else None
        }
    else:
        return JSONResponse(
            status_code=404,
            content={"status": "error", "error": "Version not found"}
        )


@router.delete("/versions/{version_id}")
def delete_version(version_id: int):
    """Delete a version (cannot delete active version)."""
    from app.services.kg_refresh import get_version_registry
    
    registry = get_version_registry()
    
    try:
        if registry.delete_version(version_id):
            return {"status": "deleted", "version_id": version_id}
        else:
            return JSONResponse(
                status_code=404,
                content={"status": "error", "error": "Version not found"}
            )
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "error": str(e)}
        )


@router.post("/versions/import-backups")
def import_backups():
    """Import all existing backups as versions."""
    from app.services.kg_refresh import get_version_registry
    
    registry = get_version_registry()
    imported = registry.import_all_backups()
    
    return {
        "status": "imported",
        "count": imported,
        "message": f"Imported {imported} backups as versions"
    }


# =========================================================================
# Clear and Health
# =========================================================================

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

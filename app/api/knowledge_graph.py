from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import logging

from app.services.knowledge_graph_service import knowledge_graph_service

logger = logging.getLogger(__name__)

router = APIRouter()


class EntitySearch(BaseModel):
    entity_type: Optional[str] = None
    property_filter: Optional[Dict[str, Any]] = None


@router.get("/stats")
async def get_knowledge_graph_stats():
    """Get statistics about the knowledge graph"""
    try:
        return knowledge_graph_service.get_graph_stats()
    except Exception as e:
        logger.error(f"Error getting knowledge graph stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entity/{entity_id}")
async def get_entity(entity_id: str):
    """Get a specific entity from the knowledge graph"""
    try:
        entity = knowledge_graph_service.get_entity(entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        return entity
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entity/{entity_id}/related")
async def get_related_entities(
    entity_id: str,
    relationship_type: Optional[str] = None,
    max_depth: int = 2
):
    """Get entities related to a specific entity"""
    try:
        related = knowledge_graph_service.get_related_entities(
            entity_id,
            relationship_type=relationship_type,
            max_depth=max_depth
        )
        return {"entity_id": entity_id, "related": related}
    except Exception as e:
        logger.error(f"Error getting related entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_entities(search: EntitySearch):
    """Search for entities in the knowledge graph"""
    try:
        results = knowledge_graph_service.search_entities(
            entity_type=search.entity_type,
            property_filter=search.property_filter
        )
        return {"results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Error searching entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/central")
async def get_central_entities(limit: int = 10):
    """Get the most central entities in the knowledge graph"""
    try:
        central = knowledge_graph_service.get_central_entities(limit=limit)
        return {
            "central_entities": [
                {"id": entity_id, "score": score}
                for entity_id, score in central
            ]
        }
    except Exception as e:
        logger.error(f"Error getting central entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/path/{source_id}/{target_id}")
async def find_path(source_id: str, target_id: str):
    """Find the shortest path between two entities"""
    try:
        path = knowledge_graph_service.find_path(source_id, target_id)
        if path is None:
            return {"path": None, "message": "No path found between entities"}
        return {"path": path, "length": len(path) - 1}
    except Exception as e:
        logger.error(f"Error finding path: {e}")
        raise HTTPException(status_code=500, detail=str(e))

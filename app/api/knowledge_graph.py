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


@router.get("/export")
async def export_graph_for_visualization():
    """Export the entire knowledge graph in a format suitable for frontend visualization"""
    try:
        if not knowledge_graph_service.enabled:
            return {
                "nodes": [],
                "edges": [],
                "stats": {"enabled": False, "message": "Knowledge graph is disabled"}
            }
        
        graph = knowledge_graph_service.graph
        
        # Build nodes array
        nodes = []
        for node_id, node_data in graph.nodes(data=True):
            entity_type = node_data.get('entity_type', 'unknown')
            properties = node_data.get('properties', {})
            
            nodes.append({
                "id": node_id,
                "label": node_id,
                "type": entity_type,
                "properties": properties,
                "title": properties.get('summary') or properties.get('title') or node_id,
                "updated_at": node_data.get('updated_at')
            })
        
        # Build edges array
        edges = []
        for source, target, edge_data in graph.edges(data=True):
            edges.append({
                "source": source,
                "target": target,
                "relationship": edge_data.get('relationship_type', 'related'),
                "properties": edge_data.get('properties', {}),
                "created_at": edge_data.get('created_at')
            })
        
        # Get stats
        stats = knowledge_graph_service.get_graph_stats()
        
        logger.info(f"📤 Exported graph: {len(nodes)} nodes, {len(edges)} edges")
        
        return {
            "nodes": nodes,
            "edges": edges,
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"Error exporting graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))

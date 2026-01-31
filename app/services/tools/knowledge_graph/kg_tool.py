"""
Knowledge Graph Tool - KG operations implementing BaseTool interface.
"""
from typing import Dict, Any, List, Optional
import logging

from ..base import ReadOnlyTool, ToolResult, ActionSchema, ToolCapability
from .kg_intent import KGIntentDetector

# Import existing KG services
from app.services.graphrag.knowledge_graph_service import knowledge_graph_service

logger = logging.getLogger(__name__)


class KnowledgeGraphTool(ReadOnlyTool):
    """
    Knowledge Graph Tool - Query relationships and context from the KG.
    
    The Knowledge Graph stores:
    - Jira issues with their relationships
    - Confluence pages
    - Cross-references between them
    - Community/cluster information
    """
    
    def __init__(self):
        self.intent_detector = KGIntentDetector()
        self.kg_service = knowledge_graph_service
        logger.info("KnowledgeGraphTool initialized")
    
    @property
    def name(self) -> str:
        return "knowledge_graph"
    
    @property
    def display_name(self) -> str:
        return "Knowledge Graph"
    
    @property
    def description(self) -> str:
        return (
            "Query the Knowledge Graph for relationships between entities, "
            "historical context, patterns, and cross-references between "
            "Jira issues and Confluence pages."
        )
    
    @property
    def capabilities(self) -> List[ToolCapability]:
        return [ToolCapability.SEARCH, ToolCapability.READ]
    
    @property
    def keywords(self) -> List[str]:
        return [
            'relationship', 'related', 'connection', 'linked',
            'pattern', 'community', 'graph', 'context'
        ]
    
    def can_handle(self, intent: str, message: str, context: Optional[Dict] = None) -> float:
        """Delegate to KGIntentDetector"""
        return self.intent_detector.score(intent, message, context)
    
    def get_actions(self) -> Dict[str, ActionSchema]:
        return {
            "search": ActionSchema(
                name="search",
                description="Search the Knowledge Graph",
                parameters={
                    "query": {"type": "string", "required": True, "description": "Search query"},
                    "entity_type": {"type": "string", "required": False, "description": "Filter by type (jira_issue, confluence_page)"},
                },
                returns="List of matching entities with relationships"
            ),
            "get_entity": ActionSchema(
                name="get_entity",
                description="Get a specific entity and its relationships",
                parameters={
                    "entity_id": {"type": "string", "required": True, "description": "Entity ID (e.g., issue key)"},
                },
                returns="Entity with all relationships"
            ),
            "get_relationships": ActionSchema(
                name="get_relationships",
                description="Get relationships for an entity",
                parameters={
                    "entity_id": {"type": "string", "required": True, "description": "Entity ID"},
                    "relationship_type": {"type": "string", "required": False, "description": "Filter by relationship type"},
                },
                returns="List of relationships"
            ),
            "get_context": ActionSchema(
                name="get_context",
                description="Get contextual information for a query",
                parameters={
                    "query": {"type": "string", "required": True, "description": "Query for context"},
                    "entity_type_filter": {"type": "string", "required": False, "description": "Filter by entity type"},
                },
                returns="Contextual information from the KG"
            ),
        }
    
    async def execute(self, action: str, params: Dict[str, Any]) -> ToolResult:
        """Execute a KG action"""
        try:
            if action == "search":
                return self._execute_search(params)
            elif action == "get_entity":
                return self._execute_get_entity(params)
            elif action == "get_relationships":
                return self._execute_get_relationships(params)
            elif action == "get_context":
                return self._execute_get_context(params)
            else:
                return ToolResult.fail(f"Unknown action: {action}")
        except Exception as e:
            logger.error(f"KG action '{action}' failed: {e}", exc_info=True)
            return ToolResult.fail(str(e))
    
    def _execute_search(self, params: Dict[str, Any]) -> ToolResult:
        """Execute search action"""
        query = params.get("query") or params.get("message", "")
        entity_type = params.get("entity_type")
        
        if not query:
            return ToolResult.fail("query is required")
        
        try:
            results = self.kg_service.search_entities(query, entity_type=entity_type)
            
            if not results:
                return ToolResult.ok([], message="No entities found in Knowledge Graph")
            
            return ToolResult.ok(results, count=len(results))
        except Exception as e:
            logger.error(f"KG search error: {e}")
            return ToolResult.fail(str(e))
    
    def _execute_get_entity(self, params: Dict[str, Any]) -> ToolResult:
        """Execute get_entity action"""
        entity_id = params.get("entity_id")
        
        if not entity_id:
            return ToolResult.fail("entity_id is required")
        
        result = self.kg_service.get_entity(entity_id)
        
        if not result:
            return ToolResult.fail(f"Entity {entity_id} not found")
        
        return ToolResult.ok(result)
    
    def _execute_get_relationships(self, params: Dict[str, Any]) -> ToolResult:
        """Execute get_relationships action"""
        entity_id = params.get("entity_id")
        relationship_type = params.get("relationship_type")
        
        if not entity_id:
            return ToolResult.fail("entity_id is required")
        
        relationships = self.kg_service.get_relationships(
            entity_id, 
            relationship_type=relationship_type
        )
        
        return ToolResult.ok(relationships, count=len(relationships))
    
    def _execute_get_context(self, params: Dict[str, Any]) -> ToolResult:
        """Execute get_context action"""
        query = params.get("query") or params.get("message", "")
        entity_type_filter = params.get("entity_type_filter")
        
        if not query:
            return ToolResult.fail("query is required")
        
        # Use the KG query service for contextual information
        try:
            from app.services.knowledge.kg_query_service import kg_query_service
            context = kg_query_service.get_kg_context_for_query(
                query, 
                entity_type_filter=entity_type_filter
            )
            
            if not context:
                return ToolResult.ok("", message="No contextual information found")
            
            return ToolResult.ok(context)
        except ImportError:
            # Fallback if kg_query_service not available
            return ToolResult.ok("", message="KG query service not available")


# Singleton instance
kg_tool = KnowledgeGraphTool()

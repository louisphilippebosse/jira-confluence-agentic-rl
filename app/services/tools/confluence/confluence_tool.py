"""
Confluence Tool - Unified Confluence operations implementing BaseTool interface.

This is the main entry point for all Confluence operations.
"""
from typing import Dict, Any, List, Optional
import logging
import json

from ..base import ReadOnlyTool, ToolResult, ActionSchema, ToolCapability
from .confluence_intent import ConfluenceIntentDetector

# Import from local package (canonical location)
from .confluence_service import confluence_service
from app.services.graphrag.knowledge_graph_service import knowledge_graph_service
from app.config import settings

logger = logging.getLogger(__name__)


class ConfluenceTool(ReadOnlyTool):
    """
    Confluence Tool - Search and read Confluence documentation.
    
    Implements BaseTool interface for integration with AgentOrchestrator.
    """
    
    def __init__(self, llm=None, mcp_enabled: bool = None):
        """
        Initialize Confluence tool.
        
        Args:
            llm: LangChain LLM for intelligent operations
            mcp_enabled: Whether to use MCP
        """
        self.llm = llm
        self.mcp_enabled = mcp_enabled if mcp_enabled is not None else settings.enable_mcp
        self.intent_detector = ConfluenceIntentDetector()
        
        # Lazy-loaded MCP client
        self._mcp_client = None
        
        logger.info(f"ConfluenceTool initialized (MCP: {self.mcp_enabled})")
    
    @property
    def name(self) -> str:
        return "confluence"
    
    @property
    def display_name(self) -> str:
        return "Confluence"
    
    @property
    def description(self) -> str:
        return (
            "Search and read Confluence documentation, wiki pages, guides, "
            "and knowledge base articles. Read-only access to organizational knowledge."
        )
    
    @property
    def capabilities(self) -> List[ToolCapability]:
        return [ToolCapability.SEARCH, ToolCapability.READ]
    
    @property
    def keywords(self) -> List[str]:
        return [
            'confluence', 'wiki', 'documentation', 'docs', 'page',
            'guide', 'tutorial', 'knowledge base', 'space'
        ]
    
    @property
    def mcp_client(self):
        """Lazy-load MCP client"""
        if self._mcp_client is None and self.mcp_enabled:
            from app.services.orchestration.mcp_operations import mcp_operations
            self._mcp_client = mcp_operations
        return self._mcp_client
    
    def can_handle(self, intent: str, message: str, context: Optional[Dict] = None) -> float:
        """Delegate to ConfluenceIntentDetector"""
        return self.intent_detector.score(intent, message, context)
    
    def get_actions(self) -> Dict[str, ActionSchema]:
        """Return available Confluence actions"""
        return {
            "search": ActionSchema(
                name="search",
                description="Search Confluence pages using keywords",
                parameters={
                    "query": {"type": "string", "required": True, "description": "Search query"},
                    "space_key": {"type": "string", "required": False, "description": "Filter by space key"},
                    "limit": {"type": "integer", "required": False, "description": "Max results (default 10)"},
                    "fetch_full_content": {"type": "boolean", "required": False, "description": "Fetch full page content"},
                },
                returns="List of matching Confluence pages"
            ),
            "get_page": ActionSchema(
                name="get_page",
                description="Get full content of a specific Confluence page",
                parameters={
                    "page_id": {"type": "string", "required": True, "description": "Page ID"},
                },
                returns="Full page content"
            ),
            "get_page_by_title": ActionSchema(
                name="get_page_by_title",
                description="Get a page by its title",
                parameters={
                    "title": {"type": "string", "required": True, "description": "Page title"},
                    "space_key": {"type": "string", "required": False, "description": "Space key"},
                },
                returns="Page content"
            ),
        }
    
    async def execute(self, action: str, params: Dict[str, Any]) -> ToolResult:
        """Execute a Confluence action"""
        try:
            if action == "search":
                return await self._execute_search(params)
            elif action == "get_page":
                return await self._execute_get_page(params)
            elif action == "get_page_by_title":
                return await self._execute_get_page_by_title(params)
            else:
                return ToolResult.fail(f"Unknown action: {action}")
        except Exception as e:
            logger.error(f"Confluence action '{action}' failed: {e}", exc_info=True)
            return ToolResult.fail(str(e))
    
    async def _execute_search(self, params: Dict[str, Any]) -> ToolResult:
        """Execute search action"""
        query = params.get("query") or params.get("message", "")
        space_key = params.get("space_key")
        limit = params.get("limit", 10)
        fetch_full_content = params.get("fetch_full_content", True)
        
        if not query:
            return ToolResult.fail("query is required")
        
        # Try MCP first if enabled
        results = None
        if self.mcp_client:
            results = await self.mcp_client.search_confluence_via_mcp(query, limit)
            if results:
                logger.info(f"MCP search returned {len(results)} pages")
        
        # Fallback to direct API
        if results is None:
            results = confluence_service.search_content(
                query, 
                limit=limit, 
                space_key=space_key,
                fetch_full_content=fetch_full_content
            )
            logger.info(f"Direct API search returned {len(results)} pages")
        
        if not results:
            return ToolResult.ok(
                [],
                message="No Confluence pages found matching your query"
            )
        
        # Add to knowledge graph
        for page in results:
            knowledge_graph_service.add_confluence_page(page)
        
        return ToolResult.ok(
            results,
            count=len(results)
        )
    
    async def _execute_get_page(self, params: Dict[str, Any]) -> ToolResult:
        """Execute get_page action"""
        page_id = params.get("page_id")
        if not page_id:
            return ToolResult.fail("page_id is required")
        
        result = confluence_service.get_page_content(page_id)
        
        if not result:
            return ToolResult.fail(f"Page {page_id} not found")
        
        # Add to knowledge graph
        knowledge_graph_service.add_confluence_page(result)
        
        return ToolResult.ok(result)
    
    async def _execute_get_page_by_title(self, params: Dict[str, Any]) -> ToolResult:
        """Execute get_page_by_title action"""
        title = params.get("title")
        space_key = params.get("space_key")
        
        if not title:
            return ToolResult.fail("title is required")
        
        result = confluence_service.get_page_by_title(title, space_key)
        
        if not result:
            return ToolResult.fail(f"Page '{title}' not found")
        
        # Add to knowledge graph
        knowledge_graph_service.add_confluence_page(result)
        
        return ToolResult.ok(result)
    
    # Convenience methods
    def extract_space_key(self, message: str) -> Optional[str]:
        """Extract Confluence space key from message"""
        return self.intent_detector.extract_space_key(message)


# Singleton instance
confluence_tool = ConfluenceTool()

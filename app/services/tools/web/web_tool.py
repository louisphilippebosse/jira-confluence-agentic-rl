"""
Web Tool - Web search operations implementing BaseTool interface.
"""
from typing import Dict, Any, List, Optional
import logging

from ..base import ReadOnlyTool, ToolResult, ActionSchema, ToolCapability
from .web_intent import WebIntentDetector

# Import from local package (canonical location)
from .web_search_service import web_search_service

logger = logging.getLogger(__name__)


class WebTool(ReadOnlyTool):
    """
    Web Tool - External web search for supplementary information.
    """
    
    def __init__(self):
        self.intent_detector = WebIntentDetector()
        logger.info("WebTool initialized")
    
    @property
    def name(self) -> str:
        return "web"
    
    @property
    def display_name(self) -> str:
        return "Web Search"
    
    @property
    def description(self) -> str:
        return (
            "Search the web for external information like events, schedules, "
            "news, general knowledge, and supplementary context."
        )
    
    @property
    def capabilities(self) -> List[ToolCapability]:
        return [ToolCapability.SEARCH, ToolCapability.READ]
    
    @property
    def keywords(self) -> List[str]:
        return [
            'web', 'google', 'search online', 'internet',
            'weather', 'news', 'event', 'schedule'
        ]
    
    def can_handle(self, intent: str, message: str, context: Optional[Dict] = None) -> float:
        """Delegate to WebIntentDetector"""
        return self.intent_detector.score(intent, message, context)
    
    def get_actions(self) -> Dict[str, ActionSchema]:
        return {
            "search": ActionSchema(
                name="search",
                description="Search the web for information",
                parameters={
                    "query": {"type": "string", "required": True, "description": "Search query"},
                    "num_results": {"type": "integer", "required": False, "description": "Number of results"},
                },
                returns="List of web search results"
            ),
        }
    
    async def execute(self, action: str, params: Dict[str, Any]) -> ToolResult:
        """Execute a web search action"""
        try:
            if action == "search":
                return await self._execute_search(params)
            else:
                return ToolResult.fail(f"Unknown action: {action}")
        except Exception as e:
            logger.error(f"Web search failed: {e}", exc_info=True)
            return ToolResult.fail(str(e))
    
    async def _execute_search(self, params: Dict[str, Any]) -> ToolResult:
        """Execute search action"""
        query = params.get("query") or params.get("message", "")
        max_results = params.get("num_results") or params.get("max_results", 5)
        
        if not query:
            return ToolResult.fail("query is required")
        
        # Clean up query for web search
        clean_query = self.intent_detector.get_search_query(query)
        
        try:
            results = await web_search_service.search(clean_query, max_results=max_results)
            
            if not results:
                return ToolResult.ok([], message="No web results found")
            
            return ToolResult.ok(results, query=clean_query, count=len(results))
        except Exception as e:
            logger.error(f"Web search error: {e}")
            return ToolResult.fail(str(e))


# Singleton instance
web_tool = WebTool()

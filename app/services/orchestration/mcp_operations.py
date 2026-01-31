"""MCP (Model Context Protocol) operations for Atlassian integrations"""
from typing import Optional, List, Dict
import logging

from app.config import settings
from app.services.tools.mcp.atlassian_mcp_client import AtlassianMCPClient

logger = logging.getLogger(__name__)


class MCPOperations:
    """Handles all MCP-specific operations for Jira and Confluence"""
    
    def __init__(self):
        """Initialize MCP client if enabled"""
        self.mcp_client: Optional[AtlassianMCPClient] = None
        if settings.enable_mcp:
            self.mcp_client = AtlassianMCPClient(settings.mcp_proxy_url)
            logger.info("MCP client initialized")
    
    async def _ensure_mcp_initialized(self) -> bool:
        """Ensure MCP client is initialized and ready. Returns True if available."""
        if not settings.enable_mcp or not self.mcp_client:
            return False
        
        try:
            if not hasattr(self.mcp_client, '_initialized') or not self.mcp_client._initialized:
                await self.mcp_client.initialize()
                self.mcp_client._initialized = True
                logger.info("✅ MCP client initialized successfully")
            return True
        except Exception as e:
            logger.warning(f"⚠️ MCP initialization failed: {e}, falling back to direct API")
            return False
    
    async def search_jira_via_mcp(self, jql: str, max_results: int = 20) -> Optional[List[Dict]]:
        """Search Jira issues via MCP. Returns None if MCP unavailable."""
        if not await self._ensure_mcp_initialized():
            return None
        
        try:
            logger.info(f"🔌 Searching Jira via MCP: {jql}")
            result = await self.mcp_client.call_tool(
                "atlassian_jira_jql",
                {"jql": jql, "maxResults": max_results}
            )
            
            if result and 'issues' in result:
                issues = result['issues']
                logger.info(f"✅ MCP returned {len(issues)} issues")
                return issues
            return None
        except Exception as e:
            logger.warning(f"⚠️ MCP search failed: {e}, falling back to direct API")
            return None
    
    async def get_jira_issue_via_mcp(self, issue_key: str) -> Optional[Dict]:
        """Get Jira issue via MCP. Returns None if MCP unavailable."""
        if not await self._ensure_mcp_initialized():
            return None
        
        try:
            logger.info(f"🔌 Getting issue via MCP: {issue_key}")
            result = await self.mcp_client.call_tool(
                "atlassian_jira_issue",
                {"issueIdOrKey": issue_key}
            )
            
            if result:
                logger.info(f"✅ MCP returned issue {issue_key}")
                return result
            return None
        except Exception as e:
            logger.warning(f"⚠️ MCP get issue failed: {e}, falling back to direct API")
            return None
    
    async def search_confluence_via_mcp(self, query: str, limit: int = 10) -> Optional[List[Dict]]:
        """Search Confluence via MCP. Returns None if MCP unavailable."""
        if not await self._ensure_mcp_initialized():
            return None
        
        try:
            logger.info(f"🔌 Searching Confluence via MCP: {query}")
            result = await self.mcp_client.call_tool(
                "atlassian_confluence_search",
                {"cql": f"text ~ \"{query}\"", "limit": limit}
            )
            
            if result and 'results' in result:
                pages = result['results']
                logger.info(f"✅ MCP returned {len(pages)} pages")
                return pages
            return None
        except Exception as e:
            logger.warning(f"⚠️ MCP confluence search failed: {e}, falling back to direct API")
            return None


# Singleton instance
mcp_operations = MCPOperations()

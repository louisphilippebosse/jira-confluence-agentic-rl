"""
Simple MCP client for internal use by AI agent
This allows the agent to use MCP tools through HTTP/JSON
"""
import json
import logging
import httpx
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MCPClient:
    """Simple MCP client for calling tools"""
    
    def __init__(self, approval_api_url: str = "http://localhost:8000/api/approvals"):
        self.approval_api_url = approval_api_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call an MCP tool
        For write operations, returns approval request
        For read operations, executes directly
        """
        logger.info(f"🔧 Calling tool: {tool_name}")
        
        # Determine if this is a write operation
        write_operations = ["create_jira_issue", "update_jira_issue", "transition_jira_issue"]
        
        if tool_name in write_operations:
            # Request approval
            return await self._request_approval(tool_name, arguments)
        else:
            # Execute read operation directly
            return await self._execute_read_tool(tool_name, arguments)
    
    async def _request_approval(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Request user approval for write operation"""
        try:
            response = await self.client.post(
                f"{self.approval_api_url}/request",
                json={
                    "action": action,
                    "parameters": parameters,
                    "reason": f"AI agent proposes: {action}"
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"⏳ Approval requested: {result['approval_id']}")
                
                return {
                    "status": "approval_required",
                    "approval_id": result["approval_id"],
                    "message": "This action requires your approval. Please review and approve in the UI.",
                    "preview": result.get("preview", {})
                }
            else:
                logger.error(f"Failed to request approval: {response.status_code}")
                return {"error": "Failed to request approval"}
                
        except Exception as e:
            logger.error(f"Error requesting approval: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def _execute_read_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute read-only tool directly using service layer"""
        from app.services.jira_service import jira_service
        from app.services.confluence_service import confluence_service
        from app.services.knowledge_graph_service import knowledge_graph_service
        from app.services.web_search_service import web_search_service
        
        try:
            if tool_name == "search_jira_issues":
                results = jira_service.search_issues(
                    arguments["jql"],
                    max_results=arguments.get("max_results", 50)
                )
                return {"results": results, "count": len(results)}
            
            elif tool_name == "get_jira_issue":
                result = jira_service.get_issue(arguments["issue_key"])
                return result or {"error": "Issue not found"}
            
            elif tool_name == "get_child_issues":
                children = jira_service.get_child_issues(arguments["parent_key"])
                return {"children": children, "count": len(children)}
            
            elif tool_name == "search_confluence":
                results = confluence_service.search_content(
                    arguments["query"],
                    limit=arguments.get("limit", 10)
                )
                return {"results": results, "count": len(results)}
            
            elif tool_name == "get_knowledge_graph_stats":
                stats = knowledge_graph_service.get_graph_stats()
                return stats
            
            elif tool_name == "search_knowledge_graph":
                results = knowledge_graph_service.search_entities(
                    entity_type=arguments.get("entity_type"),
                    property_filter=arguments.get("property_filter")
                )
                return {"results": results, "count": len(results)}
            
            elif tool_name == "get_related_entities":
                results = knowledge_graph_service.get_related_entities(
                    entity_id=arguments["entity_id"],
                    relationship_type=arguments.get("relationship_type"),
                    max_depth=arguments.get("max_depth", 2)
                )
                return {"results": results, "count": len(results)}
            
            elif tool_name == "search_web":
                results = await web_search_service.search(
                    query=arguments["query"],
                    max_results=arguments.get("max_results", 5)
                )
                return {"results": results, "count": len(results)}
            
            else:
                return {"error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Singleton instance
mcp_client = MCPClient()

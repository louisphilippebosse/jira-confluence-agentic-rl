"""
Atlassian MCP Client - Model Context Protocol client for Atlassian integrations.

This module provides MCP (Model Context Protocol) connectivity to Atlassian services
(Jira, Confluence) through a proxy server.
"""
from typing import Optional, Dict, Any, List
import logging
import httpx
import json

logger = logging.getLogger(__name__)


class AtlassianMCPClient:
    """
    MCP Client for Atlassian services.
    
    Connects to an MCP proxy server that handles communication with
    Atlassian APIs through the Model Context Protocol.
    """
    
    def __init__(self, proxy_url: str, timeout: float = 30.0):
        """
        Initialize the MCP client.
        
        Args:
            proxy_url: URL of the MCP proxy server
            timeout: Request timeout in seconds
        """
        self.proxy_url = proxy_url.rstrip('/')
        self.timeout = timeout
        self._initialized = False
        self._http_client: Optional[httpx.AsyncClient] = None
        
        logger.info(f"AtlassianMCPClient created with proxy: {proxy_url}")
    
    async def initialize(self) -> bool:
        """
        Initialize the MCP connection.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            if self._http_client is None:
                self._http_client = httpx.AsyncClient(timeout=self.timeout)
            
            # Test connection to proxy
            response = await self._http_client.get(f"{self.proxy_url}/health")
            
            if response.status_code == 200:
                self._initialized = True
                logger.info("✅ MCP client initialized successfully")
                return True
            else:
                logger.warning(f"⚠️ MCP proxy returned status {response.status_code}")
                return False
                
        except httpx.ConnectError as e:
            logger.warning(f"⚠️ Cannot connect to MCP proxy at {self.proxy_url}: {e}")
            return False
        except Exception as e:
            logger.warning(f"⚠️ MCP initialization failed: {e}")
            return False
    
    async def call_tool(self, tool_name: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Call an MCP tool.
        
        Args:
            tool_name: Name of the MCP tool to call (e.g., 'atlassian_jira_jql')
            params: Parameters to pass to the tool
            
        Returns:
            Tool result or None if call failed
        """
        if not self._initialized:
            if not await self.initialize():
                return None
        
        try:
            request_body = {
                "tool": tool_name,
                "params": params
            }
            
            logger.debug(f"🔌 Calling MCP tool: {tool_name} with params: {params}")
            
            response = await self._http_client.post(
                f"{self.proxy_url}/tools/call",
                json=request_body
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.debug(f"✅ MCP tool {tool_name} returned successfully")
                return result
            else:
                logger.warning(f"⚠️ MCP tool call failed with status {response.status_code}: {response.text}")
                return None
                
        except httpx.HTTPError as e:
            logger.warning(f"⚠️ MCP HTTP error calling {tool_name}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ MCP returned invalid JSON for {tool_name}: {e}")
            return None
        except Exception as e:
            logger.warning(f"⚠️ MCP call to {tool_name} failed: {e}")
            return None
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        List available MCP tools.
        
        Returns:
            List of tool definitions
        """
        if not self._initialized:
            if not await self.initialize():
                return []
        
        try:
            response = await self._http_client.get(f"{self.proxy_url}/tools")
            
            if response.status_code == 200:
                return response.json().get('tools', [])
            return []
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to list MCP tools: {e}")
            return []
    
    async def close(self):
        """Close the HTTP client connection."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
            self._initialized = False

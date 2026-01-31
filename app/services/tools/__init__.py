"""
Tools Package - Unified tool implementations following BaseTool interface.

This package contains all tool implementations organized by integration:
- jira/: Jira integration (search, issues, write operations)
- confluence/: Confluence integration (pages, search)
- web/: Web search integration
- knowledge_graph/: Knowledge Graph operations

Each tool implements the BaseTool interface for consistent behavior
and seamless integration with the AgentOrchestrator.
"""
from .base import BaseTool, ToolResult, ToolCapability, ActionSchema, ReadOnlyTool, ReadWriteTool
from .tool_registry import ToolRegistry, tool_registry
from .tool_router import ToolRouter, RoutingDecision, route_and_execute

# Tool implementations
from .jira import JiraTool
from .confluence import ConfluenceTool
from .web import WebTool
from .knowledge_graph import KnowledgeGraphTool

__all__ = [
    # Base classes
    "BaseTool",
    "ToolResult",
    "ToolCapability",
    "ActionSchema",
    "ReadOnlyTool",
    "ReadWriteTool",
    
    # Registry
    "ToolRegistry",
    "tool_registry",
    
    # Router
    "ToolRouter",
    "RoutingDecision",
    "route_and_execute",
    
    # Tool implementations
    "JiraTool",
    "ConfluenceTool",
    "WebTool",
    "KnowledgeGraphTool",
]

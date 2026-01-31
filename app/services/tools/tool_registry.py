"""
Tool Registry - Manages registration and discovery of tools.

Implements the Registry pattern for tool management.
Tools register themselves with the registry, enabling:
- Dynamic tool discovery
- Tool lookup by name or capability
- Extensibility without modifying core code
"""
from typing import Dict, List, Optional, Type
import logging

from .base import BaseTool, ToolCapability

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Central registry for all available tools.
    
    Usage:
        registry = ToolRegistry()
        registry.register(JiraTool())
        registry.register(ConfluenceTool())
        
        jira = registry.get("jira")
        search_tools = registry.get_by_capability(ToolCapability.SEARCH)
    """
    
    _instance: Optional["ToolRegistry"] = None
    
    def __new__(cls) -> "ToolRegistry":
        """Singleton pattern - ensure only one registry exists"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize registry (only runs once due to singleton)"""
        if not self._initialized:
            self._tools: Dict[str, BaseTool] = {}
            self._initialized = True
            logger.info("ToolRegistry initialized")
    
    def register(self, tool: BaseTool) -> None:
        """
        Register a tool with the registry.
        
        Args:
            tool: Tool instance to register
            
        Raises:
            ValueError: If a tool with the same name is already registered
        """
        if tool.name in self._tools:
            logger.warning(f"Tool '{tool.name}' already registered, replacing")
        
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name} ({tool.display_name})")
    
    def unregister(self, name: str) -> bool:
        """
        Unregister a tool by name.
        
        Args:
            name: Tool name to unregister
            
        Returns:
            True if tool was unregistered, False if not found
        """
        if name in self._tools:
            del self._tools[name]
            logger.info(f"Unregistered tool: {name}")
            return True
        return False
    
    def get(self, name: str) -> Optional[BaseTool]:
        """
        Get a tool by name.
        
        Args:
            name: Tool name (e.g., 'jira', 'confluence')
            
        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)
    
    def get_all(self) -> List[BaseTool]:
        """
        Get all registered tools.
        
        Returns:
            List of all tool instances
        """
        return list(self._tools.values())
    
    def get_names(self) -> List[str]:
        """
        Get names of all registered tools.
        
        Returns:
            List of tool names
        """
        return list(self._tools.keys())
    
    def get_by_capability(self, capability: ToolCapability) -> List[BaseTool]:
        """
        Get all tools with a specific capability.
        
        Args:
            capability: Capability to filter by
            
        Returns:
            List of tools with that capability
        """
        return [
            tool for tool in self._tools.values()
            if capability in tool.capabilities
        ]
    
    def get_by_keyword(self, keyword: str) -> List[BaseTool]:
        """
        Get tools whose keywords match the given keyword.
        
        Args:
            keyword: Keyword to match
            
        Returns:
            List of matching tools
        """
        keyword_lower = keyword.lower()
        return [
            tool for tool in self._tools.values()
            if any(kw.lower() in keyword_lower or keyword_lower in kw.lower() 
                   for kw in tool.keywords)
        ]
    
    def get_tool_descriptions(self) -> str:
        """
        Get formatted descriptions of all tools for LLM context.
        
        Returns:
            Formatted string describing all available tools
        """
        if not self._tools:
            return "No tools available."
        
        descriptions = []
        for tool in self._tools.values():
            actions = tool.get_actions()
            action_list = ", ".join(actions.keys()) if actions else "No actions"
            descriptions.append(
                f"- **{tool.display_name}** ({tool.name}): {tool.description}\n"
                f"  Actions: {action_list}"
            )
        
        return "\n".join(descriptions)
    
    def find_best_tool(self, intent: str, message: str, 
                       context: Optional[Dict] = None) -> Optional[BaseTool]:
        """
        Find the best tool to handle a request based on confidence scores.
        
        Args:
            intent: Classified intent
            message: User message
            context: Optional context
            
        Returns:
            Best matching tool or None if no tool scores above threshold
        """
        best_tool = None
        best_score = 0.0
        threshold = 0.3  # Minimum confidence to consider a tool
        
        for tool in self._tools.values():
            score = tool.can_handle(intent, message, context)
            logger.debug(f"Tool {tool.name} scored {score:.2f} for intent '{intent}'")
            
            if score > best_score and score >= threshold:
                best_score = score
                best_tool = tool
        
        if best_tool:
            logger.info(f"Best tool for '{intent}': {best_tool.name} (score: {best_score:.2f})")
        else:
            logger.warning(f"No tool found for intent '{intent}' above threshold {threshold}")
        
        return best_tool
    
    def find_all_matching_tools(self, intent: str, message: str,
                                 context: Optional[Dict] = None,
                                 threshold: float = 0.3) -> List[tuple]:
        """
        Find all tools that can handle a request, sorted by confidence.
        
        Args:
            intent: Classified intent
            message: User message
            context: Optional context
            threshold: Minimum confidence to include
            
        Returns:
            List of (tool, score) tuples, sorted by score descending
        """
        scored_tools = []
        
        for tool in self._tools.values():
            score = tool.can_handle(intent, message, context)
            if score >= threshold:
                scored_tools.append((tool, score))
        
        # Sort by score descending
        scored_tools.sort(key=lambda x: x[1], reverse=True)
        
        return scored_tools
    
    def clear(self) -> None:
        """Clear all registered tools (mainly for testing)"""
        self._tools.clear()
        logger.info("ToolRegistry cleared")
    
    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (mainly for testing)"""
        cls._instance = None


# Global singleton instance
tool_registry = ToolRegistry()

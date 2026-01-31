"""
Base Tool Interface - All tools must implement this interface.

Follows SOLID principles:
- Single Responsibility: Each tool handles one integration
- Open/Closed: Add new tools without modifying orchestrator
- Liskov Substitution: All tools are interchangeable via BaseTool
- Interface Segregation: Clean, minimal interface
- Dependency Inversion: Orchestrator depends on abstraction
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class ToolCapability(Enum):
    """Standard capabilities a tool may support"""
    SEARCH = "search"
    READ = "read"
    WRITE = "write"
    UPDATE = "update"
    DELETE = "delete"
    QUERY_BUILD = "query_build"


@dataclass
class ToolResult:
    """
    Standard result container from any tool execution.
    
    Attributes:
        success: Whether the operation succeeded
        data: The result data (type varies by tool)
        error: Error message if failed
        metadata: Additional context (timing, source, etc.)
    """
    success: bool
    data: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def ok(cls, data: Any, **metadata) -> "ToolResult":
        """Factory for successful results"""
        return cls(success=True, data=data, metadata=metadata)
    
    @classmethod
    def fail(cls, error: str, **metadata) -> "ToolResult":
        """Factory for failed results"""
        return cls(success=False, data=None, error=error, metadata=metadata)


@dataclass
class ActionSchema:
    """Schema for a tool action"""
    name: str
    description: str
    parameters: Dict[str, Dict[str, Any]]  # param_name -> {type, required, description}
    returns: str  # Description of return type


class BaseTool(ABC):
    """
    Abstract base class for all tools (Jira, Confluence, Web, KG, etc.)
    
    Each tool encapsulates:
    - Intent detection (can it handle this request?)
    - Action execution (perform the operation)
    - Result formatting
    
    This enables the AgentOrchestrator to be completely tool-agnostic.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique tool identifier.
        
        Examples: 'jira', 'confluence', 'web', 'knowledge_graph'
        """
        pass
    
    @property
    @abstractmethod
    def display_name(self) -> str:
        """
        Human-readable name for UI/logs.
        
        Examples: 'Jira', 'Confluence', 'Web Search', 'Knowledge Graph'
        """
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """
        Description for LLM routing decisions.
        
        Should clearly describe what this tool can do so the LLM
        can make informed routing decisions.
        """
        pass
    
    @property
    @abstractmethod
    def capabilities(self) -> List[ToolCapability]:
        """
        List of capabilities this tool supports.
        
        Used for filtering tools by required capability.
        """
        pass
    
    @property
    def keywords(self) -> List[str]:
        """
        Keywords that indicate this tool should be used.
        
        Override in subclasses for keyword-based routing.
        Default returns empty list (no keyword matching).
        """
        return []
    
    @abstractmethod
    def can_handle(self, intent: str, message: str, context: Optional[Dict] = None) -> float:
        """
        Return confidence score (0.0-1.0) that this tool can handle the request.
        
        Enables intelligent routing without hard-coding in orchestrator.
        Higher score = more confident this tool is appropriate.
        
        Args:
            intent: Classified intent (e.g., 'search_issues', 'get_documentation')
            message: Original user message
            context: Optional context (conversation history, etc.)
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        pass
    
    @abstractmethod
    async def execute(self, action: str, params: Dict[str, Any]) -> ToolResult:
        """
        Execute an action with given parameters.
        
        Args:
            action: Action to perform (e.g., 'search', 'get_issue')
            params: Action parameters
            
        Returns:
            ToolResult with success/failure and data
        """
        pass
    
    @abstractmethod
    def get_actions(self) -> Dict[str, ActionSchema]:
        """
        Return available actions with their schemas.
        
        Used for:
        - LLM to understand what actions are available
        - Validation of action parameters
        - Documentation generation
        
        Returns:
            Dict mapping action name to ActionSchema
        """
        pass
    
    def validate_params(self, action: str, params: Dict[str, Any]) -> Optional[str]:
        """
        Validate parameters for an action.
        
        Args:
            action: Action name
            params: Parameters to validate
            
        Returns:
            Error message if validation fails, None if valid
        """
        actions = self.get_actions()
        if action not in actions:
            return f"Unknown action: {action}. Available: {list(actions.keys())}"
        
        schema = actions[action]
        for param_name, param_schema in schema.parameters.items():
            if param_schema.get("required", False) and param_name not in params:
                return f"Missing required parameter: {param_name}"
        
        return None
    
    async def safe_execute(self, action: str, params: Dict[str, Any]) -> ToolResult:
        """
        Execute with validation and error handling.
        
        Wraps execute() with:
        - Parameter validation
        - Exception handling
        - Logging
        """
        import logging
        logger = logging.getLogger(f"tool.{self.name}")
        
        # Validate parameters
        validation_error = self.validate_params(action, params)
        if validation_error:
            logger.warning(f"Validation failed: {validation_error}")
            return ToolResult.fail(validation_error)
        
        try:
            logger.info(f"Executing {action} with params: {list(params.keys())}")
            result = await self.execute(action, params)
            logger.info(f"Execution completed: success={result.success}")
            return result
        except Exception as e:
            logger.error(f"Execution failed: {e}", exc_info=True)
            return ToolResult.fail(str(e))


class ReadOnlyTool(BaseTool):
    """Base class for read-only tools (no write/update/delete)"""
    
    @property
    def capabilities(self) -> List[ToolCapability]:
        return [ToolCapability.SEARCH, ToolCapability.READ]


class ReadWriteTool(BaseTool):
    """Base class for tools with full CRUD capabilities"""
    
    @property
    def capabilities(self) -> List[ToolCapability]:
        return [
            ToolCapability.SEARCH,
            ToolCapability.READ,
            ToolCapability.WRITE,
            ToolCapability.UPDATE,
            ToolCapability.DELETE
        ]

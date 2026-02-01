"""
Tool Router - Routes user requests to appropriate tools.

Uses intent classification and tool confidence scoring to determine
which tool(s) should handle a request.
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging
import re

from .base import BaseTool, ToolResult
from .tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class RoutingDecision:
    """Result of routing a request"""
    tools: List[BaseTool]
    scores: Dict[str, float]  # tool_name -> confidence score
    strategy: str  # 'single', 'parallel', 'sequential', 'agentic'
    reasoning: str


class ToolRouter:
    """
    Routes user requests to appropriate tool(s).
    
    Supports multiple routing strategies:
    - Single: Route to one best tool
    - Parallel: Execute multiple tools in parallel
    - Sequential: Execute tools in sequence (output of one feeds next)
    - Agentic: Use plan-execute-reflect loop for complex queries
    """
    
    def __init__(self, registry: ToolRegistry = None, llm=None):
        """
        Initialize router.
        
        Args:
            registry: Tool registry (uses global singleton if not provided)
            llm: Optional LLM for intelligent routing decisions
        """
        self.registry = registry or ToolRegistry()
        self.llm = llm
    
    def route(self, intent: str, message: str, 
              context: Optional[Dict] = None,
              explicit_tools: Optional[List[str]] = None) -> RoutingDecision:
        """
        Route a request to appropriate tool(s).
        
        Args:
            intent: Classified intent
            message: User message
            context: Optional context (conversation history, etc.)
            explicit_tools: If provided, use these tools instead of auto-routing
            
        Returns:
            RoutingDecision with selected tools and strategy
        """
        # If user explicitly selected tools, use those
        if explicit_tools:
            return self._route_explicit(explicit_tools, message)
        
        # Check for multi-tool indicators
        if self._is_multi_tool_query(message):
            return self._route_parallel(intent, message, context)
        
        # Check for complex/agentic query
        if self._is_agentic_query(message):
            return self._route_agentic(intent, message, context)
        
        # Default: single best tool
        return self._route_single(intent, message, context)
    
    def _route_explicit(self, tool_names: List[str], message: str) -> RoutingDecision:
        """Route to explicitly selected tools"""
        tools = []
        scores = {}
        
        for name in tool_names:
            tool = self.registry.get(name)
            if tool:
                tools.append(tool)
                scores[name] = 1.0  # Explicit selection = full confidence
            else:
                logger.warning(f"Requested tool '{name}' not found")
        
        strategy = "parallel" if len(tools) > 1 else "single"
        
        return RoutingDecision(
            tools=tools,
            scores=scores,
            strategy=strategy,
            reasoning=f"User explicitly selected: {tool_names}"
        )
    
    def _route_single(self, intent: str, message: str, 
                      context: Optional[Dict]) -> RoutingDecision:
        """Route to single best tool, but include Knowledge Graph for data sources"""
        best_tool = self.registry.find_best_tool(intent, message, context)
        
        if best_tool:
            score = best_tool.can_handle(intent, message, context)
            
            # For Jira/Confluence queries, also check Knowledge Graph in parallel
            # since the data might already be cached there
            if best_tool.name in ('jira', 'confluence'):
                kg_tool = self.registry.get('knowledge_graph')
                if kg_tool:
                    kg_score = kg_tool.can_handle(intent, message, context)
                    if kg_score > 0.1:  # KG has some relevance
                        return RoutingDecision(
                            tools=[best_tool, kg_tool],
                            scores={best_tool.name: score, 'knowledge_graph': kg_score},
                            strategy="parallel",
                            reasoning=f"Searching {best_tool.display_name} + Knowledge Graph cache"
                        )
            
            return RoutingDecision(
                tools=[best_tool],
                scores={best_tool.name: score},
                strategy="single",
                reasoning=f"Best match: {best_tool.display_name} (confidence: {score:.2f})"
            )
        
        return RoutingDecision(
            tools=[],
            scores={},
            strategy="single",
            reasoning="No tool matched the request"
        )
    
    def _route_parallel(self, intent: str, message: str,
                        context: Optional[Dict]) -> RoutingDecision:
        """Route to multiple tools for parallel execution"""
        matching_tools = self.registry.find_all_matching_tools(
            intent, message, context, threshold=0.3
        )
        
        tools = [tool for tool, _ in matching_tools]
        scores = {tool.name: score for tool, score in matching_tools}
        
        return RoutingDecision(
            tools=tools,
            scores=scores,
            strategy="parallel",
            reasoning=f"Multi-source query, searching: {[t.name for t in tools]}"
        )
    
    def _route_agentic(self, intent: str, message: str,
                       context: Optional[Dict]) -> RoutingDecision:
        """Route for agentic execution (plan-execute-reflect)"""
        # For agentic mode, we may need multiple tools
        matching_tools = self.registry.find_all_matching_tools(
            intent, message, context, threshold=0.2  # Lower threshold for agentic
        )
        
        tools = [tool for tool, _ in matching_tools]
        scores = {tool.name: score for tool, score in matching_tools}
        
        return RoutingDecision(
            tools=tools,
            scores=scores,
            strategy="agentic",
            reasoning="Complex query requiring multi-step reasoning"
        )
    
    def _is_multi_tool_query(self, message: str) -> bool:
        """
        Detect if query should search multiple sources.
        
        Indicators:
        - Mentions multiple source types (Jira AND Confluence)
        - Ambiguous queries that could come from any source
        - Comparison/relationship queries
        """
        message_lower = message.lower()
        
        # Explicit multi-source mentions
        jira_words = {'jira', 'issue', 'ticket', 'epic', 'story', 'bug', 'task', 'sprint'}
        confluence_words = {'confluence', 'documentation', 'docs', 'wiki', 'page'}
        
        has_jira = any(word in message_lower for word in jira_words)
        has_confluence = any(word in message_lower for word in confluence_words)
        
        if has_jira and has_confluence:
            return True
        
        # Ambiguous - no clear source indicator
        has_jira_key = bool(re.search(r'\b[A-Z]+-\d+\b', message))
        if not has_jira_key and not has_jira and not has_confluence:
            # Generic query like "tell me about project X"
            return True
        
        return False
    
    def _is_agentic_query(self, message: str) -> bool:
        """
        Detect if query needs agentic (plan-execute-reflect) approach.
        
        Indicators:
        - Multi-step reasoning ("find X, then based on that...")
        - Investigation/research queries
        - Comparison across sources
        - Complex conditional logic
        """
        message_lower = message.lower()
        
        agentic_patterns = [
            r'\b(and then|after that|based on|using that|with that|from there)\b',
            r'\b(first.*then|find.*and.*also|get.*and.*compare)\b',
            r'\b(how does.*relate to|connection between|relationship between)\b',
            r'\b(investigate|research|analyze|deep dive|look into)\b',
            r'\b(compare|contrast|difference between|similarities)\b',
            r'\b(why.*and.*how|what.*and.*why|who.*and.*what)\b',
            r'\b(all.*related|everything about|comprehensive|full picture)\b',
        ]
        
        for pattern in agentic_patterns:
            if re.search(pattern, message_lower):
                return True
        
        # Long queries often need multi-step reasoning
        if len(message.split()) > 25:
            return True
        
        return False


# Convenience function for routing
async def route_and_execute(message: str, intent: str = "search",
                            context: Optional[Dict] = None,
                            explicit_tools: Optional[List[str]] = None) -> Dict[str, ToolResult]:
    """
    Route a request and execute with appropriate tools.
    
    Args:
        message: User message
        intent: Classified intent
        context: Optional context
        explicit_tools: Optional explicit tool selection
        
    Returns:
        Dict mapping tool names to their results
    """
    router = ToolRouter()
    decision = router.route(intent, message, context, explicit_tools)
    
    results = {}
    
    if decision.strategy == "single":
        if decision.tools:
            tool = decision.tools[0]
            result = await tool.safe_execute("search", {"message": message})
            results[tool.name] = result
    
    elif decision.strategy == "parallel":
        import asyncio
        
        async def execute_tool(tool: BaseTool) -> tuple:
            result = await tool.safe_execute("search", {"message": message})
            return tool.name, result
        
        tasks = [execute_tool(tool) for tool in decision.tools]
        tool_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for item in tool_results:
            if isinstance(item, Exception):
                logger.error(f"Tool execution failed: {item}")
            else:
                name, result = item
                results[name] = result
    
    elif decision.strategy == "agentic":
        # Agentic execution would be handled by AgenticOrchestrator
        # For now, fall back to parallel
        logger.info("Agentic strategy requested - delegating to parallel for now")
        for tool in decision.tools:
            result = await tool.safe_execute("search", {"message": message})
            results[tool.name] = result
    
    return results

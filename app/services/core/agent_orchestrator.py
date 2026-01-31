"""
Agent Orchestrator - Tool-agnostic AI agent orchestration.

This is the refactored version of AIAgentService that follows SOLID principles:
- Single Responsibility: Only handles orchestration, not tool-specific logic
- Open/Closed: Add new tools without modifying this class
- Liskov Substitution: All tools are interchangeable via BaseTool
- Interface Segregation: Clean interfaces between components
- Dependency Inversion: Depends on abstractions (BaseTool), not implementations

The orchestrator:
1. Receives user messages
2. Classifies intent using IntentClassifier
3. Routes to appropriate tool(s) using ToolRouter
4. Executes tools and collects results
5. Synthesizes response using LLM
"""
from typing import Dict, Any, List, Optional
import logging
import json

from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

from app.config import settings
from app.services.tools import ToolRegistry, ToolRouter, ToolResult
from app.services.intelligence.intent_classifier import IntentClassifier, ClassifiedIntent

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """
    Tool-agnostic AI agent orchestrator.
    
    Responsibilities:
    - Conversation management
    - Intent classification (via IntentClassifier)
    - Tool routing (via ToolRouter)
    - Response synthesis
    
    Does NOT contain any tool-specific logic.
    All Jira, Confluence, Web, KG specific code is in the respective tools.
    """
    
    def __init__(self, llm=None):
        """
        Initialize the orchestrator.
        
        Args:
            llm: Optional LLM instance. If not provided, one will be created.
        """
        self.llm = llm or self._initialize_llm()
        self.tool_registry = ToolRegistry()
        self.tool_router = ToolRouter(self.tool_registry, self.llm)
        self.intent_classifier = IntentClassifier(self.llm)
        
        # Lazy tool registration
        self._tools_registered = False
        
        # Initialize SkillMiddleware for enhanced query processing
        self._skill_middleware = None
        self._init_skill_middleware()
        
        logger.info("AgentOrchestrator initialized")
    
    def _init_skill_middleware(self):
        """Initialize SkillMiddleware for enhanced processing"""
        try:
            from app.services.core.skill_middleware import SkillMiddleware
            
            # Use factory method - keeps Jira/Confluence knowledge inside SkillMiddleware
            self._skill_middleware = SkillMiddleware.create(self.llm)
            logger.info("🎯 SkillMiddleware integrated into AgentOrchestrator")
        except Exception as e:
            logger.warning(f"⚠️ Could not initialize SkillMiddleware: {e}", exc_info=True)
            self._skill_middleware = None
    
    def _initialize_llm(self):
        """Initialize LLM based on provider configuration"""
        if settings.llm_provider == "ollama":
            logger.info(f"Initializing Ollama with model: {settings.ollama_model}")
            return ChatOllama(
                base_url=settings.ollama_base_url,
                model=settings.ollama_model,
                temperature=0.7,
            )
        else:  # openai
            logger.info("Initializing OpenAI")
            return ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.7,
                api_key=settings.openai_api_key
            )
    
    def _ensure_tools_registered(self):
        """Lazy registration of tools"""
        if self._tools_registered:
            return
        
        try:
            # Import and register tools
            from app.services.tools.jira import JiraTool
            from app.services.tools.confluence import ConfluenceTool
            from app.services.tools.web import WebTool
            from app.services.tools.knowledge_graph import KnowledgeGraphTool
            
            self.tool_registry.register(JiraTool(self.llm))
            self.tool_registry.register(ConfluenceTool(self.llm))
            self.tool_registry.register(WebTool())
            self.tool_registry.register(KnowledgeGraphTool())
            
            self._tools_registered = True
            logger.info(f"Registered {len(self.tool_registry.get_all())} tools")
        except ImportError as e:
            logger.warning(f"Could not import all tools: {e}")
    
    async def chat(self, message: str, session_id: str,
                   conversation_history: List = None,
                   recommended_action: str = None,
                   context_modes: List[str] = None) -> str:
        """
        Process a chat message and return response.
        
        This is the main entry point, maintaining the same interface
        as the original AIAgentService for backward compatibility.
        
        Args:
            message: User message
            session_id: Session identifier
            conversation_history: Previous conversation messages
            recommended_action: Optional RL-recommended action
            context_modes: Optional list of context modes from frontend
            
        Returns:
            Generated response string
        """
        try:
            logger.info(f"📨 Processing message: {message[:100]}...")
            
            # Ensure tools are registered
            self._ensure_tools_registered()
            
            # Build conversation context
            context = self._build_context(conversation_history)
            
            # Step 0: Use SkillMiddleware for enhanced query analysis (if available)
            skill_analysis = None
            if self._skill_middleware:
                try:
                    logger.info("🧠 Running SkillMiddleware analysis...")
                    skill_analysis = await self._skill_middleware.analyze_query(message, conversation_history)
                    logger.info(f"🎯 Skill analysis: intent={skill_analysis.get('intent')}, sources={skill_analysis.get('data_sources')}")
                except Exception as e:
                    logger.warning(f"⚠️ Skill analysis failed: {e}", exc_info=True)
            else:
                logger.debug("SkillMiddleware not available, skipping skill analysis")
            
            # Step 1: Classify intent (use skill analysis if available)
            logger.info("🎯 Classifying intent...")
            intent = await self.intent_classifier.classify(message, conversation_history)
            logger.info(f"✅ Intent: {intent.primary_intent}/{intent.action} (confidence: {intent.confidence:.2f})")
            
            # Enhance routing with skill analysis data sources
            suggested_tools = None
            if skill_analysis and skill_analysis.get('data_sources'):
                suggested_tools = skill_analysis['data_sources']
                logger.info(f"🎯 Skill suggests tools: {suggested_tools}")
            
            # Step 2: Route to tools
            logger.info("🔀 Routing to tools...")
            routing_decision = self.tool_router.route(
                intent=intent.action,
                message=message,
                context={"conversation_history": conversation_history, "skill_analysis": skill_analysis},
                explicit_tools=context_modes if context_modes else suggested_tools
            )
            
            if not routing_decision.tools:
                logger.warning("No tools matched, using general conversation")
                return self._general_conversation(message, context)
            
            logger.info(f"✅ Routed to: {[t.name for t in routing_decision.tools]} ({routing_decision.strategy})")
            
            # Step 3: Execute tools
            results = await self._execute_tools(
                routing_decision.tools,
                routing_decision.strategy,
                intent,
                message,
                skill_analysis=skill_analysis
            )
            
            # Step 4: Synthesize response
            response = self._synthesize_response(
                message=message,
                intent=intent,
                results=results,
                context=context,
                routing_strategy=routing_decision.strategy
            )
            
            return response
            
        except Exception as e:
            logger.error(f"❌ Error in chat processing: {e}", exc_info=True)
            return f"I apologize, but an error occurred: {str(e)}"
    
    def _build_context(self, conversation_history: Optional[List]) -> str:
        """Build context string from conversation history"""
        if not conversation_history or len(conversation_history) <= 1:
            return ""
        
        recent_history = conversation_history[-10:]
        context = "\n\nConversation History:\n"
        
        for msg in recent_history:
            if hasattr(msg, 'role') and hasattr(msg, 'content'):
                context += f"{msg.role.capitalize()}: {msg.content[:200]}\n"
            elif isinstance(msg, dict):
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')[:200]
                context += f"{role.capitalize()}: {content}\n"
        
        logger.info(f"💭 Including {len(recent_history)} previous messages for context")
        return context
    
    async def _execute_tools(self, tools: List, strategy: str,
                             intent: ClassifiedIntent, message: str,
                             skill_analysis: Dict = None) -> Dict[str, ToolResult]:
        """Execute tools based on routing strategy"""
        results = {}
        
        # Map generic intent actions to tool-specific actions
        action = self._map_action_for_tool(intent.action, tools[0] if tools else None, message)
        
        # Build params from message and skill analysis
        params = {"query": message, "message": message}
        if skill_analysis:
            # Add extracted entities as additional params
            entities = skill_analysis.get('entities', {})
            if entities.get('issue_keys'):
                params['issue_keys'] = entities['issue_keys']
            if entities.get('keywords'):
                params['keywords'] = entities['keywords']
            if entities.get('project_names'):
                params['project'] = entities['project_names'][0] if entities['project_names'] else None
            logger.info(f"🎯 Enhanced params from skill analysis: {list(params.keys())}")
        
        if strategy == "single":
            # Execute single best tool
            tool = tools[0]
            result = await tool.safe_execute(action, params)
            results[tool.name] = result
            logger.info(f"✅ {tool.name}: success={result.success}")
        
        elif strategy == "parallel":
            # Execute all tools in parallel
            import asyncio
            
            async def execute_tool(tool):
                tool_action = self._map_action_for_tool(intent.action, tool, message)
                result = await tool.safe_execute(tool_action, params)
                return tool.name, result
            
            tasks = [execute_tool(tool) for tool in tools]
            tool_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for item in tool_results:
                if isinstance(item, Exception):
                    logger.error(f"Tool execution failed: {item}")
                else:
                    name, result = item
                    results[name] = result
                    logger.info(f"✅ {name}: success={result.success}")
        
        elif strategy == "agentic":
            # Agentic execution - plan, execute, reflect, adapt
            # For now, fall back to sequential with reflection
            logger.info("🧠 Using agentic strategy (sequential with reflection)")
            
            for tool in tools:
                tool_action = self._map_action_for_tool(intent.action, tool, message)
                result = await tool.safe_execute(tool_action, params)
                results[tool.name] = result
                
                # Simple reflection: if we got good results, we might stop early
                if result.success and result.data:
                    data = result.data
                    if isinstance(data, list) and len(data) > 5:
                        logger.info(f"Agentic: {tool.name} returned sufficient results, stopping")
                        break
                    elif isinstance(data, dict) and data:
                        logger.info(f"Agentic: {tool.name} returned valid data")
        
        elif strategy == "sequential":
            # Execute tools in sequence
            for tool in tools:
                tool_action = self._map_action_for_tool(intent.action, tool, message)
                result = await tool.safe_execute(tool_action, params)
                results[tool.name] = result
                logger.info(f"✅ {tool.name}: success={result.success}")
        
        return results
    
    def _map_action_for_tool(self, intent_action: str, tool, message: str) -> str:
        """
        Map generic intent actions to tool-specific actions.
        
        The intent classifier returns actions like 'search', 'multi_step_search', 'get_details'
        but tools have their own action vocabularies. This method translates between them.
        """
        if tool is None:
            return intent_action
        
        # Get available actions for this tool
        available_actions = list(tool.get_actions().keys())
        
        # If the intent action is already valid for this tool, use it
        if intent_action in available_actions:
            return intent_action
        
        # Map generic actions to tool-specific actions
        action_mapping = {
            # Search-related mappings
            'multi_step_search': 'search',
            'lookup': 'search',
            'find': 'search',
            'query': 'search',
            
            # Detail/investigation mappings
            'get_details': 'get_issue' if tool.name == 'jira' else 'search',
            'investigate': 'search',
            'analyze': 'search',
            
            # Child issues specific
            'get_children': 'get_child_issues',
            'child_issues': 'get_child_issues',
            'subtasks': 'get_child_issues',
        }
        
        mapped = action_mapping.get(intent_action, 'search')
        
        # Ensure mapped action exists in tool
        if mapped not in available_actions:
            # Fall back to first available action (usually 'search')
            mapped = available_actions[0] if available_actions else 'search'
            logger.debug(f"Action '{intent_action}' not in {tool.name}, using '{mapped}'")
        
        return mapped
    
    def _synthesize_response(self, message: str, intent: ClassifiedIntent,
                             results: Dict[str, ToolResult], context: str,
                             routing_strategy: str) -> str:
        """Synthesize final response from tool results"""
        
        # Build results context
        results_context = []
        has_data = False
        
        for tool_name, result in results.items():
            if result.success and result.data:
                has_data = True
                data_str = self._format_result_data(result.data)
                results_context.append(f"**{tool_name.title()} Results:**\n{data_str}")
            elif result.error:
                results_context.append(f"**{tool_name.title()}:** Error - {result.error}")
        
        if not has_data:
            return self._no_results_response(message, results)
        
        combined_results = "\n\n---\n\n".join(results_context)
        
        # Create synthesis prompt
        prompt = f"""User asked: {message}
{context}

I searched the following sources and found:

{combined_results}

CRITICAL RULES:
1. Base your response ONLY on the actual data provided above
2. DO NOT invent information or add external knowledge
3. If the data doesn't fully answer the question, acknowledge it
4. Be conversational but factual

FORMATTING:
- Use markdown (headers, lists, tables, code blocks)
- Include issue keys in backticks (`KEY-123`)
- Be helpful and engaging

Provide a comprehensive response based on the data above."""
        
        response = self.llm.invoke(prompt)
        return response.content
    
    def _format_result_data(self, data: Any) -> str:
        """Format result data for LLM context"""
        if isinstance(data, str):
            return data
        elif isinstance(data, list):
            return json.dumps(data, indent=2, default=str)
        elif isinstance(data, dict):
            return json.dumps(data, indent=2, default=str)
        else:
            return str(data)
    
    def _no_results_response(self, message: str, results: Dict[str, ToolResult]) -> str:
        """Generate response when no results found"""
        errors = [f"{name}: {r.error}" for name, r in results.items() if r.error]
        
        if errors:
            return f"I searched but encountered some issues:\n" + "\n".join(f"- {e}" for e in errors)
        
        return "I searched but couldn't find any results matching your query. Try rephrasing or being more specific."
    
    def _general_conversation(self, message: str, context: str) -> str:
        """Handle general conversation without tool routing"""
        system_message = """You are an intelligent AI assistant specialized in delivery intelligence and decision support.

You have access to Jira, Confluence, and web search for information retrieval.
You can help with:
- Finding and analyzing Jira issues, epics, stories, bugs
- Searching Confluence documentation
- Answering questions about projects and work items

If you need specific data, let the user know what to ask for."""

        full_prompt = f"{system_message}\n{context}\n\nUser: {message}\n\nAssistant:"
        response = self.llm.invoke(full_prompt)
        return response.content


# Singleton instance for convenience
agent_orchestrator = AgentOrchestrator()

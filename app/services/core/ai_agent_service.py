
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from typing import Dict, Any, List, Optional
import logging
import json
import re
from datetime import datetime

from app.config import settings
from app.services.tools.jira.jira_service import jira_service
from app.services.tools.jira.jira_query_builder import JiraQueryBuilder
from app.services.graphrag.knowledge_graph_service import knowledge_graph_service
from app.services.orchestration.mcp_operations import mcp_operations
from app.services.orchestration.search_orchestrator import SearchOrchestrator
from app.services.tools.jira.jira_write_service import JiraWriteService
from app.services.core.skill_middleware import SkillMiddleware

logger = logging.getLogger(__name__)



class AIAgentService:
    """Agentic AI system for delivery intelligence and decision support with Knowledge Graph RAG"""
    
    def __init__(self):
        self.llm = self._initialize_llm()
        
        # Initialize component services first
        from app.services.intelligence.query_analyzer_service import QueryAnalyzerService
        from app.services.intelligence.result_verifier import ResultVerifier
        
        query_analyzer = QueryAnalyzerService()
        jql_builder = JiraQueryBuilder(self.llm)
        result_verifier = ResultVerifier(self.llm)
        
        self.skill_middleware = SkillMiddleware(
            llm=self.llm,
            query_analyzer=query_analyzer,
            jql_builder=jql_builder,
            result_verifier=result_verifier,
            kg_service=knowledge_graph_service
        )
        self.query_builder = JiraQueryBuilder(llm=self.llm)
        self.search_orchestrator = SearchOrchestrator(self.llm, skill_middleware=self.skill_middleware)
        self.jira_write_service = JiraWriteService(self.llm)
    
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
    
    # MCP operations delegated to mcp_operations singleton
    async def _search_jira_via_mcp(self, jql: str, max_results: int = 20) -> Optional[List[Dict]]:
        """Delegate to mcp_operations service"""
        return await mcp_operations.search_jira_via_mcp(jql, max_results)
    
    async def _get_jira_issue_via_mcp(self, issue_key: str) -> Optional[Dict]:
        """Delegate to mcp_operations service"""
        return await mcp_operations.get_jira_issue_via_mcp(issue_key)
    
    async def _search_confluence_via_mcp(self, query: str, limit: int = 10) -> Optional[List[Dict]]:
        """Delegate to mcp_operations service"""
        return await mcp_operations.search_confluence_via_mcp(query, limit)
    
    def _verify_search_intent(self, message: str, recommended_action: str) -> Dict[str, Any]:
        """Use LLM to verify if user intent matches the recommended action"""
        try:
            prompt = f"""Analyze if this user message is asking about {recommended_action.replace('_', ' ')}.

User message: "{message}"

Recommended action: {recommended_action}

Question: Is the user asking about Jira issues/tickets or Confluence documentation?

Consider:
- They might not use explicit keywords like "jira" or "issue"
- They might refer to work items, tasks, features, epics, stories implicitly
- They might be asking about something documented in the system
- Context matters: "Extract some philosophy book" likely refers to a Jira issue/epic about reading philosophy

Respond in this format:
INTENT: <jira|confluence|general>
REASON: <one sentence explanation>

Examples:
"show me the login bug" → INTENT: jira | REASON: Asking about a bug (work item)
"extract philosophy book" → INTENT: jira | REASON: Likely referring to a work item/epic about extracting philosophy content
"how do I deploy" → INTENT: confluence | REASON: Asking for documentation/guide
"what's the weather" → INTENT: general | REASON: Not work-related"""
            
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            
            intent_match = re.search(r'INTENT:\s*(jira|confluence|general)', content, re.IGNORECASE)
            reason_match = re.search(r'REASON:\s*(.+)', content, re.IGNORECASE)
            
            if intent_match:
                detected_intent = intent_match.group(1).lower()
                reason = reason_match.group(1).strip() if reason_match else "LLM detected intent"
                
                # Check if detected intent matches recommended action
                should_search = (
                    (detected_intent == 'jira' and 'jira' in recommended_action) or
                    (detected_intent == 'confluence' and 'confluence' in recommended_action)
                )
                
                return {
                    'should_search': should_search,
                    'detected_intent': detected_intent,
                    'reason': reason
                }
            
            return {'should_search': False, 'reason': 'Could not parse LLM response'}
            
        except Exception as e:
            logger.error(f"Error verifying intent: {e}")
            return {'should_search': False, 'reason': f'Error: {str(e)}'}
    
    def _should_search_jira(self, message: str) -> bool:
        """Determine if the message requires a Jira search"""
        message_lower = message.lower()
        
        # First check if this is a meta-conversation about the assistant's response
        meta_phrases = ['you said', 'you mentioned', 'explain yourself', 'what do you mean', 
                       'i only see', 'that doesn\'t make sense', 'you\'re wrong', 'incorrect',
                       'why did you say', 'can you clarify', 'what are you talking about']
        if any(phrase in message_lower for phrase in meta_phrases):
            logger.info("💬 Detected meta-conversation (not a Jira query)")
            return False
        
        keywords = ['jira', 'issue', 'ticket', 'issues', 'project', 'sprint', 'epic', 'story', 'bug', 'task', 
                    'show me', 'find', 'search', 'list', 'get', 'details', 'status', 'information', 'about',
                    'assigned', 'open', 'closed', 'blocked', 'blocker', 'child', 'parent', 'subtask', 'children']
        
        # Check for keywords
        if any(keyword in message_lower for keyword in keywords):
            return True
        
        # Check if there's a Jira issue key (e.g., PROJ-123, LIFEOPS-7)
        if self._extract_issue_key(message):
            return True
        
        return False
    
    def _is_asking_for_children(self, message: str) -> bool:
        """Check if user is asking for child/subtask issues. Delegates to QueryAnalyzerService."""
        return self.query_analyzer.is_asking_for_children(message)
    
    def _extract_issue_key(self, message: str) -> str:
        """Extract Jira issue key from message (e.g., PROJ-123). Delegates to QueryAnalyzerService."""
        return self.query_analyzer.extract_single_issue_key(message)
    
    def _build_jql_from_message(self, message: str) -> str:
        """
        Build a JQL query from natural language message.
        Delegates to JiraQueryBuilder in integrations layer.
        """
        return self.query_builder.build_jql_from_keywords(message)
    
    async def _intelligent_jira_search(self, message: str) -> str:
        """Use LLM to build intelligent JQL and try multiple search strategies. Tries MCP first, falls back to direct API."""
        try:
            # Use LLM to understand intent and build JQL
            prompt = f"""Analyze this user request and create Jira JQL queries.

User Request: "{message}"

Create 2 JQL queries:
1. PRIMARY - Specific query matching the request
2. FALLBACK - Broader query to catch more results

CRITICAL JQL RULES:
- ALWAYS quote multi-word status values: "To Do", "In Progress" (NOT To Do, In Progress)
- Use text~ for searching: text~"keyword"
- For "latest", "recent", "last updated": use ORDER BY updated DESC or updated >= -7d
- For time-based queries: updated >= -1d (last day), updated >= -7d (last week)
- Status values: "To Do", "In Progress", Done, Closed, Open
- Types: Epic, Story, Task, Bug
- When user asks for "latest" or "recent", sort by updated DESC and limit results

Format (respond in exactly this format):
PRIMARY: <jql query here>
FALLBACK: <jql query here>

Examples:
Request: "latest task updated"
PRIMARY: type=Task ORDER BY updated DESC
FALLBACK: ORDER BY updated DESC

Request: "show me recent changes"
PRIMARY: updated >= -7d ORDER BY updated DESC
FALLBACK: updated >= -30d ORDER BY updated DESC

Request: "philosophy books to read"
PRIMARY: text~"philosophy" AND text~"book" AND status="To Do"
FALLBACK: text~"philosophy" AND text~"book"

Request: "show me open bugs"
PRIMARY: type=Bug AND status in (Open, "To Do", "In Progress")
FALLBACK: type=Bug

Request: "tasks in progress"
PRIMARY: type=Task AND status="In Progress"
FALLBACK: status="In Progress"

IMPORTANT: Output ONLY the two JQL queries, nothing else. No explanations.

Now create JQL for: "{message}"
PRIMARY:
FALLBACK:
"""

            response = self.llm.invoke(prompt)
            llm_output = response.content.strip()
            logger.info(f"🧠 LLM response:\n{llm_output}")
            
            # Parse PRIMARY and FALLBACK queries - extract JQL after the labels
            primary_match = re.search(r'PRIMARY:\s*(.+?)(?=\n\s*FALLBACK:|\Z)', llm_output, re.IGNORECASE | re.DOTALL)
            fallback_match = re.search(r'FALLBACK:\s*(.+?)$', llm_output, re.IGNORECASE | re.DOTALL)
            
            primary_jql = primary_match.group(1).strip() if primary_match else None
            fallback_jql = fallback_match.group(1).strip() if fallback_match else None
            
            # Clean up JQL - remove markdown, quotes, extra whitespace, trailing periods, newlines
            def clean_jql(jql: str) -> str:
                if not jql:
                    return None
                # Remove markdown and backticks
                jql = re.sub(r'\*\*|\*|`', '', jql)
                # Take only first line if multiline
                jql = jql.split('\n')[0].strip()
                # Remove leading/trailing special chars
                jql = jql.strip('"\'` \n.;*')
                # Basic validation - must contain valid JQL operators
                valid_operators = ['=', '~', 'AND', 'OR', 'IN', 'NOT', 'ORDER']
                if not any(op in jql.upper() for op in valid_operators):
                    logger.warning(f"❌ Invalid JQL (no operators found): {jql}")
                    return None
                # Ensure quotes are balanced
                if jql.count('"') % 2 != 0:
                    jql += '"'
                    logger.warning(f"⚠️ Balanced uneven quotes in JQL")
                return jql
            
            primary_jql = clean_jql(primary_jql)
            fallback_jql = clean_jql(fallback_jql)
            
            logger.info(f"🧠 LLM-generated PRIMARY JQL: {primary_jql}")
            logger.info(f"🧠 LLM-generated FALLBACK JQL: {fallback_jql}")
            
            # If LLM failed to generate queries, use basic extraction
            if not primary_jql and not fallback_jql:
                logger.warning("⚠️ LLM failed to generate JQL, using keyword extraction")
                return await self._search_jira_issues(self._build_jql_from_message(message))
            
            # Try primary query first
            if primary_jql:
                try:
                    # Try MCP first, fall back to direct API
                    results = await self._search_jira_via_mcp(primary_jql, max_results=20)
                    if results is None:
                        results = jira_service.search_issues(primary_jql, max_results=20)
                    if results and len(results) > 0:
                        logger.info(f"✅ Primary query found {len(results)} results")
                        # Add to knowledge graph
                        for issue in results:
                            knowledge_graph_service.add_jira_issue(issue)
                        return json.dumps(results, indent=2)
                except Exception as jql_error:
                    logger.warning(f"⚠️ Primary JQL failed: {jql_error}")
            
            # Try fallback if primary didn't return results or failed
            if fallback_jql:
                try:
                    logger.info(f"🔄 Trying fallback query...")
                    # Try MCP first, fall back to direct API
                    results = await self._search_jira_via_mcp(fallback_jql, max_results=20)
                    if results is None:
                        results = jira_service.search_issues(fallback_jql, max_results=20)
                    if results and len(results) > 0:
                        logger.info(f"✅ Fallback query found {len(results)} results")
                        for issue in results:
                            knowledge_graph_service.add_jira_issue(issue)
                        return json.dumps(results, indent=2)
                except Exception as jql_error:
                    logger.warning(f"⚠️ Fallback JQL failed: {jql_error}")
            
            # Last resort - use basic keyword search
            logger.info("🔄 Both LLM queries failed or returned no results, using basic keyword search")
            return await self._search_jira_issues(self._build_jql_from_message(message))
            
        except Exception as e:
            logger.error(f"Error in intelligent search: {e}", exc_info=True)
            # Fallback to basic search
            jql = self._build_jql_from_message(message)
            logger.info(f"⚠️ Falling back to basic JQL: {jql}")
            return await self._search_jira_issues(jql)
    
    def _is_ambiguous_query(self, message: str) -> bool:
        """
        Determine if a query is ambiguous and could benefit from multi-source search.
        Returns True if the query doesn't clearly indicate a single source.
        """
        message_lower = message.lower()
        
        # Queries that explicitly mention Jira or issue keys
        jira_indicators = ['jira', 'issue', 'epic', 'story', 'task', 'bug', 'sprint', 'backlog']
        has_jira_key = bool(re.search(r'\b[A-Z]+-\d+\b', message))
        
        # Queries that explicitly mention Confluence
        confluence_indicators = ['confluence', 'document', 'page', 'wiki', 'documentation']
        
        # Count indicators
        jira_score = sum(1 for word in jira_indicators if word in message_lower)
        confluence_score = sum(1 for word in confluence_indicators if word in message_lower)
        
        # If has Jira key, it's clearly Jira
        if has_jira_key:
            return False
        
        # If one source is clearly dominant (score >= 2 and other is 0), not ambiguous
        if jira_score >= 2 and confluence_score == 0:
            return False
        if confluence_score >= 2 and jira_score == 0:
            return False
        
        # Otherwise, it's ambiguous - search all sources
        return True
    
    def _should_use_agentic_search(self, message: str, query_analysis: Optional[Dict] = None) -> bool:
        """
        Determine if a query is complex enough to benefit from agentic search
        (Plan → Execute → Reflect → Adapt loop with thinking stream).
        
        Complex queries that benefit from agentic search:
        - Multi-step reasoning (find X, then based on that, find Y)
        - Comparisons across sources
        - Investigation/research type questions
        - Queries with conditional logic or dependencies
        - Questions requiring synthesis from multiple pieces of information
        """
        message_lower = message.lower()
        
        # Direct simple queries - don't need agentic
        has_jira_key = bool(re.search(r'\b[A-Z]+-\d+\b', message))
        if has_jira_key and len(message.split()) < 10:
            return False
        
        # Multi-step reasoning indicators
        multi_step_patterns = [
            r'\b(and then|after that|based on|using that|with that|from there)\b',
            r'\b(first.*then|find.*and.*also|get.*and.*compare)\b',
            r'\b(how does.*relate to|connection between|relationship between)\b',
            r'\b(investigate|research|analyze|deep dive|look into)\b',
            r'\b(compare|contrast|difference between|similarities)\b',
            r'\b(why.*and.*how|what.*and.*why|who.*and.*what)\b',
            r'\b(all.*related|everything about|comprehensive|full picture)\b',
        ]
        
        for pattern in multi_step_patterns:
            if re.search(pattern, message_lower):
                logger.info(f"🧠 Query matches agentic pattern: {pattern}")
                return True
        
        # Query analysis complexity
        if query_analysis:
            # Complex intent types benefit from agentic search
            complex_intents = ['investigation', 'analysis', 'comparison', 'research', 'comprehensive']
            intent = query_analysis.get('intent', '').lower()
            if any(ci in intent for ci in complex_intents):
                return True
            
            # Multiple entities to track
            entities = query_analysis.get('entities', [])
            if len(entities) >= 3:
                return True
            
            # Low confidence means we need to explore
            confidence = query_analysis.get('confidence', 1.0)
            if confidence < 0.6:
                return True
        
        # Long queries often need multi-step reasoning
        word_count = len(message.split())
        if word_count > 25:
            return True
        
        return False
    
    def _verify_and_filter_results(self, user_query: str, jira_results: str, skip_verification: bool = False) -> str:
        """
        Verify that search results actually match user's intent and filter out irrelevant items.
        Delegates to ResultVerifier.
        
        Args:
            user_query: Original user question
            jira_results: JSON string of Jira issues found
            skip_verification: If True, skip verification (e.g., for child issues which are inherently relevant)
            
        Returns:
            Filtered JSON string containing only relevant results
        """
        return self.result_verifier.verify_json_string(user_query, jira_results, skip_verification=skip_verification)
    
    # Search methods - delegated to search_orchestrator
    async def _search_jira_issues(self, query: str) -> str:
        """Delegate to SearchOrchestrator"""
        return await self.search_orchestrator.search_jira_issues(query)
    
    async def _get_jira_issue(self, issue_key: str) -> str:
        """Delegate to SearchOrchestrator"""
        return await self.search_orchestrator.get_jira_issue(issue_key)
    
    def _search_confluence(self, query: str) -> str:
        """Delegate to SearchOrchestrator"""
        return self.search_orchestrator.search_confluence(query)
    
    def _get_confluence_page(self, page_id: str) -> str:
        """Delegate to SearchOrchestrator"""
        return self.search_orchestrator.get_confluence_page(page_id)
    
    async def _should_supplement_with_web(self, user_query: str, jira_results: List[Dict]) -> Dict[str, Any]:
        """Delegate to SearchOrchestrator"""
        return await self.search_orchestrator.should_supplement_with_web(user_query, jira_results)
    
    async def _search_web(self, query: str) -> str:
        """Delegate to SearchOrchestrator"""
        return await self.search_orchestrator.search_web(query)
    
    async def _agentic_search(self, user_query: str, context: str = "", session_id: str = None) -> Dict[str, Any]:
        """Delegate to SearchOrchestrator"""
        return await self.search_orchestrator.agentic_search(
            user_query, context, session_id, 
            extract_issue_key_fn=self._extract_issue_key
        )
    
    async def _execute_agentic_step(self, step: Dict[str, Any], user_query: str) -> Any:
        """Delegate to SearchOrchestrator"""
        return await self.search_orchestrator._execute_agentic_step(
            step, user_query,
            extract_issue_key_fn=self._extract_issue_key
        )
    
    async def _parallel_multi_source_search(self, query: str) -> Dict[str, any]:
        """Delegate to SearchOrchestrator"""
        return await self.search_orchestrator.parallel_multi_source_search(query)
    
    # Knowledge Graph methods - delegated to kg_query_service
    def _search_knowledge_graph_direct(self, query: str) -> str:
        """Delegate to KGQueryService"""
        return self.kg_query_service.search_knowledge_graph_direct(query)
    
    def _analyze_delivery_metrics(self, project_key: str) -> str:
        """Delegate to KGQueryService"""
        return self.kg_query_service.analyze_delivery_metrics(project_key)
    
    def _get_knowledge_graph_context(self, query: str) -> str:
        """Delegate to KGQueryService"""
        return self.kg_query_service.get_knowledge_graph_context(query)
    
    def _get_kg_context_for_query(self, query: str, entity_type_filter: Optional[str] = None) -> str:
        """Delegate to KGQueryService"""
        return self.kg_query_service.get_kg_context_for_query(query, entity_type_filter)
    
    async def chat(self, message: str, session_id: str, conversation_history: List = None, recommended_action: str = None, context_modes: List[str] = None) -> str:
        """Process a chat message and return response with intelligent tool routing and conversation memory
        
        Args:
            message: User message
            session_id: Session identifier
            conversation_history: Previous conversation messages
            recommended_action: Optional RL-recommended action to bias tool selection
            context_modes: Optional list of context modes from frontend (e.g., ['jira', 'confluence', 'web']). If None or empty, auto-detect is used
        """
        try:
            logger.info(f"📨 Processing message: {message[:100]}...")
            logger.info(f"🎯 SKILL ENHANCEMENT enabled (always-on)")
            if recommended_action:
                logger.info(f"🧠 RL recommends action: {recommended_action}")
            if context_modes:
                logger.info(f"🎯 Context modes from frontend: {context_modes}")
            
            # ...existing code...
            # Always define message_lower and recent_issue_key at the top
            message_lower = message.lower()
            recent_issue_key = None
            if conversation_history and len(conversation_history) > 0:
                for msg in reversed(conversation_history[-3:]):
                    if hasattr(msg, 'role') and msg.role == "assistant":
                        match = re.search(r'\b([A-Z]{2,10}-\d+)\b', msg.content)
                        if match:
                            recent_issue_key = match.group(1)
                            logger.info(f"📌 Found recent issue in conversation: {recent_issue_key}")
                            break
            
            # Build conversation context from history (last 10 messages)
            context = ""
            if conversation_history and len(conversation_history) > 1:
                recent_history = conversation_history[-10:]  # Last 10 messages
                context = "\n\nConversation History:\n"
                for msg in recent_history:
                    context += f"{msg.role.capitalize()}: {msg.content[:200]}\n"
                logger.info(f"💭 Including {len(recent_history)} previous messages for context")
            
            # Respect user's explicit context mode selection first, then fallback to auto-detection
            # If user explicitly selected context modes, ONLY use those (don't override)
            if context_modes and len(context_modes) > 0:
                logger.info(f"👤 User explicitly selected context modes: {context_modes}")
                should_use_jira = 'jira' in context_modes
                should_use_confluence = 'confluence' in context_modes
                should_use_web = 'web' in context_modes
            else:
                # Auto-detect based on keywords, RL recommendation, etc.
                logger.info("🤖 Auto-detecting context mode from message content")
                
                # Check if this is a relationship query (needs both Jira + KG)
                is_relationship_query = any(phrase in message.lower() for phrase in [
                    'link between', 'relationship between', 'connection between',
                    'related to', 'connects', 'linked to', 'associated with',
                    'delivered by', 'delivers', 'blocks', 'blocked by', 'depends on'
                ])
                
                should_use_jira = (
                    (recommended_action in ["search_jira", "get_jira_issue", "get_child_issues"]) or 
                    self._should_search_jira(message) or
                    is_relationship_query  # Relationship queries need Jira data
                )
                
                should_use_confluence = (
                    recommended_action in ["search_confluence", "get_confluence_page"] or
                    any(word in message.lower() for word in ['confluence', 'documentation', 'docs', 'wiki', 'guide']) or
                    (is_relationship_query and not should_use_jira)  # Check Confluence too if not obvious Jira query
                )
                
                # Check for web search intent
                should_use_web = any(phrase in message.lower() for phrase in [
                    'search web', 'search the web', 'google', 'look up online', 
                    'find online', 'web search', 'search for', 'what is', 'who is',
                    'weather', 'news', 'latest', 'current events', 'when is', 'where is',
                    'competition', 'event', 'tournament', 'championship'
                ])
            
            # If RL recommended an action but keywords don't match, use LLM to verify intent
            # Only do this in auto-detect mode (not when user explicitly selected context)
            if not context_modes and not should_use_jira and not should_use_confluence and recommended_action:
                logger.info(f"🤔 RL recommended {recommended_action} but keywords don't match. Using LLM to verify intent...")
                intent_check = self._verify_search_intent(message, recommended_action)
                if intent_check['should_search']:
                    if 'jira' in recommended_action:
                        should_use_jira = True
                        logger.info(f"✅ LLM confirmed Jira intent: {intent_check['reason']}")
                    elif 'confluence' in recommended_action:
                        should_use_confluence = True
                        logger.info(f"✅ LLM confirmed Confluence intent: {intent_check['reason']}")
            
            # Check if we should search Jira
            if should_use_jira:
                logger.info("🎯 Detected Jira query - routing to Jira service")
                is_child_issue_query = False  # Track if this is a child issue query to skip verification
                
                # SKILL ENHANCEMENT: Analyze query (always enabled)
                logger.info("🎯 [SKILL] Analyzing query before search...")
                query_analysis = await self.skill_middleware.analyze_query(message, conversation_history)
                logger.info(f"✅ [SKILL] Query intent: {query_analysis.get('intent')}, confidence: {query_analysis.get('confidence')}")
                
                # PRIORITY ORDER for query handling:
                # 1. Child issues query (most specific)
                # 2. Specific issue key in message
                # 3. Follow-up about recent issue (but NOT if asking for child issues)
                # 4. Follow-up about status groups
                # 5. Agentic/parallel search
                
                # FIRST: Check if asking for child issues (highest priority)
                if self._is_asking_for_children(message):
                    is_child_issue_query = True
                    issue_key = self._extract_issue_key(message)
                    logger.info(f"👶 Detected child issue query, explicit key: {issue_key}")
                    
                    # If no explicit key, try to find the parent from message content or conversation
                    if not issue_key:
                        # Try to extract the parent issue name from the message itself
                        # e.g., "child issues of read 12 books in 2025"
                        match = re.search(r'child issues? (?:of|for)\s+["\']?([^"\'?,]+)["\']?', message, re.IGNORECASE)
                        if match:
                            search_terms = match.group(1).strip()
                            logger.info(f"🔍 Searching for parent issue by name: {search_terms}")
                            jql = f'summary ~ "{search_terms}"'
                            try:
                                search_results = jira_service.search_issues(jql, max_results=1)
                                if search_results:
                                    issue_key = search_results[0].get('key')
                                    logger.info(f"✅ Found parent issue: {issue_key}")
                            except Exception as e:
                                logger.warning(f"Search for parent failed: {e}")
                        
                        # If still no key, look in conversation history
                        if not issue_key and conversation_history:
                            found_keys = []
                            for msg in reversed(conversation_history[-5:]):
                                if msg.role == "assistant":
                                    keys = re.findall(r'\b([A-Z]+-\d+)\b', msg.content)
                                    found_keys.extend(keys)
                            found_keys = list(dict.fromkeys(found_keys))
                            if found_keys:
                                issue_key = found_keys[0]
                                logger.info(f"📌 Using first issue key from history: {issue_key}")
                    
                    if issue_key:
                        logger.info(f"👶 Fetching child issues and status summary for: {issue_key}")
                        child_issues, status_counts, in_progress_names = jira_service.get_child_issues_with_status_summary(issue_key)
                        if child_issues:
                            # Add to knowledge graph
                            for child in child_issues:
                                knowledge_graph_service.add_jira_issue(child)
                                knowledge_graph_service.add_relationship(
                                    child.get('key'), issue_key, "child_of",
                                    properties={"relationship": "parent-child"}
                                )
                            jira_result = json.dumps(child_issues, indent=2)
                            # Build context for LLM
                            context += f"\n\nChild Issue Analysis for {issue_key}:\n"
                            context += f"Total: {len(child_issues)}\n"
                            context += f"Done: {status_counts['Done']}\n"
                            context += f"In Progress: {status_counts['In Progress']}\n"
                            context += f"To Do: {status_counts['To Do']}\n"
                            if in_progress_names:
                                context += f"In Progress items:\n" + "\n".join(f"  - {name}" for name in in_progress_names)
                            # Generate response with full context
                            prompt = f"""User asked: {message}
{context}

Child issues data:
{jira_result}

The user is asking about child issues of {issue_key}. Based on the data above, provide:
1. A summary of the status distribution (how many Done, In Progress, To Do)
2. List the names of issues that are "In Progress" (if user asked for them)
3. Any relevant observations about the work items

Use markdown formatting. Include issue keys in backticks like `ACTHUB-123`.
Be conversational but accurate - base your response ONLY on the actual data provided."""
                            response = self.llm.invoke(prompt)
                            return response.content
                        else:
                            return f"No child issues found for {issue_key}. This issue may not have any subtasks."
                    else:
                        return "I couldn't find the parent issue. Please provide the issue key (e.g., ACTHUB-9) or the exact issue name."
                
                # SECOND: Check for specific issue key in message
                elif self._extract_issue_key(message):
                    issue_key = self._extract_issue_key(message)
                    logger.info(f"📋 Fetching specific issue: {issue_key}")
                    jira_result = await self._get_jira_issue(issue_key)
                    
                    # Generate response
                    prompt = f"""User asked: {message}
{context}
Jira issue details:
{jira_result}

Provide detailed information about this issue including status, assignee, and key details.
Be conversational and use markdown formatting."""
                    
                    response = self.llm.invoke(prompt)
                    return response.content
                
                # THIRD: Check if asking for more info about a recent issue
                # BUT exclude if user is asking about child issues (already handled above)
                is_asking_about_recent = False
                if recent_issue_key and not self._is_asking_for_children(message):
                    # More restrictive phrases - must be specifically about "this/that issue"
                    if any(phrase in message_lower for phrase in [
                        'this issue', 'that issue', 'about it', 
                        'more information', 'more info', 'more details',
                        'what is it', 'what\'s it'
                    ]):
                        is_asking_about_recent = True
                        logger.info(f"💬 User asking for more info about recent issue: {recent_issue_key}")
                
                if is_asking_about_recent and recent_issue_key:
                    logger.info(f"📋 Fetching details for recent issue: {recent_issue_key}")
                    jira_result = await self._get_jira_issue(recent_issue_key)
                    
                    # Skip to synthesis (no need for verification/ranking/KG - single issue fetch)
                    prompt = f"""User asked: {message}
{context}
Jira issue details:
{jira_result}

The user is asking for more information about this specific issue from our previous conversation.

Provide detailed information about:
- What the issue is about
- Current status
- Key details (assignee, priority, dates)
- Description and any important notes

Be conversational and focus on what the user asked for."""
                    
                    response = self.llm.invoke(prompt)
                    return response.content
                
                # FIRST: Check if this is a follow-up question about previous results
                # Look for status-based references (e.g., "the in progress", "the to do", "the done")
                is_followup = False
                target_keys = []
                
                if conversation_history and any(phrase in message_lower for phrase in ['in progress', 'to do', 'done', 'the ']):
                    logger.info("🤔 Analyzing if this is a follow-up question about previous results...")
                    
                    # Extract all issue keys from recent conversation
                    found_keys = []
                    for msg in reversed(conversation_history[-5:]):
                        if msg.role == "assistant":
                            keys = re.findall(r'\b([A-Z]+-\d+)\b', msg.content)
                            found_keys.extend(keys)
                    
                    found_keys = list(dict.fromkeys(found_keys))  # Remove duplicates
                    
                    if found_keys:
                        # Check if user is referencing a specific status group
                        if 'in progress' in message_lower:
                            # Find keys mentioned IN THE "In Progress" SECTION ONLY (not Done/To Do sections)
                            for msg in reversed(conversation_history[-5:]):
                                if msg.role == "assistant" and "In Progress" in msg.content:
                                    # Split content by status sections to isolate In Progress items
                                    content = msg.content
                                    # Find In Progress section boundaries
                                    in_progress_start = content.find("In Progress")
                                    if in_progress_start != -1:
                                        # Find next section (To Do or Done) to determine boundary
                                        next_section = float('inf')
                                        for section in ["To Do", "Done", "## To Do", "## Done", "**To Do**", "**Done**"]:
                                            pos = content.find(section, in_progress_start + 11)  # +11 to skip "In Progress" itself
                                            if pos != -1 and pos < next_section:
                                                next_section = pos
                                        
                                        # Extract In Progress section only
                                        in_progress_section = content[in_progress_start:next_section if next_section != float('inf') else len(content)]
                                        
                                        # Find keys ONLY in this section
                                        for key in found_keys:
                                            if key in in_progress_section and key not in target_keys:
                                                target_keys.append(key)
                                                logger.info(f"📌 Found {key} in In Progress section")
                            
                            if target_keys:
                                is_followup = True
                                logger.info(f"✅ Recognized follow-up about In Progress items: {target_keys}")
                        
                        elif 'to do' in message_lower or 'todo' in message_lower:
                            # Find keys mentioned IN THE "To Do" SECTION ONLY
                            for msg in reversed(conversation_history[-5:]):
                                if msg.role == "assistant" and "To Do" in msg.content:
                                    content = msg.content
                                    to_do_start = content.find("To Do")
                                    if to_do_start != -1:
                                        # Find next section boundary
                                        next_section = float('inf')
                                        for section in ["In Progress", "Done", "## In Progress", "## Done", "**In Progress**", "**Done**"]:
                                            pos = content.find(section, to_do_start + 5)
                                            if pos != -1 and pos < next_section:
                                                next_section = pos
                                        
                                        to_do_section = content[to_do_start:next_section if next_section != float('inf') else len(content)]
                                        
                                        for key in found_keys:
                                            if key in to_do_section and key not in target_keys:
                                                target_keys.append(key)
                                                logger.info(f"📌 Found {key} in To Do section")
                            
                            if target_keys:
                                is_followup = True
                                logger.info(f"✅ Recognized follow-up about To Do items: {target_keys}")
                        
                        elif 'done' in message_lower:
                            # Find keys mentioned IN THE "Done" SECTION ONLY
                            for msg in reversed(conversation_history[-5:]):
                                if msg.role == "assistant" and "Done" in msg.content:
                                    content = msg.content
                                    done_start = content.find("Done")
                                    if done_start != -1:
                                        # Find next section boundary
                                        next_section = float('inf')
                                        for section in ["In Progress", "To Do", "## In Progress", "## To Do", "**In Progress**", "**To Do**"]:
                                            pos = content.find(section, done_start + 4)
                                            if pos != -1 and pos < next_section:
                                                next_section = pos
                                        
                                        done_section = content[done_start:next_section if next_section != float('inf') else len(content)]
                                        
                                        for key in found_keys:
                                            if key in done_section and key not in target_keys:
                                                target_keys.append(key)
                                                logger.info(f"📌 Found {key} in Done section")
                            
                            if target_keys:
                                is_followup = True
                                logger.info(f"✅ Recognized follow-up about Done items: {target_keys}")
                
                # Handle follow-up questions about specific issues
                if is_followup and target_keys:
                    if self._is_asking_for_children(message):
                        # Asking for child issues of the referenced items
                        logger.info(f"👶 Getting child issues for {len(target_keys)} items")
                        issue_key = target_keys
                    else:
                        # Asking for more details about the referenced items
                        logger.info(f"📋 Getting details for {len(target_keys)} items")
                        if len(target_keys) == 1:
                            jira_result = await self._get_jira_issue(target_keys[0])
                        else:
                            # Get multiple issues
                            issues_data = []
                            for key in target_keys:
                                issue_data = jira_service.get_issue(key)
                                if issue_data:
                                    issues_data.append(issue_data)
                                    knowledge_graph_service.add_jira_issue(issue_data)
                            jira_result = json.dumps(issues_data, indent=2)
                        
                        logger.info(f"✅ Jira query completed, formatting response...")
                        
                        prompt = f"""User asked: {message}
{context}
Jira data retrieved:
{jira_result}

IMPORTANT: Base your response ONLY on the actual data provided. Do NOT make assumptions or create fictional narratives.

RESPONSE GUIDELINES:
- Describe what's ACTUALLY in the data - use the real summaries, statuses, and details from the Jira issues
- Be conversational but factual - let the data tell its own story
- Always include issue keys in code format (`ACTHUB-123`) for follow-up questions
- Use markdown for clarity: headers, bold, lists, tables
- Provide observations about patterns you see in the ACTUAL data
- Do NOT invent context or themes that aren't explicitly present

Provide a clear, engaging response that accurately represents the data."""
                        
                        response = self.llm.invoke(prompt)
                        return response.content
                
                # SECOND: Check if asking for child issues
                elif self._is_asking_for_children(message):
                    is_child_issue_query = True  # Mark as child issue query
                    issue_key = self._extract_issue_key(message)
                    
                    # If no explicit key, try to find it from the message or conversation
                    if not issue_key:
                        # Look for ALL issue keys mentioned in recent conversation
                        found_keys = []
                        if conversation_history:
                            logger.info(f"🔍 Searching {len(conversation_history)} messages for issue keys...")
                            for msg in reversed(conversation_history[-5:]):
                                if msg.role == "assistant":
                                    logger.info(f"📝 Checking assistant message: {msg.content[:100]}...")
                                    # Extract ALL issue keys from assistant's response
                                    keys = re.findall(r'\b([A-Z]+-\d+)\b', msg.content)
                                    if keys:
                                        found_keys.extend(keys)
                                        logger.info(f"📌 Found issue keys from history: {keys}")
                        
                        # Remove duplicates while preserving order
                        found_keys = list(dict.fromkeys(found_keys))
                        logger.info(f"🎯 Total unique keys found: {found_keys}")
                        
                        # If we found keys and user is asking about specific ones (e.g., "the to do")
                        if found_keys:
                            # Check if user is asking about a subset based on status
                            message_lower = message.lower()
                            if 'to do' in message_lower or 'todo' in message_lower:
                                # User wants to know about To Do status items mentioned earlier
                                # Extract To Do items from conversation by looking for "To Do" status mentions
                                to_do_keys = []
                                if conversation_history:
                                    for msg in reversed(conversation_history[-5:]):
                                        if msg.role == "assistant" and "To Do" in msg.content:
                                            # Look for pattern like "(ACTHUB-107)" near "To Do"
                                            content = msg.content
                                            # Find all issue keys that appear near "To Do" status
                                            for key in found_keys:
                                                if key in content:
                                                    # Check if this key is mentioned in To Do context
                                                    key_pos = content.find(key)
                                                    # Look 100 chars before and after for "To Do"
                                                    context_window = content[max(0, key_pos-100):key_pos+100]
                                                    if "To Do" in context_window and key not in to_do_keys:
                                                        to_do_keys.append(key)
                                
                                if to_do_keys:
                                    logger.info(f"🎯 Found {len(to_do_keys)} To Do items from history: {to_do_keys}")
                                    # Check all To Do items for child issues
                                    issue_key = to_do_keys  # Pass list for batch checking
                                else:
                                    logger.info(f"🎯 User asking about To Do items, using first key: {found_keys[0]}")
                                    issue_key = found_keys[0]
                            else:
                                # Use first found key
                                issue_key = found_keys[0]
                                logger.info(f"📌 Using first issue key from history: {issue_key}")
                        
                        # If still no key, try searching by the Epic/issue name in the message
                        if not issue_key:
                            # Extract potential Epic name from message (everything before status questions)
                            # Try to extract issue name before status/count questions
                            match = re.search(r'child issues? (?:of|for) ([^,?]+)', message, re.IGNORECASE)
                            if match:
                                search_terms = match.group(1).strip()
                            else:
                                # Fallback: take everything after "child issues" until first comma/question
                                search_terms = message.lower()
                                for word in ['child issues', 'children of', 'subtasks of', 'tell me about']:
                                    if word in search_terms:
                                        search_terms = search_terms.split(word)[-1]
                                        break
                                # Take only until first comma or question mark
                                search_terms = re.split(r'[,?]', search_terms)[0].strip()
                            
                            if search_terms and len(search_terms) > 3:
                                logger.info(f"🔍 Searching for Epic/issue by name: {search_terms}")
                                # Try to find the issue by searching
                                jql = f'summary ~ "{search_terms}" OR text ~ "{search_terms}"'
                                search_results = jira_service.search_issues(jql, max_results=1)
                                if search_results:
                                    issue_key = search_results[0].get('key')
                                    logger.info(f"✅ Found issue: {issue_key}")
                    
                    if issue_key:
                        # Handle both single key (string) and multiple keys (list)
                        if isinstance(issue_key, list):
                            logger.info(f"👶 Fetching child issues for {len(issue_key)} issues: {issue_key}")
                            # Get child issues for all keys
                            child_issues = []
                            parent_info = []
                            for parent_key in issue_key:
                                children = jira_service.get_child_issues(parent_key)
                                if children:
                                    child_issues.extend(children)
                                    parent_info.append({"parent": parent_key, "child_count": len(children)})
                                else:
                                    parent_info.append({"parent": parent_key, "child_count": 0})
                            
                            # Add parent info to context
                            context += "\n\nChecked multiple parents:\n"
                            for info in parent_info:
                                context += f"  {info['parent']}: {info['child_count']} child issues\n"
                        else:
                            logger.info(f"👶 Fetching child issues for: {issue_key}")
                            child_issues = jira_service.get_child_issues(issue_key)
                        
                        if child_issues:
                            # Add ALL child issues to knowledge graph with relationships
                            logger.info(f"📊 Adding {len(child_issues)} child issues to knowledge graph")
                            for child in child_issues:
                                # Add child issue
                                knowledge_graph_service.add_jira_issue(child)
                                # Add parent-child relationship
                                knowledge_graph_service.add_relationship(
                                    child.get('key'), 
                                    issue_key, 
                                    "child_of",
                                    properties={"relationship": "parent-child"}
                                )
                            
                            # Analyze the child issues status
                            status_counts = {'To Do': 0, 'In Progress': 0, 'Done': 0}
                            in_progress_names = []
                            
                            for child in child_issues:
                                status = child.get('status', '')
                                summary = child.get('summary', '')
                                
                                if 'progress' in status.lower() or 'doing' in status.lower():
                                    status_counts['In Progress'] += 1
                                    in_progress_names.append(summary)
                                elif 'done' in status.lower() or 'closed' in status.lower() or 'resolved' in status.lower():
                                    status_counts['Done'] += 1
                                elif 'to do' in status.lower() or 'open' in status.lower() or 'backlog' in status.lower():
                                    status_counts['To Do'] += 1
                                else:
                                    # Default to To Do if unknown
                                    status_counts['To Do'] += 1
                            
                            # Build a summary response
                            jira_result = json.dumps(child_issues, indent=2)
                            
                            # Add analysis to context for better response
                            context += f"\n\nChild Issue Analysis:\n"
                            context += f"Total: {len(child_issues)}\n"
                            context += f"Done: {status_counts['Done']}\n"
                            context += f"In Progress: {status_counts['In Progress']}\n"
                            context += f"To Do: {status_counts['To Do']}\n"
                            if in_progress_names:
                                context += f"In Progress items: {', '.join(in_progress_names)}\n"
                        else:
                            jira_result = f"No child issues found for {issue_key}. This issue may not have any subtasks."
                    else:
                        jira_result = "I couldn't find the issue you're referring to. Please provide the issue key (e.g., ACTHUB-9) or search for it first."
                
                # First check for specific issue key
                elif self._extract_issue_key(message):
                    issue_key = self._extract_issue_key(message)
                    logger.info(f"📋 Fetching specific issue: {issue_key}")
                    jira_result = await self._get_jira_issue(issue_key)
                else:
                    # DECISION POINT: Agentic vs Parallel search
                    # - Agentic: For complex queries needing multi-step reasoning with reflection
                    # - Parallel: For simpler queries that just need data from multiple sources
                    
                    use_agentic_search = self._should_use_agentic_search(message, query_analysis)
                    use_parallel_search = (
                        (not context_modes or len(context_modes) == 0) or  # No explicit choice
                        (should_use_jira and should_use_confluence) or  # Multiple contexts chosen
                        self._is_ambiguous_query(message)  # Query could come from multiple sources
                    )
                    
                    # AGENTIC SEARCH: For complex queries needing planning and reflection
                    if use_agentic_search:
                        logger.info(f"🧠 Using AGENTIC search (Plan → Execute → Reflect → Adapt)...")
                        
                        # Notify UI that we're starting agentic thinking
                        logger.info("[Thinking] Analyzing query complexity and creating search plan...")
                        
                        try:
                            # Execute agentic search with real-time thinking updates
                            agentic_results = await self.search_orchestrator.agentic_search(
                                user_query=message,
                                session_id=session_id,
                                extract_issue_key_fn=self._extract_issue_key
                            )
                            
                            # Process agentic results
                            if agentic_results and agentic_results.get("results"):
                                # Compile results from all iterations
                                all_step_results = []
                                for step_result in agentic_results.get("results", []):
                                    step_data = step_result.get("results", "")
                                    if step_data and step_data != "No issue key provided":
                                        all_step_results.append({
                                            "action": step_result.get("step", {}).get("action", "unknown"),
                                            "reason": step_result.get("step", {}).get("reason", ""),
                                            "data": step_data
                                        })
                                
                                # Build comprehensive context from agentic exploration
                                sources_data = []
                                for result in all_step_results:
                                    action = result.get("action", "")
                                    data = result.get("data", "")
                                    if data:
                                        if action == "search_jira":
                                            sources_data.append(f"**Jira Results (via agentic search):**\n{data}")
                                        elif action == "search_web":
                                            sources_data.append(f"**Web Search Results:**\n{data}")
                                        elif action == "search_kg":
                                            sources_data.append(f"**Knowledge Graph Results:**\n{data}")
                                        elif action == "get_jira_issue":
                                            sources_data.append(f"**Jira Issue Details:**\n{data}")
                                        else:
                                            sources_data.append(f"**{action} Results:**\n{data}")
                                
                                # Include reasoning trace for transparency
                                reasoning = agentic_results.get("reasoning_trace", [])
                                
                                if sources_data:
                                    combined_data = "\n\n---\n\n".join(sources_data)
                                    
                                    # Synthesize with LLM, including reasoning trace
                                    prompt = f"""User asked: {message}
{context}

I performed an intelligent multi-step search with the following reasoning:
{chr(10).join(f"• {r}" for r in reasoning)}

Here are the collected results:

{combined_data}

CRITICAL RULES:
1. Use ONLY the data provided above - DO NOT add external knowledge
2. Reference the reasoning trace to explain HOW you found the answer
3. If results are from multiple iterations, synthesize them coherently
4. Be transparent about any gaps or limitations in the findings

FORMATTING:
- Use markdown (headers, lists, tables, code blocks)
- Include issue keys in backticks (`KEY-123`)
- Be conversational and explain your reasoning

Provide a comprehensive response based on the agentic exploration above."""
                                    
                                    response = self.llm.invoke(prompt)
                                    return response.content
                                else:
                                    # Agentic search completed but no useful results
                                    logger.warning("⚠️ Agentic search completed but no results found")
                                    # Fall through to parallel search as backup
                            
                        except Exception as e:
                            logger.error(f"❌ Agentic search failed: {e}")
                            logger.warning("[Thinking] Agentic search encountered an issue, falling back to parallel search...")
                            # Fall through to parallel search
                    
                    # PARALLEL SEARCH: For simpler multi-source queries
                    if use_parallel_search and not use_agentic_search:
                        logger.info(f"🔄 Using PARALLEL multi-source search...")
                        
                        # Execute parallel search across all sources
                        all_results = await self._parallel_multi_source_search(message)
                        
                        # Let LLM analyze and synthesize from all sources
                        sources_data = []
                        if all_results["jira"]:
                            sources_data.append(f"**Jira Results:**\n{all_results['jira']}")
                        if all_results["confluence"]:
                            sources_data.append(f"**Confluence Results:**\n{all_results['confluence']}")
                        if all_results["knowledge_graph"]:
                            sources_data.append(f"**Knowledge Graph Results:**\n{all_results['knowledge_graph']}")
                        
                        if not sources_data:
                            jira_result = "No results found from any source (Jira, Confluence, or Knowledge Graph)."
                        else:
                            combined_data = "\n\n---\n\n".join(sources_data)
                            
                            # Use LLM to synthesize the best answer from all sources
                            prompt = f"""User asked: {message}
{context}

I searched multiple sources in parallel and found the following:

{combined_data}

CRITICAL RULES:
1. Use ONLY the data provided above - DO NOT add external knowledge or general information
2. If no relevant results exist, say so clearly - DO NOT invent information
3. DO NOT provide Wikipedia-style overviews, external facts, or general knowledge
4. If the data doesn't answer the question, acknowledge it honestly

FORMATTING:
- Prioritize FRESH data (Jira/Confluence) over cached Knowledge Graph data
- Synthesize multiple sources into one coherent response when relevant
- Use markdown (headers, lists, tables, code blocks)
- Include issue keys in backticks (`KEY-123`)
- Be conversational but strictly factual

Provide a response based EXCLUSIVELY on the actual data provided above."""
                            
                            response = self.llm.invoke(prompt)
                            return response.content
                    
                    # FALLBACK: Single-source search (original behavior)
                    elif not use_agentic_search:
                        # SKILL ENHANCEMENT: Optimize JQL before search (always enabled)
                        if query_analysis:
                            logger.info("🔧 [SKILL] Optimizing JQL query...")
                            jql_optimization = await self.skill_middleware.optimize_jql(message, analysis=query_analysis)
                            logger.info(f"✅ [SKILL] Optimized JQL: {jql_optimization.get('primary_jql', '')[:100]}")
                        
                        # Query Jira for FRESH data (source of truth)
                        logger.info(f"🔍 Querying Jira for fresh data...")
                        jira_result = await self._intelligent_jira_search(message)
                        
                        # PARALLEL: Get Knowledge Graph context for enrichment
                        logger.info(f"🕸️ Gathering Knowledge Graph context (Jira issues only)...")
                        kg_context = self._get_kg_context_for_query(message, entity_type_filter='jira_issue')
                        if kg_context:
                            logger.info(f"✅ KG context: {kg_context[:100]}...")
                
                
                logger.info(f"✅ Jira query completed, formatting response...")
                
                # STEP 1: Verify results match user's intent (filter irrelevant results)
                # Skip verification for child issues - they are inherently relevant when explicitly requested
                if query_analysis:
                    # Use skill-enhanced ranking and verification (always enabled)
                    logger.info("📊 [SKILL] Ranking and filtering results...")
                    ranked = await self.skill_middleware.rank_results(message, jira_result, query_analysis, skip_verification=is_child_issue_query)
                    filtered_result = json.dumps(ranked.get("ranked_results", []), indent=2)
                    logger.info(f"✅ [SKILL] Ranked {len(ranked.get('ranked_results', []))} results, filtered out {ranked.get('filtered_out', 0)}")
                else:
                    # Fallback if query analysis failed
                    filtered_result = self._verify_and_filter_results(message, jira_result, skip_verification=is_child_issue_query)
                
                # Build context for LLM response with KG insights
                if 'kg_context' in locals() and kg_context:
                    context += f"\n🕸️ Knowledge Graph Insights:\n{kg_context}\n"
                    context += "Note: Use these insights to enrich your response, but base your answer on the fresh Jira data.\n"
                
                # SKILL ENHANCEMENT: Enrich with KG relationships (always enabled)
                if query_analysis:
                    logger.info("🕸️ [SKILL] Enriching results with Knowledge Graph...")
                    try:
                        parsed_results = json.loads(filtered_result) if isinstance(filtered_result, str) else filtered_result
                        enriched = await self.skill_middleware.enrich_with_kg(message, parsed_results, query_analysis)
                        filtered_result = json.dumps(enriched.get("enriched_results", parsed_results), indent=2)
                        
                        # Add global KG context
                        global_kg_context = enriched.get("global_context", {})
                        if global_kg_context.get("relevant_communities"):
                            context += f"\n🌐 Knowledge Communities: {', '.join([c['name'] for c in global_kg_context['relevant_communities'][:3]])}\n"
                        
                        logger.info(f"✅ [SKILL] Enriched {len(enriched.get('enriched_results', []))} results with KG context")
                    except Exception as e:
                        logger.error(f"❌ [SKILL] KG enrichment failed: {e}")
                
                # STEP 2: Check if we should supplement with web search for external context
                # Use LLM to intelligently decide instead of keyword matching
                should_supplement_with_web = False
                web_search_query = None
                
                try:
                    parsed_results = json.loads(filtered_result) if isinstance(filtered_result, str) else filtered_result
                    if parsed_results and len(parsed_results) > 0:
                        logger.info("🤔 Analyzing if Jira results need web context supplement...")
                        web_decision = await self._should_supplement_with_web(message, parsed_results)
                        
                        should_supplement_with_web = web_decision.get("should_search", False)
                        web_search_query = web_decision.get("search_query")
                        
                        if should_supplement_with_web and not web_search_query:
                            # Fallback: build query from user message and key terms
                            logger.info("⚠️ LLM said to search but no query provided, building fallback")
                            web_search_query = f"{message} details schedule information"
                except Exception as e:
                    logger.error(f"Error checking for web supplement: {e}")
                
                # If we should supplement with web search, do it
                web_results = None
                if should_supplement_with_web and web_search_query:
                    try:
                        logger.info(f"🌐 Supplementing Jira results with web search: {web_search_query}")
                        web_results = await self._search_web(web_search_query)
                        logger.info(f"✅ Web search returned additional context")
                    except Exception as e:
                        logger.error(f"❌ Web search supplement failed: {e}")
                
                prompt = f"""User asked: {message}
{context}
Jira data retrieved:
{filtered_result}

{f'''
Web search results (additional context about external events):
{web_results}

IMPORTANT: The Jira data shows internal work/tasks. Web results provide context about external events/competitions/venues mentioned in those tasks.
''' if web_results else ''}

IMPORTANT: Your response must be based on the actual data provided above.

RESPONSE GUIDELINES:
1. Use the REAL issue summaries, statuses, and details from the Jira data
2. If web results are provided, use them to add external context (like competition dates, locations, event details)
3. **Connect the dots**: If Jira shows "May CrossFit Prep" and web shows a gym's competition, explain the connection
4. Be conversational but accurate - describe what you actually see in the data
5. Use markdown formatting:
   - Headers (##) for sections
   - Bold (**text**) for emphasis  
   - Code backticks for issue keys (`ACTHUB-123`)
   - Tables when comparing multiple items
   - Lists for organization
6. Include issue keys for all mentioned items
7. If Jira mentions external venues/events and web has details, provide the full picture!
8. Do NOT create fictional scenarios or assume what the project is about

Example: If Jira shows "May CrossFit Prep" and web finds "L'Usine CrossFit Repentigny UR Beast Competition in May", connect them: "The task ACTHUB-255 is about preparing for the UR Beast competition at L'Usine CrossFit Repentigny, which takes place in May [details from web]."

Describe the actual data in an engaging way, connecting Jira tasks to external event details if available."""
                
                response = self.llm.invoke(prompt)
                return response.content
            
            # Check for Confluence searches
            elif should_use_confluence:
                logger.info("📚 Detected Confluence query - routing to Confluence service")
                confluence_result = self._search_confluence(message)
                
                # ALWAYS get Knowledge Graph context for enrichment - FILTERED for Confluence pages
                logger.info(f"🕸️ Gathering Knowledge Graph context (Confluence pages only)...")
                kg_context = self._get_kg_context_for_query(message, entity_type_filter='confluence_page')
                if kg_context:
                    logger.info(f"✅ KG context found: {kg_context[:100]}...")
                    context += f"\n🕸️ Knowledge Graph Insights (Confluence):\n{kg_context}\n"
                    context += "Note: Use these insights to enrich your response with additional Confluence context.\n"
                
                prompt = f"""User asked: {message}
{context}
Confluence data retrieved:
{confluence_result}

Please provide a clear, helpful response based on this Confluence data. If Knowledge Graph insights are provided above, use them to enrich your response with additional context."""
                
                response = self.llm.invoke(prompt)
                return response.content
            
            # Check for web search
            elif should_use_web:
                logger.info("🌐 Detected web search query - routing to web search")
                web_result = await self._search_web(message)
                
                # ALWAYS get Knowledge Graph context for enrichment
                logger.info(f"🕸️ Gathering Knowledge Graph context for enrichment...")
                kg_context = self._get_kg_context_for_query(message)
                if kg_context:
                    logger.info(f"✅ KG context found: {kg_context[:100]}...")
                    context += f"\n🕸️ Knowledge Graph Insights:\n{kg_context}\n"
                    context += "Note: Use these insights to enrich your response with additional context from your knowledge base.\n"
                
                prompt = f"""User asked: {message}
{context}
Web search results:
{web_result}

Please provide a clear, helpful response based on these web search results. Include source URLs when relevant. If Knowledge Graph insights are provided above, use them to add relevant context from the knowledge base."""
                
                response = self.llm.invoke(prompt)
                return response.content
            
            # General conversation
            else:
                logger.info("💬 General conversation - no tool routing needed")
                system_message = """You are an intelligent AI assistant specialized in delivery intelligence and decision support for engineering teams.

You have access to Jira (read-only) and Confluence (read-only).

When users ask about Jira issues, projects, or sprints, I will automatically search Jira for them.
When users ask about documentation, I will search Confluence.

Use the conversation history to provide contextual, relevant responses. Remember what was discussed earlier in the conversation."""

                full_prompt = f"{system_message}\n{context}\n\nUser: {message}\n\nAssistant:"
                response = self.llm.invoke(full_prompt)
                return response.content
            
        except Exception as e:
            logger.error(f"❌ Error in chat processing: {e}", exc_info=True)
            return f"I apologize, but an error occurred: {str(e)}"
    
    def _start_clarification_workflow(self, message: str, session_id: str, operation: str, context_issue_key: Optional[str] = None) -> str:
        """Start interactive clarification workflow for write operations"""
        logger.info(f"🔍 Starting clarification workflow for {operation} operation")
        
        # Extract initial information from the message
        extracted_info = self._extract_operation_details(message, operation)
        
        # If we have context from conversation, pre-fill fields
        if context_issue_key and operation == 'update':
            if 'issue_key' not in extracted_info or not extracted_info['issue_key']:
                extracted_info['issue_key'] = context_issue_key
                logger.info(f"✅ Pre-filled issue_key from context: {context_issue_key}")
            
            # Detect field to update from message
            if 'better name' in message.lower() or 'rename' in message.lower() or 'change the name' in message.lower():
                extracted_info['field'] = 'summary'
                logger.info(f"✅ Detected field from context: summary")
        
        # Define required fields based on operation type
        required_fields = self._get_required_fields(operation, extracted_info.get('issue_type'))
        
        # Identify missing fields
        missing_fields = [field for field in required_fields if field not in extracted_info or not extracted_info[field]]
        
        logger.info(f"📊 Extracted: {list(extracted_info.keys())}, Missing: {missing_fields}")
        
        # Validate project if it was extracted
        if 'project' in extracted_info and extracted_info['project']:
            validation_result = self._validate_project(extracted_info['project'])
            if validation_result['status'] == 'valid':
                # Update with validated project key
                extracted_info['project'] = validation_result['project_key']
                logger.info(f"✅ Project validated: {validation_result['project_key']}")
            elif validation_result['status'] == 'not_found':
                # Project not found - ask user to provide correct one
                logger.warning(f"⚠️ Invalid project: {extracted_info['project']}")
                # Add project to missing fields and remove the invalid value
                if 'project' not in missing_fields:
                    missing_fields.insert(0, 'project')
                extracted_info['project'] = None
                
                # Store pending operation and return validation message
                self.pending_operations[session_id] = {
                    'operation': operation,
                    'collected_info': extracted_info,
                    'missing_fields': missing_fields
                }
                return validation_result['message']
        
        # Add optional fields as a batch (only for CREATE operations)
        if operation == 'create':
            optional_fields = ['description', 'priority', 'assignee', 'labels']
            has_any_optional = any(field in extracted_info and extracted_info.get(field) for field in optional_fields)
            needs_optional = not all(field in extracted_info for field in optional_fields)
            
            if needs_optional:
                # Add a special marker to ask for all optional fields at once
                if 'optional_batch' not in missing_fields:
                    missing_fields.append('optional_batch')
        
        # If all required fields are present, continue with optional fields
        if not missing_fields:
            return self._create_approval_request(session_id, operation, extracted_info)
        
        # Store pending operation
        self.pending_operations[session_id] = {
            'operation': operation,
            'collected_info': extracted_info,
            'required_fields': required_fields,
            'missing_fields': missing_fields,
            'started_at': datetime.utcnow().isoformat()
        }
        
        # Special handling: if asking for issue_key and we have issue_search, search first
        first_field = missing_fields[0]
        if first_field == 'issue_key' and 'issue_search' in extracted_info:
            search_term = extracted_info['issue_search']
            project = extracted_info.get('project')
            logger.info(f"🔍 Auto-searching for issue: {search_term}")
            
            search_result = self._search_and_suggest_issues(search_term, project)
            if search_result['status'] == 'found':
                # Only one match - use it automatically and remove from missing
                extracted_info['issue_key'] = search_result['issue_key']
                missing_fields.pop(0)
                self.pending_operations[session_id]['missing_fields'] = missing_fields
                logger.info(f"✅ Auto-selected issue: {search_result['issue_key']}")
                
                # If no more missing fields, create approval
                if not missing_fields:
                    del self.pending_operations[session_id]
                    return self._create_approval_request(session_id, operation, extracted_info)
                # Otherwise ask for next field
                return self._ask_clarification_question(missing_fields[0], operation, extracted_info)
            elif search_result['status'] == 'suggestions':
                return search_result['message']
        
        # Ask for the first missing field
        # Check if user is asking for suggestions in their original message
        if first_field == 'value' and any(word in message.lower() for word in ['idea', 'suggest', 'recommend', 'think', 'proposal', 'suggestion']):
            result = self._generate_value_suggestions(message, operation, extracted_info)
            if isinstance(result, dict) and 'suggestions' in result:
                # Store suggestions and detected field in pending operation
                self.pending_operations[session_id]['suggestions'] = result['suggestions']
                if 'detected_field' in result:
                    # Update the field based on LLM detection
                    extracted_info['field'] = result['detected_field']
                    self.pending_operations[session_id]['collected_info']['field'] = result['detected_field']
                    logger.info(f"🧠 Updated field to: {result['detected_field']}")
                return result['message']
            else:
                return result
        
        return self._ask_clarification_question(first_field, operation, extracted_info)
    
    def _extract_operation_details(self, message: str, operation: str) -> Dict[str, Any]:
        """Delegate to JiraWriteService"""
        return self.jira_write_service.extract_operation_details(message, operation)
    
    def _get_required_fields(self, operation: str, issue_type: Optional[str] = None) -> List[str]:
        """Delegate to JiraWriteService"""
        return self.jira_write_service.get_required_fields(operation, issue_type)
    
    def _generate_value_suggestions(self, message: str, operation: str, current_info: Dict[str, Any]) -> str:
        """Delegate to ClarificationService"""
        return self.clarification_service.generate_value_suggestions(message, operation, current_info)
    
    def _ask_clarification_question(self, field: str, operation: str, current_info: Dict[str, Any]) -> str:
        """Delegate to ClarificationService"""
        return self.clarification_service.ask_clarification_question(field, operation, current_info)
    
    def _handle_clarification_response(self, message: str, session_id: str, pending_op: Dict[str, Any]) -> str:
        """Process user's response to a clarification question"""
        collected_info = pending_op['collected_info']
        missing_fields = pending_op['missing_fields']
        operation = pending_op['operation']
        
        logger.info(f"💬 Processing clarification response. missing_fields: {missing_fields}, collected: {list(collected_info.keys())}")
        
        # FIRST: Check if user is asking about a DIFFERENT issue or asking a new question
        # This should be checked BEFORE the empty missing_fields check
        
        # Check if user mentions a different issue key
        other_issue_match = re.search(r'\b([A-Z]{2,10}-\d+)\b', message)
        if other_issue_match:
            mentioned_key = other_issue_match.group(1)
            # Check if they're asking ABOUT this issue vs selecting it
            if any(word in message.lower() for word in ['what about', 'what is', "doesn't", "why not", "how about", "don't you"]):
                logger.info(f"🔀 User is asking about {mentioned_key}, searching knowledge graph")
                del self.pending_operations[session_id]
                
                # Search knowledge graph for this issue
                kg_result = knowledge_graph_service.get_entity(mentioned_key)
                
                if kg_result:
                    props = kg_result.get('properties', {})
                    summary = props.get('summary', 'No summary')
                    status = props.get('status', 'Unknown')
                    issue_type = props.get('issue_type', 'Unknown')
                    project = props.get('project', 'Unknown')
                    
                    response = f"""✅ **Yes, I found {mentioned_key} in the Knowledge Graph!**

**Summary:** {summary}
**Type:** {issue_type}
**Project:** {project}
**Status:** {status}

This issue is stored in my knowledge graph. Would you like to update it or get more details?

(Note: I've canceled the previous update operation. You can restart it anytime.)"""
                else:
                    # Not in KG, try searching Jira
                    logger.info(f"📝 {mentioned_key} not in KG, searching Jira...")
                    try:
                        jira_result = jira_service.get_issue(mentioned_key)
                        if jira_result:
                            # Add to KG for future
                            knowledge_graph_service.add_jira_issue(jira_result)
                            summary = jira_result.get('summary', 'No summary')
                            
                            response = f"""✅ **Found {mentioned_key} in Jira** (now added to Knowledge Graph)

**Summary:** {summary}
**Type:** {jira_result.get('issue_type', 'Unknown')}
**Status:** {jira_result.get('status', 'Unknown')}

This issue is now in my knowledge graph! Would you like to update it?"""
                        else:
                            response = f"❌ I couldn't find {mentioned_key} in the Knowledge Graph or Jira. It may not exist or you may not have access to it."
                    except Exception as e:
                        logger.error(f"Error fetching {mentioned_key}: {e}")
                        response = f"❌ I couldn't find {mentioned_key} in the Knowledge Graph, and got an error searching Jira: {str(e)}"
                
                return response
        
        # Check if user is asking a DIFFERENT question (not about clarification)
        new_request_indicators = [
            'show me', 'tell me about', 'give me', 'get me', 'what is', 'what are',
            'find', 'search for', 'look for', 'display', 'list', 'can you show',
            'what about', "doesn't it", "don't you", "why not"
        ]
        if any(indicator in message.lower() for indicator in new_request_indicators):
            logger.info(f"🔀 User is asking a different question, exiting clarification mode")
            del self.pending_operations[session_id]
            return f"Sure! Let me help you with that.\n\n(Note: I've canceled the {operation} operation. You can restart it anytime.)"
        
        # NOW check if missing_fields is empty
        if not missing_fields:
            logger.error(f"⚠️ missing_fields is empty! collected_info: {collected_info}")
            del self.pending_operations[session_id]
            return "⚠️ Something went wrong with the clarification workflow. Let's start over - what would you like to do?"
        
        # Get the field we're currently asking about (first in missing_fields)
        current_field = missing_fields[0]
        
        logger.info(f"💬 Processing response for field: {current_field}")
        
        # Check if user is asking about a DIFFERENT issue (mentions an issue key that's not what we're working on)
        # Example: "what about ACTHUB-322" when we're asking them to pick an issue
        other_issue_match = re.search(r'\b([A-Z]{2,10}-\d+)\b', message)
        if other_issue_match and current_field == 'issue_key':
            mentioned_key = other_issue_match.group(1)
            # Check if they're asking ABOUT this issue vs selecting it
            if any(word in message.lower() for word in ['what about', 'what is', "doesn't", "why not", "how about"]):
                logger.info(f"🔀 User is asking about {mentioned_key}, switching to info mode")
                # Clear pending operation and answer their question
                del self.pending_operations[session_id]
                # Return a response that searches for this issue
                return f"Let me look up {mentioned_key} for you...\n\n(Note: I've canceled the update operation. You can restart it anytime by saying 'modify an epic about climbing')"
        
        # Check if user is asking a DIFFERENT question (not about clarification)
        # These indicate they want to do something else entirely
        new_request_indicators = [
            'show me', 'tell me about', 'give me', 'get me', 'what is', 'what are',
            'find', 'search for', 'look for', 'display', 'list', 'can you show',
            'what about', "doesn't it", "don't you"
        ]
        if any(indicator in message.lower() for indicator in new_request_indicators):
            logger.info(f"🔀 User is asking a different question, exiting clarification mode")
            # Clear pending operation
            del self.pending_operations[session_id]
            # Return a helpful message
            return f"Sure! Let me help you with that.\n\n(Note: I've canceled the update operation. You can restart it anytime.)"
        
        # Check if user is asking a question about the current field
        question_indicators = ['?', 'what', 'how', 'why', 'should', 'can i', 'is it', "isn't it", 'do i', 'does it']
        if any(indicator in message.lower() for indicator in question_indicators):
            logger.info(f"❓ User asked a question about the field: {message}")
            return self._answer_clarification_question(message, current_field, collected_info, operation)
        
        # Check if user is selecting a numbered suggestion (1, 2, 3)
        if current_field == 'value' and message.strip() in ['1', '2', '3']:
            suggestions = pending_op.get('suggestions', [])
            if suggestions:
                selection_num = int(message.strip()) - 1  # Convert to 0-indexed
                if 0 <= selection_num < len(suggestions):
                    selected_value = suggestions[selection_num]
                    collected_info[current_field] = selected_value
                    logger.info(f"✅ User selected suggestion #{message.strip()}: {selected_value}")
                    # Clear suggestions from pending op
                    if 'suggestions' in pending_op:
                        del pending_op['suggestions']
                else:
                    return f"❌ Invalid selection. Please choose 1, 2, or 3, or provide your own value."
            else:
                # No suggestions stored, treat as regular input
                collected_info[current_field] = message.strip()
        
        # Check if user says "use it" for description suggestions
        elif current_field == 'value' and message.lower().strip() in ['use it', 'use this', 'looks good', 'perfect']:
            logger.info(f"✅ User accepted suggestion")
            return "Please copy and paste the full suggested text so I can apply it."
        
        # Check if user wants to skip optional fields
        elif message.lower().strip() in ['skip', 'no', 'none', 'empty', 'pass', 'keep current']:
            logger.info(f"⏭️ Skipping optional field: {current_field}")
            if current_field == 'optional_batch':
                # Skip all optional fields
                collected_info['description'] = None
                collected_info['priority'] = None
                collected_info['assignee'] = None
                collected_info['labels'] = None
            elif current_field == 'value':
                # User wants to keep current value - cancel operation
                del self.pending_operations[session_id]
                return "✅ Keeping the current value. Update canceled."
            else:
                collected_info[current_field] = None
        else:
            # Special handler for optional_batch
            if current_field == 'optional_batch':
                # Extract all optional fields from the message
                self._extract_optional_batch(message, collected_info)
                logger.info(f"✅ Collected optional fields from batch")
            # Special handling for issue_key - search and suggest
            elif current_field == 'issue_key':
                # First check if we have issue_search from extraction
                search_term = collected_info.get('issue_search', message)
                project = collected_info.get('project')
                
                # Search for matching issues
                search_result = self._search_and_suggest_issues(search_term, project)
                if search_result['status'] == 'found':
                    collected_info[current_field] = search_result['issue_key']
                    logger.info(f"✅ Collected {current_field}: {search_result['issue_key']}")
                elif search_result['status'] == 'suggestions':
                    # Show suggestions and wait for user to pick
                    return search_result['message']
                else:
                    return f"❌ No issues found matching '{search_term}'. Please provide the exact issue key (e.g., ACTHUB-123)."
            else:
                # Extract value from response
                value = self._extract_field_value(message, current_field)
                if value:
                    # Special validation for project field
                    if current_field == 'project':
                        validation_result = self._validate_project(value)
                        if validation_result['status'] == 'valid':
                            collected_info[current_field] = validation_result['project_key']
                            logger.info(f"✅ Collected {current_field}: {validation_result['project_key']}")
                        elif validation_result['status'] == 'not_found':
                            # Project not found, suggest similar ones
                            return validation_result['message']
                        else:
                            return f"❌ Unable to validate project. Please try again.\n\n{self._ask_clarification_question(current_field, operation, collected_info)}"
                    else:
                        collected_info[current_field] = value
                        logger.info(f"✅ Collected {current_field}: {value}")
                else:
                    return f"❌ I couldn't understand that value for {current_field.replace('_', ' ')}. Please try again.\n\n{self._ask_clarification_question(current_field, operation, collected_info)}"
        
        # Remove current field from missing list
        missing_fields.pop(0)
        pending_op['missing_fields'] = missing_fields
        
        # Check if we have all required fields now (operation-specific)
        if operation == 'create':
            truly_required = ['project', 'issue_type', 'summary']
        elif operation == 'update':
            truly_required = ['issue_key', 'field', 'value']
        else:
            truly_required = []
        
        missing_required = [f for f in truly_required if f not in collected_info or not collected_info[f]]
        
        if not missing_required:
            # All required fields collected, create approval request
            logger.info(f"✅ All required fields collected: {collected_info}")
            del self.pending_operations[session_id]
            return self._create_approval_request(session_id, operation, collected_info)
        
        # If there are still missing fields, ask next question
        if missing_fields:
            return self._ask_clarification_question(missing_fields[0], operation, collected_info)
        else:
            logger.error(f"Completed questions but missing required: {missing_required}")
            del self.pending_operations[session_id]
            return f"❌ Missing required fields: {', '.join(missing_required)}. Let's start over."
    
    def _extract_field_value(self, message: str, field: str) -> Any:
        """Delegate to ClarificationService"""
        return self.clarification_service.extract_field_value(message, field)
    
    def _create_approval_request(self, session_id: str, operation: str, details: Dict[str, Any]) -> str:
        """Delegate to JiraWriteService"""
        return self.jira_write_service.create_approval_request(session_id, operation, details)
    
    def _validate_project(self, project_key: str) -> Dict[str, Any]:
        """Delegate to JiraWriteService"""
        return self.jira_write_service.validate_project(project_key)
    
    def _search_and_suggest_issues(self, search_term: str, project: Optional[str] = None) -> Dict[str, Any]:
        """Delegate to JiraWriteService"""
        return self.jira_write_service.search_and_suggest_issues(search_term, project)
    
    def _improve_summary(self, raw_summary: str, issue_type: str) -> str:
        """Delegate to JiraWriteService"""
        return self.jira_write_service.improve_summary(raw_summary, issue_type)
    
    def _extract_optional_batch(self, message: str, collected_info: Dict[str, Any]) -> None:
        """Delegate to ClarificationService"""
        self.clarification_service.extract_optional_batch(message, collected_info)
    
    def _generate_operation_preview(self, operation: str, details: Dict[str, Any]) -> str:
        """Delegate to JiraWriteService"""
        return self.jira_write_service.generate_operation_preview(operation, details)
    
    def _answer_clarification_question(self, question: str, field: str, current_info: Dict[str, Any], operation: str) -> str:
        """Delegate to ClarificationService"""
        return self.clarification_service.answer_clarification_question(question, field, current_info, operation)


ai_agent_service = AIAgentService()

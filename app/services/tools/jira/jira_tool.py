"""
Jira Tool - Unified Jira operations implementing BaseTool interface.

This is the main entry point for all Jira operations. It:
- Implements BaseTool for consistent behavior
- Delegates to specialized services (JiraService, JiraQueryBuilder, etc.)
- Handles MCP fallback to direct API
- Encapsulates all Jira-specific logic
"""
from typing import Dict, Any, List, Optional
import logging
import json
import re

from ..base import ReadWriteTool, ToolResult, ActionSchema, ToolCapability
from .jira_intent import JiraIntentDetector
from .jira_service import jira_service
from app.services.graphrag.knowledge_graph_service import knowledge_graph_service
from app.config import settings

logger = logging.getLogger(__name__)


class JiraTool(ReadWriteTool):
    """
    Jira Tool - Search and manage Jira issues.
    
    Implements BaseTool interface for integration with AgentOrchestrator.
    Consolidates all Jira-related logic previously scattered across:
    - ai_agent_service.py
    - mcp_operations.py
    - search_orchestrator.py
    - jira_write_service.py
    """
    
    def __init__(self, llm=None, mcp_enabled: bool = None):
        """
        Initialize Jira tool.
        
        Args:
            llm: LangChain LLM for intelligent query generation
            mcp_enabled: Whether to use MCP (defaults to settings.enable_mcp)
        """
        self.llm = llm
        self.mcp_enabled = mcp_enabled if mcp_enabled is not None else settings.enable_mcp
        self.intent_detector = JiraIntentDetector()
        
        # Lazy-loaded services
        self._mcp_client = None
        self._query_builder = None
        self._write_service = None
        
        logger.info(f"JiraTool initialized (MCP: {self.mcp_enabled})")
    
    @property
    def name(self) -> str:
        return "jira"
    
    @property
    def display_name(self) -> str:
        return "Jira"
    
    @property
    def description(self) -> str:
        return (
            "Search and manage Jira issues, epics, stories, bugs, and tasks. "
            "Can search using JQL or natural language, get issue details, "
            "find child issues, and perform create/update operations."
        )
    
    @property
    def capabilities(self) -> List[ToolCapability]:
        return [
            ToolCapability.SEARCH,
            ToolCapability.READ,
            ToolCapability.WRITE,
            ToolCapability.UPDATE,
            ToolCapability.QUERY_BUILD,
        ]
    
    @property
    def keywords(self) -> List[str]:
        return [
            'jira', 'issue', 'ticket', 'epic', 'story', 'bug', 'task',
            'sprint', 'subtask', 'blocker', 'backlog', 'kanban'
        ]
    
    @property
    def query_builder(self):
        """Lazy-load query builder"""
        if self._query_builder is None:
            from .jira_query_builder import JiraQueryBuilder
            self._query_builder = JiraQueryBuilder(self.llm)
        return self._query_builder
    
    @property
    def mcp_client(self):
        """Lazy-load MCP client"""
        if self._mcp_client is None and self.mcp_enabled:
            from app.services.orchestration.mcp_operations import mcp_operations
            self._mcp_client = mcp_operations
        return self._mcp_client
    
    @property
    def write_service(self):
        """Lazy-load write service"""
        if self._write_service is None:
            from .jira_write_service import JiraWriteService
            self._write_service = JiraWriteService(self.llm)
        return self._write_service
    
    def can_handle(self, intent: str, message: str, context: Optional[Dict] = None) -> float:
        """Delegate to JiraIntentDetector"""
        return self.intent_detector.score(intent, message, context)
    
    def get_actions(self) -> Dict[str, ActionSchema]:
        """Return available Jira actions"""
        return {
            "search": ActionSchema(
                name="search",
                description="Search Jira issues using natural language or JQL",
                parameters={
                    "message": {"type": "string", "required": True, "description": "Natural language query or JQL"},
                    "jql": {"type": "string", "required": False, "description": "Direct JQL query (bypasses NL parsing)"},
                    "max_results": {"type": "integer", "required": False, "description": "Max results (default 20)"},
                },
                returns="List of matching Jira issues"
            ),
            "get_issue": ActionSchema(
                name="get_issue",
                description="Get detailed information about a specific issue",
                parameters={
                    "issue_key": {"type": "string", "required": True, "description": "Issue key (e.g., PROJ-123)"},
                },
                returns="Detailed issue information"
            ),
            "get_child_issues": ActionSchema(
                name="get_child_issues",
                description="Get child issues (subtasks) of a parent issue",
                parameters={
                    "parent_key": {"type": "string", "required": True, "description": "Parent issue key"},
                    "include_status_summary": {"type": "boolean", "required": False, "description": "Include status counts"},
                },
                returns="List of child issues with optional status summary"
            ),
            "build_jql": ActionSchema(
                name="build_jql",
                description="Convert natural language to JQL query",
                parameters={
                    "message": {"type": "string", "required": True, "description": "Natural language query"},
                },
                returns="JQL query string"
            ),
            "create_issue": ActionSchema(
                name="create_issue",
                description="Create a new Jira issue",
                parameters={
                    "project": {"type": "string", "required": True, "description": "Project key"},
                    "issue_type": {"type": "string", "required": True, "description": "Issue type (Epic, Story, Task, Bug)"},
                    "summary": {"type": "string", "required": True, "description": "Issue summary/title"},
                    "description": {"type": "string", "required": False, "description": "Issue description"},
                },
                returns="Created issue details"
            ),
            "update_issue": ActionSchema(
                name="update_issue",
                description="Update an existing Jira issue",
                parameters={
                    "issue_key": {"type": "string", "required": True, "description": "Issue key to update"},
                    "field": {"type": "string", "required": True, "description": "Field to update"},
                    "value": {"type": "string", "required": True, "description": "New value"},
                },
                returns="Updated issue details"
            ),
        }
    
    async def execute(self, action: str, params: Dict[str, Any]) -> ToolResult:
        """Execute a Jira action"""
        try:
            if action == "search":
                return await self._execute_search(params)
            elif action == "get_issue":
                return await self._execute_get_issue(params)
            elif action == "get_child_issues":
                return await self._execute_get_child_issues(params)
            elif action == "build_jql":
                return self._execute_build_jql(params)
            elif action == "create_issue":
                return await self._execute_create_issue(params)
            elif action == "update_issue":
                return await self._execute_update_issue(params)
            else:
                return ToolResult.fail(f"Unknown action: {action}")
        except Exception as e:
            logger.error(f"Jira action '{action}' failed: {e}", exc_info=True)
            return ToolResult.fail(str(e))
    
    async def _execute_search(self, params: Dict[str, Any]) -> ToolResult:
        """
        Execute agentic search with multi-step strategy:
        1. Query knowledge graph for context enrichment
        2. Build intelligent JQL using context
        3. Execute search with retry on errors
        4. Auto-fetch linked/child issues for epics
        """
        message = params.get("message", "") or params.get("query", "")
        jql = params.get("jql")
        max_results = params.get("max_results", 20)
        max_retries = 2
        
        # Step 1: Query knowledge graph for context enrichment
        kg_context = await self._get_kg_context(message)
        if kg_context:
            logger.info(f"🧠 KG context found: {len(kg_context.get('related_entities', []))} related entities")
        
        # Step 2: Build JQL using KG context if available
        if not jql:
            jql = self._build_context_aware_jql(message, kg_context)
            logger.info(f"Built JQL from message: {jql}")
        
        for attempt in range(max_retries):
            try:
                # Try MCP first if enabled
                results = None
                if self.mcp_client:
                    results = await self.mcp_client.search_jira_via_mcp(jql, max_results)
                    if results:
                        logger.info(f"MCP search returned {len(results)} results")
                
                # Fallback to direct API
                if results is None:
                    results = jira_service.search_issues(jql, max_results)
                    logger.info(f"Direct API search returned {len(results)} results")
                
                if not results:
                    # If no results and we have KG context, try using issue keys from KG
                    if kg_context and kg_context.get('issue_keys'):
                        logger.info("🔄 No results, trying issue keys from KG context")
                        results = await self._fetch_issues_by_keys(kg_context['issue_keys'][:10])
                    
                    if not results:
                        return ToolResult.ok(
                            [],
                            jql=jql,
                            message="No issues found matching your query"
                        )
                
                # Step 3: Auto-expand epics - fetch linked issues
                expanded_results = await self._expand_epic_results(results, message)
                
                # Add all to knowledge graph
                for issue in expanded_results:
                    knowledge_graph_service.add_jira_issue(issue)
                
                return ToolResult.ok(
                    expanded_results,
                    jql=jql,
                    count=len(expanded_results),
                    original_count=len(results),
                    expanded=len(expanded_results) > len(results)
                )
                
            except Exception as e:
                error_msg = str(e)
                
                # Check if this is a JQL syntax error we can retry
                if "JQL" in error_msg and attempt < max_retries - 1:
                    logger.warning(f"🔄 JQL error on attempt {attempt + 1}, asking LLM to fix: {error_msg[:200]}")
                    
                    # Extract just the error message for cleaner prompt
                    if "text:" in error_msg:
                        error_msg = error_msg.split("text:")[1].split("\n")[0].strip()
                    
                    # Retry with error feedback
                    jql = self.query_builder.build_intelligent_query(message, previous_error=error_msg)
                    logger.info(f"🔄 Retrying with corrected JQL: {jql}")
                    continue
                else:
                    logger.error(f"Jira search failed after {attempt + 1} attempts: {e}")
                    return ToolResult.fail(f"Search failed: {error_msg[:200]}")
    
    async def _execute_get_issue(self, params: Dict[str, Any]) -> ToolResult:
        """Execute get_issue action"""
        issue_key = params.get("issue_key")
        if not issue_key:
            return ToolResult.fail("issue_key is required")
        
        # Try MCP first if enabled
        result = None
        if self.mcp_client:
            result = await self.mcp_client.get_jira_issue_via_mcp(issue_key)
            if result:
                logger.info(f"MCP returned issue {issue_key}")
        
        # Fallback to direct API
        if result is None:
            result = jira_service.get_issue(issue_key)
            logger.info(f"Direct API returned issue {issue_key}")
        
        if not result:
            return ToolResult.fail(f"Issue {issue_key} not found")
        
        # Add to knowledge graph
        knowledge_graph_service.add_jira_issue(result)
        
        return ToolResult.ok(result)
    
    async def _execute_get_child_issues(self, params: Dict[str, Any]) -> ToolResult:
        """Execute get_child_issues action"""
        parent_key = params.get("parent_key")
        include_status_summary = params.get("include_status_summary", True)
        
        if not parent_key:
            return ToolResult.fail("parent_key is required")
        
        if include_status_summary:
            child_issues, status_counts, in_progress_names = \
                jira_service.get_child_issues_with_status_summary(parent_key)
            
            # Add to knowledge graph with relationships
            for child in child_issues:
                knowledge_graph_service.add_jira_issue(child)
                knowledge_graph_service.add_relationship(
                    child.get('key'), parent_key, "child_of",
                    properties={"relationship": "parent-child"}
                )
            
            return ToolResult.ok({
                "children": child_issues,
                "status_summary": status_counts,
                "in_progress_items": in_progress_names,
                "total_count": len(child_issues)
            })
        else:
            child_issues = jira_service.get_child_issues(parent_key)
            
            # Add to knowledge graph
            for child in child_issues:
                knowledge_graph_service.add_jira_issue(child)
            
            return ToolResult.ok(child_issues)
    
    def _execute_build_jql(self, params: Dict[str, Any]) -> ToolResult:
        """Execute build_jql action"""
        message = params.get("message", "")
        if not message:
            return ToolResult.fail("message is required")
        
        jql = self.query_builder.build_intelligent_query(message)
        return ToolResult.ok({"jql": jql})
    
    async def _execute_create_issue(self, params: Dict[str, Any]) -> ToolResult:
        """Execute create_issue action"""
        # Delegate to write service
        # This would require approval workflow in production
        return ToolResult.fail("Create issue requires approval workflow - use clarification service")
    
    async def _execute_update_issue(self, params: Dict[str, Any]) -> ToolResult:
        """Execute update_issue action"""
        # Delegate to write service
        # This would require approval workflow in production
        return ToolResult.fail("Update issue requires approval workflow - use clarification service")
    
    # ==========================================================================
    # Agentic Search Enhancement Methods
    # ==========================================================================
    
    async def _get_kg_context(self, message: str) -> Optional[Dict]:
        """
        Query knowledge graph to get context for the search.
        Returns related entities, issue keys, and semantic context.
        """
        try:
            # Try nano-graphrag first for semantic search
            if knowledge_graph_service.nano_graphrag and knowledge_graph_service.nano_graphrag.enabled:
                try:
                    # Use local mode for entity-focused search  
                    # nano-graphrag has async aquery method
                    context = await knowledge_graph_service.nano_graphrag.graphrag.aquery(
                        message, 
                        param=knowledge_graph_service.nano_graphrag._get_query_param("local")
                    )
                    if context:
                        # Extract issue keys from context
                        issue_keys = re.findall(r'\b([A-Z]+-\d+)\b', str(context))
                        logger.info(f"KG context found {len(issue_keys)} issue keys: {issue_keys[:5]}")
                        return {
                            'context': str(context)[:1000],  # Limit size
                            'issue_keys': list(set(issue_keys)),
                            'related_entities': issue_keys[:5]
                        }
                except Exception as e:
                    logger.debug(f"Nano-graphrag query failed: {e}")
            
            # Fall back to legacy KG entity search
            entities = knowledge_graph_service.search_by_text(message)
            if entities:
                issue_keys = [e['id'] for e in entities if e.get('entity_type') == 'jira_issue']
                return {
                    'issue_keys': issue_keys[:10],
                    'related_entities': [e['id'] for e in entities[:5]]
                }
            
            return None
        except Exception as e:
            logger.debug(f"KG context lookup failed: {e}")
            return None
    
    def _build_context_aware_jql(self, message: str, kg_context: Optional[Dict]) -> str:
        """
        Build JQL using knowledge graph context for enrichment.
        If KG has related issue keys, incorporate them.
        """
        # Start with standard intelligent query
        base_jql = self.query_builder.build_intelligent_query(message)
        
        # If we found related issue keys in KG, we might want to search parent issues
        if kg_context and kg_context.get('issue_keys'):
            # Check if message mentions relationships (parent, epic, linked)
            relationship_terms = ['epic', 'parent', 'linked', 'related', 'child', 'subtask']
            if any(term in message.lower() for term in relationship_terms):
                # Add parent search to find epics/parents
                issue_keys = kg_context['issue_keys'][:3]
                if issue_keys:
                    parent_clause = ' OR '.join([f'key = "{k}"' for k in issue_keys])
                    logger.info(f"🧠 Enriching JQL with KG issue keys: {issue_keys}")
                    # Don't replace, just log - the base JQL should be good
        
        return base_jql
    
    async def _fetch_issues_by_keys(self, issue_keys: list) -> list:
        """Fetch specific issues by their keys"""
        results = []
        for key in issue_keys[:10]:  # Limit to 10
            try:
                issue = jira_service.get_issue(key)
                if issue:
                    results.append(issue)
            except Exception as e:
                logger.debug(f"Could not fetch {key}: {e}")
        return results
    
    async def _expand_epic_results(self, results: list, message: str) -> list:
        """
        If we found an Epic and user seems to want details, auto-fetch linked issues.
        This is the key agentic behavior - anticipating what the user needs.
        """
        if not results:
            return results
        
        expanded = list(results)  # Copy original results
        
        # Check if user is asking about contents/children/details
        detail_terms = ['books', 'items', 'children', 'subtasks', 'linked', 'contains', 
                       'what', 'which', 'list', 'show', 'tell', 'how many', 'details']
        wants_details = any(term in message.lower() for term in detail_terms)
        
        if not wants_details:
            return expanded
        
        for issue in results:
            issue_type = issue.get('issue_type', '').lower()
            issue_key = issue.get('key', '')
            
            # If it's an Epic or has linked issues, fetch them
            if issue_type in ['epic', 'initiative', 'feature'] or issue.get('issue_links'):
                logger.info(f"🔍 Expanding {issue_type} {issue_key} - fetching linked/child issues")
                
                # Get child issues
                try:
                    children = jira_service.get_child_issues(issue_key)
                    if children:
                        logger.info(f"📦 Found {len(children)} child issues for {issue_key}")
                        for child in children:
                            if child.get('key') not in [r.get('key') for r in expanded]:
                                expanded.append(child)
                except Exception as e:
                    logger.debug(f"Could not fetch children of {issue_key}: {e}")
                
                # Also fetch linked issues from the issue_links field
                issue_links = issue.get('issue_links', [])
                if issue_links:
                    logger.info(f"🔗 Fetching {len(issue_links)} linked issues for {issue_key}")
                    for link in issue_links[:10]:  # Limit
                        link_key = link.get('key')
                        if link_key and link_key not in [r.get('key') for r in expanded]:
                            try:
                                linked_issue = jira_service.get_issue(link_key)
                                if linked_issue:
                                    expanded.append(linked_issue)
                            except Exception as e:
                                logger.debug(f"Could not fetch linked issue {link_key}: {e}")
        
        if len(expanded) > len(results):
            logger.info(f"📈 Expanded results from {len(results)} to {len(expanded)} issues")
        
        return expanded
    
    # Convenience methods for common operations
    def extract_issue_key(self, message: str) -> Optional[str]:
        """Extract Jira issue key from message"""
        return self.intent_detector.extract_issue_key(message)
    
    def is_asking_for_children(self, message: str) -> bool:
        """Check if asking for child issues"""
        return self.intent_detector.is_asking_for_children(message)
    
    def is_write_operation(self, message: str) -> Optional[str]:
        """Check if this is a write operation"""
        return self.intent_detector.is_write_operation(message)


# Singleton instance for convenience
jira_tool = JiraTool()

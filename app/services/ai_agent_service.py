from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from typing import Dict, Any, List, Optional
import logging
import json
import re
import uuid
from datetime import datetime

from app.config import settings
from app.services.jira_service import jira_service
from app.services.confluence_service import confluence_service
from app.services.knowledge_graph_service import knowledge_graph_service
from app.services.web_search_service import web_search_service

logger = logging.getLogger(__name__)

# Module-level state for pending operations (persists across requests)
# In production, this should be stored in Redis or a database
_pending_operations: Dict[str, Dict[str, Any]] = {}


class AIAgentService:
    """Agentic AI system for delivery intelligence and decision support with Knowledge Graph RAG"""
    
    def __init__(self):
        self.llm = self._initialize_llm()
        # Use module-level pending operations
        self.pending_operations = _pending_operations
    
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
        """Check if user is asking for child/subtask issues"""
        child_keywords = ['child', 'children', 'subtask', 'sub-task', 'sub task', 'child issue', 'child issues',
                         'task created', 'tasks created', 'any task', 'any tasks', 'subtasks of', 'tasks for']
        return any(keyword in message.lower() for keyword in child_keywords)
    
    def _extract_issue_key(self, message: str) -> str:
        """Extract Jira issue key from message (e.g., PROJ-123)"""
        match = re.search(r'\b([A-Z]+-\d+)\b', message)
        return match.group(1) if match else None
    
    def _build_jql_from_message(self, message: str) -> str:
        """Build a JQL query from natural language message (legacy method, use _intelligent_jira_search instead)"""
        message_lower = message.lower()
        
        # Extract quoted phrases (exact matches)
        quoted = re.findall(r'"([^"]+)"', message)
        if quoted:
            return f'summary~"{quoted[0]}"'
        
        # Look for key phrases
        if 'open' in message_lower:
            return 'status in (Open, "To Do", "In Progress")'
        elif 'closed' in message_lower or 'done' in message_lower:
            return 'status in (Done, Closed, Resolved)'
        elif 'assigned to me' in message_lower:
            return 'assignee = currentUser()'
        
        # Default: search in summary
        # Remove common words
        words = [w for w in message.split() if len(w) > 3 and w.lower() not in ['show', 'find', 'search', 'about', 'jira', 'issues', 'tickets']]
        if words:
            search_term = ' '.join(words[:5])  # Use first 5 meaningful words
            return f'summary~"{search_term}" OR description~"{search_term}"'
        
        # Fallback to all recent issues
        return 'order by updated DESC'
    
    def _intelligent_jira_search(self, message: str) -> str:
        """Use LLM to build intelligent JQL and try multiple search strategies"""
        try:
            # Use LLM to understand intent and build JQL
            prompt = f"""Analyze this user request and create Jira JQL queries.

User Request: "{message}"

Create 2 JQL queries:
1. PRIMARY - Specific query matching the request
2. FALLBACK - Broader query to catch more results

Rules:
- Use text~ for searching summary/description (e.g., text~"philosophy")
- Common statuses: "To Do", "In Progress", Done, Closed
- Common types: Epic, Story, Task, Bug
- Keep queries simple and valid
- IMPORTANT: When user mentions MULTIPLE keywords (e.g., "philosophy book"), use AND to require ALL keywords
- Example: "philosophy book" should use: text~"philosophy" AND text~"book" (not OR)
- Use OR only when user explicitly wants alternatives

Format (IMPORTANT - respond in exactly this format):
PRIMARY: <jql query here>
FALLBACK: <jql query here>

Examples:
Request: "philosophy books to read"
PRIMARY: text~"philosophy" AND text~"book" AND status="To Do"
FALLBACK: text~"philosophy" AND text~"book"

Request: "show me open bugs"
PRIMARY: type=Bug AND status in (Open, "To Do", "In Progress")
FALLBACK: type=Bug

Request: "epics about authentication"
PRIMARY: type=Epic AND text~"authentication"
FALLBACK: text~"authentication"

Request: "reading books OR watching movies"
PRIMARY: text~"reading" AND text~"book" OR text~"watching" AND text~"movie"
FALLBACK: text~"reading" OR text~"watching"

Now create JQL for: "{message}"
"""

            response = self.llm.invoke(prompt)
            llm_output = response.content.strip()
            logger.info(f"🧠 LLM response:\n{llm_output}")
            
            # Parse PRIMARY and FALLBACK queries with more flexible regex
            # Handle markdown formatting (**, *, etc.) and multiline responses
            # Look for PRIMARY: followed by JQL on same or next line
            primary_match = re.search(r'(?:\*\*)?PRIMARY(?:\*\*)?[:\s]+(.+?)(?=(?:\*\*)?FALLBACK|$)', llm_output, re.IGNORECASE | re.DOTALL)
            fallback_match = re.search(r'(?:\*\*)?FALLBACK(?:\*\*)?[:\s]+(.+?)(?:\n\n|$)', llm_output, re.IGNORECASE | re.DOTALL)
            
            primary_jql = primary_match.group(1).strip() if primary_match else None
            fallback_jql = fallback_match.group(1).strip() if fallback_match else None
            
            # Clean up JQL - remove markdown, quotes, extra whitespace, trailing periods, newlines
            if primary_jql:
                primary_jql = primary_jql.strip('"\'` \n.;*')
                primary_jql = re.sub(r'\*\*|\*|`', '', primary_jql)  # Remove markdown formatting
                primary_jql = primary_jql.split('\n')[0].strip()  # Take only first line if multiline
                # Ensure quotes are balanced
                if primary_jql.count('"') % 2 != 0:
                    primary_jql += '"'  # Add missing closing quote
            if fallback_jql:
                fallback_jql = fallback_jql.strip('"\'` \n.;*')
                fallback_jql = re.sub(r'\*\*|\*|`', '', fallback_jql)  # Remove markdown formatting
                fallback_jql = fallback_jql.split('\n')[0].strip()  # Take only first line if multiline
                # Ensure quotes are balanced
                if fallback_jql.count('"') % 2 != 0:
                    fallback_jql += '"'  # Add missing closing quote
            
            logger.info(f"🧠 LLM-generated PRIMARY JQL: {primary_jql}")
            logger.info(f"🧠 LLM-generated FALLBACK JQL: {fallback_jql}")
            
            # If LLM failed to generate queries, use basic extraction
            if not primary_jql and not fallback_jql:
                logger.warning("⚠️ LLM failed to generate JQL, using keyword extraction")
                return self._search_jira_issues(self._build_jql_from_message(message))
            
            # Try primary query first
            if primary_jql:
                try:
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
            return self._search_jira_issues(self._build_jql_from_message(message))
            
        except Exception as e:
            logger.error(f"Error in intelligent search: {e}", exc_info=True)
            # Fallback to basic search
            jql = self._build_jql_from_message(message)
            logger.info(f"⚠️ Falling back to basic JQL: {jql}")
            return self._search_jira_issues(jql)
    
    def _verify_and_filter_results(self, user_query: str, jira_results: str) -> str:
        """
        Verify that search results actually match user's intent and filter out irrelevant items.
        
        Args:
            user_query: Original user question
            jira_results: JSON string of Jira issues found
            
        Returns:
            Filtered JSON string containing only relevant results
        """
        try:
            # Parse results
            import json
            results = json.loads(jira_results) if isinstance(jira_results, str) else jira_results
            
            # If no results or error message, return as-is
            if not results or not isinstance(results, list):
                return jira_results
            
            # If only 1-3 results, probably already filtered well - return as-is
            if len(results) <= 3:
                logger.info(f"✅ Only {len(results)} results, skipping verification")
                return jira_results
            
            logger.info(f"🔍 Verifying {len(results)} results match intent: '{user_query}'")
            
            # Create a concise summary of results for LLM
            results_summary = []
            for i, issue in enumerate(results[:20]):  # Check max 20 to avoid token limits
                results_summary.append({
                    'index': i,
                    'key': issue.get('key', 'N/A'),
                    'summary': issue.get('summary', 'N/A')[:150],  # Limit length
                    'type': issue.get('issue_type', 'N/A'),
                    'status': issue.get('status', 'N/A')
                })
            
            # Ask LLM to verify which results actually match
            verification_prompt = f"""User asked: "{user_query}"

Found {len(results)} Jira issues. Review which ones ACTUALLY match the user's intent.

Results:
{json.dumps(results_summary, indent=2)}

Task: Identify which issue indexes (0-{len(results_summary)-1}) are RELEVANT to the user's query.

Rules:
- Be strict: Only include issues that clearly match ALL keywords in the query
- Example: If user asks for "philosophy books", exclude issues about "reading in general" or "other topics"
- If user specifies a status (e.g., "to read", "done"), only include matching statuses
- Return ONLY the indexes of relevant issues

Format your response as a comma-separated list of indexes:
RELEVANT: 0, 2, 5, 8

If ALL results are relevant, respond with:
RELEVANT: ALL

If NO results match, respond with:
RELEVANT: NONE"""
            
            verification_response = self.llm.invoke(verification_prompt)
            response_text = verification_response.content.strip()
            
            logger.info(f"🧠 LLM verification: {response_text}")
            
            # Parse LLM response
            if "RELEVANT: ALL" in response_text:
                logger.info("✅ All results verified as relevant")
                return jira_results
            
            if "RELEVANT: NONE" in response_text:
                logger.warning("⚠️ No results matched user intent")
                return json.dumps([], indent=2)
            
            # Extract relevant indexes
            relevant_match = re.search(r'RELEVANT:\s*([0-9,\s]+)', response_text)
            if relevant_match:
                indexes_str = relevant_match.group(1)
                relevant_indexes = [int(idx.strip()) for idx in indexes_str.split(',') if idx.strip().isdigit()]
                
                # Filter results to only relevant ones
                filtered_results = [results[i] for i in relevant_indexes if i < len(results)]
                
                logger.info(f"✅ Filtered from {len(results)} to {len(filtered_results)} relevant results")
                return json.dumps(filtered_results, indent=2)
            
            # If parsing failed, return original results
            logger.warning("⚠️ Could not parse verification response, returning all results")
            return jira_results
            
        except Exception as e:
            logger.error(f"Error verifying results: {e}", exc_info=True)
            # On error, return original results
            return jira_results
            # Fallback to basic search
            jql = self._build_jql_from_message(message)
            logger.info(f"⚠️ Falling back to basic JQL: {jql}")
            return self._search_jira_issues(jql)
            return self._search_jira_issues(jql)
    
    def _search_jira_issues(self, query: str) -> str:
        """Search Jira issues using JQL and add to knowledge graph"""
        try:
            results = jira_service.search_issues(query, max_results=20)
            if not results:
                return "No issues found matching your query."
            
            # Add issues to knowledge graph
            for issue in results:
                knowledge_graph_service.add_jira_issue(issue)
            
            return json.dumps(results, indent=2)
        except Exception as e:
            logger.error(f"Error in Jira search: {e}")
            return f"Error searching Jira: {str(e)}"
    
    def _get_jira_issue(self, issue_key: str) -> str:
        """Get detailed information about a specific Jira issue"""
        try:
            result = jira_service.get_issue(issue_key.strip())
            if not result:
                return f"Issue {issue_key} not found."
            
            # Add to knowledge graph
            knowledge_graph_service.add_jira_issue(result)
            
            # Get related entities from knowledge graph
            related = knowledge_graph_service.get_related_entities(issue_key)
            if related:
                result["related_entities"] = related
            
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error getting Jira issue: {e}")
            return f"Error getting issue: {str(e)}"
    
    def _search_confluence(self, query: str) -> str:
        """Search Confluence documentation and add to knowledge graph"""
        try:
            results = confluence_service.search_content(query, limit=10)
            if not results:
                return "No Confluence pages found matching your query."
            
            # Add pages to knowledge graph
            for page in results:
                knowledge_graph_service.add_confluence_page(page)
            
            return json.dumps(results, indent=2)
        except Exception as e:
            logger.error(f"Error in Confluence search: {e}")
            return f"Error searching Confluence: {str(e)}"
    
    def _get_confluence_page(self, page_id: str) -> str:
        """Get content from a specific Confluence page"""
        try:
            result = confluence_service.get_page(page_id.strip())
            if not result:
                return f"Page {page_id} not found."
            
            # Add to knowledge graph
            knowledge_graph_service.add_confluence_page(result)
            
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error getting Confluence page: {e}")
            return f"Error getting page: {str(e)}"
    
    async def _search_web(self, query: str) -> str:
        """Search the web using DuckDuckGo"""
        try:
            logger.info(f"🌐 Searching web for: {query}")
            results = await web_search_service.search(query, max_results=5)
            if not results:
                return "No web results found for your query."
            
            return json.dumps(results, indent=2)
        except Exception as e:
            logger.error(f"Error in web search: {e}")
            return f"Error searching web: {str(e)}"
            
            # Add to knowledge graph
            knowledge_graph_service.add_confluence_page(result)
            
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error getting Confluence page: {e}")
            return f"Error getting page: {str(e)}"
    
    def _analyze_delivery_metrics(self, project_key: str) -> str:
        """Analyze delivery metrics for a project using knowledge graph"""
        try:
            issues = jira_service.get_project_issues(project_key.strip(), max_results=100)
            if not issues:
                return f"No issues found for project {project_key}"
            
            # Add all issues to knowledge graph
            for issue in issues:
                knowledge_graph_service.add_jira_issue(issue)
            
            # Calculate basic metrics
            total = len(issues)
            status_counts = {}
            assignee_counts = {}
            
            for issue in issues:
                status = issue.get("status", "Unknown")
                status_counts[status] = status_counts.get(status, 0) + 1
                
                assignee = issue.get("assignee", "Unassigned")
                assignee_counts[assignee] = assignee_counts.get(assignee, 0) + 1
            
            # Get knowledge graph insights
            kg_stats = knowledge_graph_service.get_graph_stats()
            central_entities = knowledge_graph_service.get_central_entities(limit=5)
            
            metrics = {
                "project": project_key,
                "total_issues": total,
                "status_breakdown": status_counts,
                "assignee_breakdown": assignee_counts,
                "completion_rate": f"{(status_counts.get('Done', 0) / total * 100):.1f}%" if total > 0 else "0%",
                "knowledge_graph": {
                    "total_entities": kg_stats.get("total_nodes", 0),
                    "total_relationships": kg_stats.get("total_edges", 0),
                    "central_entities": [{"id": eid, "score": f"{score:.4f}"} for eid, score in central_entities]
                }
            }
            
            return json.dumps(metrics, indent=2)
        except Exception as e:
            logger.error(f"Error analyzing delivery metrics: {e}")
            return f"Error analyzing metrics: {str(e)}"
    
    def _get_knowledge_graph_context(self, query: str) -> str:
        """Get relevant context from knowledge graph for RAG"""
        try:
            # Search for relevant entities
            jira_entities = knowledge_graph_service.search_entities(entity_type="jira_issue")
            confluence_entities = knowledge_graph_service.search_entities(entity_type="confluence_page")
            
            context = {
                "total_jira_issues": len(jira_entities),
                "total_confluence_pages": len(confluence_entities),
                "recent_issues": jira_entities[:5] if jira_entities else [],
                "graph_stats": knowledge_graph_service.get_graph_stats()
            }
            
            return json.dumps(context, indent=2)
        except Exception as e:
            logger.error(f"Error getting knowledge graph context: {e}")
            return "{}"
    
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
            if recommended_action:
                logger.info(f"🧠 RL recommends action: {recommended_action}")
            if context_modes:
                logger.info(f"🎯 Context modes from frontend: {context_modes}")
            
            # FIRST: Check for write operations (CREATE/UPDATE/DELETE)
            message_lower = message.lower()
            write_keywords = ['create', 'add', 'new', 'make', 'update', 'modify', 'change', 'edit', 'delete', 'remove', 'transition', 'move to']
            
            # Detect update intent with broader patterns
            # Common updatable fields in Jira
            updatable_fields = ['name', 'title', 'summary', 'description', 'priority', 'assignee', 'status', 'label', 'epic']
            
            # Update action words
            update_actions = ['better', 'improve', 'fix', 'correct', 'update', 'change', 'modify', 'rename', 'edit']
            
            # Check if user is expressing update intent
            # Pattern: [update_action] + [field] OR [field] + needs + [update_action]
            has_update_intent = False
            detected_field = None
            
            for action in update_actions:
                for field in updatable_fields:
                    # Pattern 1: "better name", "improve summary", etc.
                    if f"{action} {field}" in message_lower or f"{action} the {field}" in message_lower:
                        has_update_intent = True
                        detected_field = field if field != 'name' else 'summary'  # Map 'name' to 'summary'
                        detected_field = field if field != 'title' else 'summary'  # Map 'title' to 'summary'
                        logger.info(f"✅ Detected update intent: {action} {field}")
                        break
                    # Pattern 2: "any ideas for the name?", "suggestions for title?"
                    if f"for the {field}" in message_lower or f"for {field}" in message_lower:
                        if any(word in message_lower for word in ['idea', 'suggest', 'recommend', 'think']):
                            has_update_intent = True
                            detected_field = field if field not in ['name', 'title'] else 'summary'
                            logger.info(f"✅ Detected update intent: suggestions for {field}")
                            break
                if has_update_intent:
                    break
            
            # Check if user is responding to a suggestion to update (e.g., "yes I would like to")
            affirmative_with_update = False
            if any(phrase in message_lower for phrase in ['yes', 'yeah', 'sure', 'ok', 'okay']):
                if has_update_intent:
                    affirmative_with_update = True
                    logger.info(f"✅ Detected affirmative response with update intent")
            
            # Check conversation history for recent issue mentions
            recent_issue_key = None
            if conversation_history and len(conversation_history) > 0:
                # Look at last 3 messages for issue keys
                for msg in reversed(conversation_history[-3:]):
                    if msg.role == "assistant":
                        # Extract issue key from assistant's response
                        match = re.search(r'\b([A-Z]{2,10}-\d+)\b', msg.content)
                        if match:
                            recent_issue_key = match.group(1)
                            logger.info(f"📌 Found recent issue in conversation: {recent_issue_key}")
                            break
            
            # Check if this is a response to clarification questions FIRST
            pending_op = self.pending_operations.get(session_id)
            logger.info(f"🔍 Checking for pending operations. Session: {session_id}, Pending: {pending_op is not None}")
            
            if pending_op:
                # Validate and clean up pending operation fields
                valid_fields = ['project', 'issue_type', 'summary', 'description', 'priority', 'assignee', 'labels']
                pending_op['missing_fields'] = [f for f in pending_op.get('missing_fields', []) if f in valid_fields]
                
                logger.info(f"📝 Processing clarification response for {pending_op['operation']}")
                return self._handle_clarification_response(message, session_id, pending_op)
            
            # Then check for new write operations
            is_write_operation = any(keyword in message_lower for keyword in write_keywords)
            
            # Also check for context-based update intent
            if not is_write_operation and (affirmative_with_update or has_update_intent):
                if recent_issue_key:
                    logger.info(f"🎯 Detected context-based update intent for {recent_issue_key}")
                    is_write_operation = True
            
            if is_write_operation:
                logger.info(f"⚠️ WRITE OPERATION detected: {message}")
                
                # Extract operation type
                operation = None
                if any(word in message_lower for word in ['create', 'add', 'new', 'make']):
                    operation = 'create'
                elif any(word in message_lower for word in ['update', 'modify', 'change', 'edit']) or affirmative_with_update or has_update_intent:
                    operation = 'update'
                    # Pre-fill issue_key and field if detected from context
                    if recent_issue_key and operation == 'update':
                        logger.info(f"📝 Auto-filling issue_key from context: {recent_issue_key}")
                        # We'll pass this to the extraction phase
                elif any(word in message_lower for word in ['delete', 'remove']):
                    operation = 'delete'
                elif any(word in message_lower for word in ['transition', 'move to']):
                    operation = 'transition'
                
                # Start clarification workflow with context
                return self._start_clarification_workflow(message, session_id, operation, context_issue_key=recent_issue_key)
            
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
                should_use_jira = (
                    (recommended_action in ["search_jira", "get_jira_issue", "get_child_issues"]) or 
                    self._should_search_jira(message)
                )
                
                should_use_confluence = (
                    recommended_action in ["search_confluence", "get_confluence_page"] or
                    any(word in message.lower() for word in ['confluence', 'documentation', 'docs', 'wiki', 'guide'])
                )
                
                # Check for web search intent
                should_use_web = any(phrase in message.lower() for phrase in [
                    'search web', 'search the web', 'google', 'look up online', 
                    'find online', 'web search', 'search for', 'what is', 'who is',
                    'weather', 'news', 'latest', 'current events'
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
                
                # FIRST: Check if this is a follow-up question about previous results
                # Look for status-based references (e.g., "the in progress", "the to do", "the done")
                message_lower = message.lower()
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
                            jira_result = self._get_jira_issue(target_keys[0])
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
                    jira_result = self._get_jira_issue(issue_key)
                else:
                    # FIRST: Search knowledge graph for existing data
                    logger.info(f"🔍 Searching Knowledge Graph first...")
                    kg_results = knowledge_graph_service.search_by_text(message)
                    
                    if kg_results and len(kg_results) > 0:
                        # Found results in KG
                        logger.info(f"✅ Found {len(kg_results)} results in Knowledge Graph")
                        jira_result = json.dumps(kg_results, indent=2)
                    else:
                        # Not in KG, search Jira with intelligent query building
                        logger.info(f"📡 No KG results, searching Jira with intelligent query...")
                        jira_result = self._intelligent_jira_search(message)
                
                logger.info(f"✅ Jira query completed, formatting response...")
                
                # STEP 1: Verify results match user's intent (filter irrelevant results)
                filtered_result = self._verify_and_filter_results(message, jira_result)
                
                # STEP 2: Have LLM format the filtered results nicely with context
                prompt = f"""User asked: {message}
{context}
Jira data retrieved:
{filtered_result}

IMPORTANT: Your response must be based ONLY on the actual Jira data provided above. Do NOT invent themes, narratives, or context.

RESPONSE GUIDELINES:
1. Use the REAL issue summaries, statuses, and details from the data
2. Be conversational but accurate - describe what you actually see in the data
3. Use markdown formatting:
   - Headers (##) for sections
   - Bold (**text**) for emphasis  
   - Code backticks for issue keys (`ACTHUB-123`)
   - Tables when comparing multiple items
   - Lists for organization
4. Include issue keys for all mentioned items
5. Provide observations about actual patterns in the data
6. Do NOT create fictional scenarios or assume what the project is about

Describe the actual data in an engaging way."""
                
                response = self.llm.invoke(prompt)
                return response.content
            
            # Check for Confluence searches
            elif should_use_confluence:
                logger.info("📚 Detected Confluence query - routing to Confluence service")
                confluence_result = self._search_confluence(message)
                
                prompt = f"""User asked: {message}
{context}
Confluence data retrieved:
{confluence_result}

Please provide a clear, helpful response based on this Confluence data."""
                
                response = self.llm.invoke(prompt)
                return response.content
            
            # Check for web search
            elif should_use_web:
                logger.info("🌐 Detected web search query - routing to web search")
                web_result = await self._search_web(message)
                
                prompt = f"""User asked: {message}
{context}
Web search results:
{web_result}

Please provide a clear, helpful response based on these web search results. Include source URLs when relevant."""
                
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
        """Extract as much information as possible from the initial message"""
        details = {}
        message_lower = message.lower()
        
        # For UPDATE operations, extract issue identifier
        if operation == 'update':
            # Try to extract issue key first (PROJ-123)
            key_match = re.search(r'\b([A-Z]{2,10}-\d+)\b', message)
            if key_match:
                details['issue_key'] = key_match.group(1)
            else:
                # Extract issue description for search
                update_patterns = [
                    r'(?:update|change|modify)\s+(?:an?\s+)?(epic|story|task|bug|issue)\s+(?:about|called|named)\s+(.+?)(?:\s+to|\s+in|\s+for|$)',
                    r'(?:update|change|modify)\s+["\']?([^"\']+?)["\']?\s+(?:to|in|for)',
                    r'(?:update|change|modify)\s+(.+?)\s+(?:to|in|for)'
                ]
                for pattern in update_patterns:
                    match = re.search(pattern, message, re.IGNORECASE)
                    if match:
                        # Get the last group (search term)
                        groups = match.groups()
                        search_term = groups[-1].strip() if groups else ''
                        # Remove trailing words
                        search_term = re.sub(r'\s+(to|in|for|the)$', '', search_term, flags=re.IGNORECASE)
                        if search_term:
                            details['issue_search'] = search_term
                            logger.info(f"🔍 Extracted search term: '{search_term}'")
                            break
            
            # Extract what to update (field and value)
            if 'priority' in message_lower:
                details['field'] = 'priority'
                priorities = ['highest', 'high', 'medium', 'low', 'lowest']
                for priority in priorities:
                    if priority in message_lower:
                        details['value'] = priority.title()
                        break
            
            if 'status' in message_lower or 'move to' in message_lower or 'transition' in message_lower:
                details['field'] = 'status'
                # Extract status value
                status_match = re.search(r'(?:to|status)\s+["\']?([A-Za-z\s]+)["\']?', message)
                if status_match:
                    details['value'] = status_match.group(1).strip()
        
        # For CREATE operations
        elif operation == 'create':
            # Extract issue type
            issue_types = ['epic', 'story', 'task', 'bug', 'subtask', 'sub-task', 'idea', 'improvement']
            for itype in issue_types:
                if itype in message_lower:
                    details['issue_type'] = itype.replace('-', '').title()
                    break
            
            # Extract summary/title (look for quoted text or after "called"/"named")
            summary_patterns = [
                r'called ["\']([^"\']+)["\']',
                r'named ["\']([^"\']+)["\']',
                r'["\']([^"\']+)["\']',
                r'(?:called|named)\s+([^\s]+(?:\s+[^\s]+)?(?:\s+[^\s]+)?)(?:\s+in\s+|\s+for\s+|$)',
                r'^create\s+(?:an?\s+)?(?:epic|story|task|bug|idea|improvement)?\s+(.+?)(?:\s+in\s+|\s+for\s+|$)'
            ]
            for pattern in summary_patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    summary = match.group(1).strip()
                    # Remove trailing 'in', 'for' words and clean up
                    summary = re.sub(r'\s+(in|for)$', '', summary, flags=re.IGNORECASE)
                    # Improve the summary using AI
                    summary = self._improve_summary(summary, details.get('issue_type', 'Task'))
                    details['summary'] = summary
                    break
        
        # Extract project key
        proj_match = re.search(r'\b([A-Z]{2,})-?\d*\b', message)
        if proj_match:
            project_key = proj_match.group(1)
            if project_key not in ['TEST', 'NEW', 'CREATE']:  # Avoid false positives
                details['project'] = project_key
        
        # Look for explicit project mentions
        proj_keywords = re.search(r'(?:project|in) ([A-Z]{2,10})', message, re.IGNORECASE)
        if proj_keywords:
            details['project'] = proj_keywords.group(1).upper()
        
        # Extract description (everything after "with description" or "description:")
        desc_match = re.search(r'(?:with description|description:)\s*["\']?([^"\']+)["\']?', message, re.IGNORECASE)
        if desc_match:
            details['description'] = desc_match.group(1).strip()
        
        # Extract priority
        priorities = ['highest', 'high', 'medium', 'low', 'lowest']
        for priority in priorities:
            if priority in message_lower:
                details['priority'] = priority.title()
                break
        
        # Extract assignee
        assignee_match = re.search(r'(?:assign to|assigned to|assignee:?)\s+([A-Za-z][A-Za-z0-9._@-]+)', message, re.IGNORECASE)
        if assignee_match:
            details['assignee'] = assignee_match.group(1).strip()
        
        # Extract labels
        labels_match = re.search(r'(?:labels?:?|tagged)\s+([A-Za-z0-9,\s-]+)', message, re.IGNORECASE)
        if labels_match:
            labels_str = labels_match.group(1).strip()
            details['labels'] = [l.strip() for l in labels_str.split(',')]
        
        logger.info(f"🎯 Extracted from message: {details}")
        return details
    
    def _get_required_fields(self, operation: str, issue_type: Optional[str] = None) -> List[str]:
        """Get list of required fields based on operation and issue type"""
        if operation == 'create':
            # Core required fields for any Jira issue
            required = ['project', 'issue_type', 'summary']
            
            return required
        
        elif operation == 'update':
            return ['issue_key', 'field', 'value']
        
        elif operation == 'delete':
            return ['issue_key', 'confirmation']
        
        elif operation == 'transition':
            return ['issue_key', 'status']
        
        return []
    
    def _generate_value_suggestions(self, message: str, operation: str, current_info: Dict[str, Any]) -> str:
        """Generate AI-powered suggestions for field values"""
        issue_key = current_info.get('issue_key')
        field = current_info.get('field')
        
        if not issue_key or not field:
            return self._ask_clarification_question('value', operation, current_info)
        
        try:
            # Fetch current issue data
            issue_data = jira_service.get_issue(issue_key)
            if not issue_data:
                return f"❌ Couldn't find issue {issue_key}. Please provide the new value for {field}:"
            
            # Use LLM to detect what the user is asking about and generate suggestions
            prompt = f"""You are helping a user update a Jira issue. Analyze their request and provide intelligent suggestions.

**User's Message:** "{message}"

**Current Issue Data:**
- Key: {issue_key}
- Type: {issue_data.get('issue_type', 'Unknown')}
- Summary: {issue_data.get('summary', 'No summary')}
- Description: {issue_data.get('description', 'No description')[:300]}
- Status: {issue_data.get('status', 'Unknown')}
- Priority: {issue_data.get('priority', 'Not set')}
- Due Date: {issue_data.get('duedate', 'Not set')}
- Labels: {', '.join(issue_data.get('labels', [])) if issue_data.get('labels') else 'None'}
- Assignee: {issue_data.get('assignee', 'Unassigned')}

**Task:** 
1. Determine what field the user wants help with (summary, description, priority, duedate, labels, assignee, etc.)
2. If they're asking for suggestions/ideas, provide 3 concrete options
3. If they're asking about priority/urgency relative to other work, provide contextual advice
4. If they're asking about dates/timeline, suggest realistic options with reasoning

**Response Format:**
- First line: "FIELD: <detected_field>" (e.g., "FIELD: summary" or "FIELD: duedate" or "FIELD: priority")
- Then provide suggestions in this format:

**What I think you're asking about:** <brief explanation>

**Current Value:** <current value if applicable>

**Suggestions:**
1. <first suggestion with brief reasoning>
2. <second suggestion with brief reasoning>  
3. <third suggestion with brief reasoning>

**Or you can:**
- Provide your own custom value
- Say 'keep current' to leave unchanged

Keep suggestions practical, specific, and contextual to the issue."""

            response = self.llm.invoke(prompt)
            suggestion_content = response.content.strip()
            
            # Extract the detected field from LLM response
            detected_field_match = re.search(r'^FIELD:\s*(\w+)', suggestion_content, re.IGNORECASE | re.MULTILINE)
            detected_field = detected_field_match.group(1) if detected_field_match else field
            
            # Update the field in current_info if detected
            if detected_field and detected_field != field:
                current_info['field'] = detected_field
                logger.info(f"🧠 LLM detected field: {detected_field}")
            
            # Remove the FIELD: line from the display
            display_content = re.sub(r'^FIELD:\s*\w+\s*\n', '', suggestion_content, flags=re.IGNORECASE | re.MULTILINE)
            
            # Parse numbered suggestions if they exist
            suggestions_list = []
            for line in display_content.split('\n'):
                line = line.strip()
                # Match lines like "1. text" or "1) text"
                match = re.match(r'^[1-3][\.\)]\s*(.+?)(?:\s*[-–—]\s*.*)?$', line)
                if match:
                    # Extract just the suggestion part before any reasoning
                    suggestion = match.group(1).strip()
                    # Remove quotes if present
                    suggestion = suggestion.strip('"\'')
                    suggestions_list.append(suggestion)
            
            # Store suggestions and detected field in pending operation
            return {
                'suggestions': suggestions_list,
                'detected_field': detected_field,
                'full_response': display_content,
                'message': f"""💡 **AI Suggestions for `{issue_key}`:**

{display_content}

**To use a suggestion:** Type the number (1, 2, or 3)
**Or:** Provide your own value
**Or:** Say 'keep current' to cancel"""
            }
        
        except Exception as e:
            logger.error(f"Error generating suggestions: {e}")
            return self._ask_clarification_question('value', operation, current_info)
    
    def _ask_clarification_question(self, field: str, operation: str, current_info: Dict[str, Any]) -> str:
        """Generate a contextual clarification question for a missing field"""
        
        questions = {
            'project': "📋 **Which project should this be created in?**\n\nPlease provide the project key (e.g., ACTHUB, LIFEOPS, PROJ).\n\nYou can also say something like:\n- \"Project ACTHUB\"\n- \"In the LIFEOPS project\"\n- \"ACTHUB\"",
            
            'issue_key': "🔑 **Which issue would you like to update?**\n\nProvide the issue key (e.g., ACTHUB-123) or describe the issue:\n- \"ACTHUB-123\"\n- \"The login bug\"\n- \"User authentication story\"\n\nI'll search for matching issues if you provide a description.",
            
            'field': f"✏️ **What field would you like to update for `{current_info.get('issue_key', 'this issue')}`?**\n\nCommon fields you can update:\n- **priority** - Change urgency (Highest, High, Medium, Low, Lowest)\n- **summary** - Change the title\n- **description** - Update the description\n- **assignee** - Change who it's assigned to\n- **labels** - Update tags\n- **status** - Transition to new status (In Progress, Done, etc.)\n\nExamples:\n- \"priority\"\n- \"summary\"\n- \"assignee\"",
            
            'value': f"💡 **What should the new value be for {current_info.get('field', 'this field')}?**\n\nProvide the new value.\n\nExamples:\n- For priority: \"High\", \"Highest\", \"Low\"\n- For summary: \"New Title Here\"\n- For assignee: \"john@example.com\"",
            
            'issue_type': "📝 **What type of issue would you like to create?**\n\nAvailable types:\n- **Epic** - Large feature, initiative, or theme\n- **Story** - User story or feature requirement\n- **Task** - Work item or action to complete\n- **Bug** - Defect or issue to fix\n- **Idea** - Suggestion from process discovery or brainstorming\n- **Improvement** - Enhancement to existing functionality\n- **Subtask** - Child task of another issue\n\nExamples:\n- \"Epic\"\n- \"Story\"\n- \"It's an Idea from process discovery\"\n- \"Task\"",
            
            'summary': f"✏️ **What should the {current_info.get('issue_type', 'issue')} be called?**\n\nProvide a clear, concise title.\n\nExamples:\n- \"Implement user authentication\"\n- \"Fix login page styling\"\n- \"Q1 2026 Product Launch\"",
            
            'description': f"📄 **Please provide a description for this {current_info.get('issue_type', 'issue')}**\n\nInclude details such as:\n- What needs to be done\n- Acceptance criteria\n- Context and background\n- Why this is important\n- Links to resources\n\nOr say 'skip' to leave it empty.",
            
            'priority': "⚡ **What priority should this have?**\n\nOptions:\n- Highest - Critical, blocks other work\n- High - Important, should be done soon\n- Medium - Normal priority (default)\n- Low - Can wait\n- Lowest - Nice to have\n\nOr say 'skip' for Medium (default)",
            
            'assignee': "👤 **Who should this be assigned to?**\n\nProvide:\n- Email address\n- Jira username\n- Or say 'skip' to leave unassigned",
            
            'labels': "🏷️ **Would you like to add any labels?**\n\nProvide labels separated by commas, or say 'skip'.\n\nExamples:\n- \"frontend, urgent\"\n- \"technical-debt\"\n- \"skip\"",
            
            'optional_batch': f"""📋 **Optional Details** (all in one go!)

You can provide any or all of these optional fields in your response, or just say **'skip'** to proceed:

**Description:** What needs to be done, acceptance criteria, context
**Priority:** Highest, High, Medium, Low, Lowest
**Assignee:** Username or email
**Labels:** Comma-separated tags

**Examples:**
- "Description: Implement login flow. Priority: High. Assignee: john@example.com. Labels: frontend, urgent"
- "Priority high, assign to john"  
- "skip" (to leave all empty)

Just type naturally and I'll extract what you provide!"""
        }
        
        # Build summary of what we have so far
        summary_parts = []
        if current_info:
            summary_parts.append("\n**Information collected so far:**")
            for key, value in current_info.items():
                if value:
                    summary_parts.append(f"\n- {key.replace('_', ' ').title()}: `{value}`")
        
        question = questions.get(field, f"Please provide the {field.replace('_', ' ')}:")
        
        if summary_parts:
            return f"{question}{''.join(summary_parts)}"
        return question
    
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
        """Extract specific field value from user's response"""
        message = message.strip()
        message_lower = message.lower()
        
        # For most fields, the entire message is the value (trimmed)
        if field in ['summary', 'description']:
            return message
        
        # Project: extract uppercase letters
        if field == 'project':
            match = re.search(r'\b([A-Z]{2,10})\b', message)
            return match.group(1) if match else message.upper() if len(message) <= 10 else None
        
        # Issue key: validate format or search
        if field == 'issue_key':
            # Check if it's a valid issue key format (PROJ-123)
            key_match = re.search(r'\b([A-Z]{2,10}-\d+)\b', message)
            if key_match:
                return key_match.group(1)
            
            # If not a key, it's a search term - don't search yet, just store it
            # The clarification handler will use this to search and show suggestions
            return None
        
        # Issue type: normalize
        if field == 'issue_type':
            message_lower = message.lower()
            type_map = {
                'epic': 'Epic',
                'story': 'Story',
                'task': 'Task',
                'bug': 'Bug',
                'subtask': 'Subtask',
                'sub-task': 'Subtask',
                'sub task': 'Subtask',
                'idea': 'Idea',
                'suggestion': 'Idea',
                'improvement': 'Improvement',
                'enhance': 'Improvement',
                'enhancement': 'Improvement'
            }
            for key, value in type_map.items():
                if key in message_lower:
                    return value
            # Default to Task if we can't parse
            return 'Task'
        
        # Priority: normalize
        if field == 'priority':
            message_lower = message.lower()
            priorities = ['Highest', 'High', 'Medium', 'Low', 'Lowest']
            for priority in priorities:
                if priority.lower() in message_lower:
                    return priority
            return None
        
        # Labels: split by comma
        if field == 'labels':
            return [label.strip() for label in message.split(',')]
        
        # Default: return as-is
        return message
    
    def _create_approval_request(self, session_id: str, operation: str, details: Dict[str, Any]) -> str:
        """Create an approval request that will appear in the UI"""
        from app.api.approvals import pending_approvals
        
        approval_id = str(uuid.uuid4())
        
        # Generate preview of what will be created
        preview = self._generate_operation_preview(operation, details)
        
        # Map our field names to Jira API field names based on operation type
        if operation == 'create':
            jira_parameters = {
                'project_key': details.get('project'),
                'summary': details.get('summary'),
                'issue_type': details.get('issue_type'),
                'description': details.get('description'),
                'assignee': details.get('assignee'),
                'priority': details.get('priority'),
                'labels': details.get('labels')
            }
        elif operation == 'update':
            jira_parameters = {
                'issue_key': details.get('issue_key'),
                'field': details.get('field'),
                'value': details.get('value')
            }
        elif operation == 'delete':
            jira_parameters = {
                'issue_key': details.get('issue_key')
            }
        elif operation == 'transition':
            jira_parameters = {
                'issue_key': details.get('issue_key'),
                'status': details.get('status')
            }
        else:
            jira_parameters = {}
        
        # Remove None values
        jira_parameters = {k: v for k, v in jira_parameters.items() if v is not None}
        
        # Save to pending approvals queue
        approval_data = {
            "id": approval_id,
            "action": f"{operation}_jira_issue",
            "parameters": jira_parameters,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "preview": details
        }
        pending_approvals[approval_id] = approval_data
        
        logger.info(f"📋 APPROVAL REQUEST CREATED: {approval_id}")
        logger.info(f"Operation: {operation}")
        logger.info(f"Details: {json.dumps(details, indent=2)}")
        logger.info(f"Jira Parameters: {json.dumps(jira_parameters, indent=2)}")
        logger.info(f"✅ Saved to approval queue. View at: http://localhost:8000/approvals")
        logger.info(f"✅ Saved to approval queue. View at: http://localhost:8000/approvals")
        
        return f"""✅ **All information collected!**

{preview}

---

🔐 **Approval Required**

This {operation} operation requires manual approval for security.

**Approval ID:** `{approval_id[:8]}...`

**Next Steps:**
1. Review the details above
2. Go to the **[Approval Queue](/approvals)** to approve or reject
3. Or click here: http://localhost:8000/approvals

*Note: Direct write operations require explicit approval to prevent unauthorized changes to your Jira instance.*

**What I can help with while you wait:**
- ✅ Search and view Jira issues
- ✅ Analyze project data and metrics  
- ✅ Query knowledge graph relationships
- ✅ Search Confluence documentation"""
    
    def _validate_project(self, project_key: str) -> Dict[str, Any]:
        """Validate that a project exists and suggest similar ones if not found"""
        logger.info(f"🔍 Validating project: {project_key}")
        
        # Check for exact match
        exact_match = jira_service.find_project(project_key)
        if exact_match:
            logger.info(f"✅ Project found: {exact_match['key']} - {exact_match['name']}")
            return {
                'status': 'valid',
                'project_key': exact_match['key'],
                'project_name': exact_match['name']
            }
        
        # Not found - find similar projects
        logger.warning(f"⚠️ Project '{project_key}' not found, searching for similar projects...")
        similar = jira_service.find_similar_projects(project_key, limit=5)
        
        if similar:
            suggestions = "\n".join([f"- **{p['key']}** - {p['name']}" for p in similar])
            message = f"""❌ **Project '{project_key}' not found**

Did you mean one of these?

{suggestions}

Please type the exact project key you want to use (e.g., `{similar[0]['key']}`), or type a different project name."""
            
            return {
                'status': 'not_found',
                'message': message,
                'suggestions': similar
            }
        else:
            # No similar projects found
            all_projects = jira_service.get_all_projects()[:10]  # Show first 10
            if all_projects:
                project_list = "\n".join([f"- **{p['key']}** - {p['name']}" for p in all_projects])
                message = f"""❌ **Project '{project_key}' not found**

No similar projects found. Here are some available projects:

{project_list}

Please type the exact project key you want to use."""
            else:
                message = f"""❌ **Project '{project_key}' not found**

Unable to retrieve available projects. Please check with your Jira administrator."""
            
            return {
                'status': 'not_found',
                'message': message
            }
    
    def _search_and_suggest_issues(self, search_term: str, project: Optional[str] = None) -> Dict[str, Any]:
        """Search for issues and return suggestions, prioritizing knowledge graph (RAG)"""
        logger.info(f"🔍 Searching for issues: '{search_term}' in project: {project}")
        
        try:
            # FIRST: Search in Knowledge Graph (faster, local)
            logger.info("📊 Searching Knowledge Graph first...")
            kg_results = knowledge_graph_service.search_by_text(search_term, entity_type="jira_issue", limit=5)
            
            # Filter by project if specified
            if project and kg_results:
                kg_results = [r for r in kg_results if r['properties'].get('project') == project]
            
            if kg_results:
                logger.info(f"✅ Found {len(kg_results)} matches in Knowledge Graph")
                
                # Always show suggestions (1-5 matches) - let user see and choose
                suggestions = []
                for result in kg_results:
                    props = result['properties']
                    summary = props.get('summary', 'No summary')
                    status = props.get('status', 'Unknown')
                    issue_type = props.get('issue_type', '')
                    type_emoji = '📦' if issue_type == 'Epic' else '📋'
                    suggestions.append(f"{type_emoji} **{result['id']}**: {summary} ({status})")
                
                message = f"""🔍 **Found {len(kg_results)} matching issue{'s' if len(kg_results) > 1 else ''} in Knowledge Graph:**

{chr(10).join(suggestions)}

Please type the issue key you want to update (e.g., `{kg_results[0]['id']}`), or provide more details to narrow down the search."""
                
                return {
                    'status': 'suggestions',
                    'message': message,
                    'suggestions': kg_results,
                    'source': 'knowledge_graph'
                }
            
            # SECOND: If not found in KG, search Jira directly
            logger.info("📝 Knowledge Graph didn't have matches, searching Jira...")
            
            # Build search query
            if project:
                jql = f'project = {project} AND (summary ~ "{search_term}" OR description ~ "{search_term}" OR key ~ "{search_term}") ORDER BY updated DESC'
            else:
                jql = f'(summary ~ "{search_term}" OR description ~ "{search_term}" OR key ~ "{search_term}") ORDER BY updated DESC'
            
            results = jira_service.search_issues(jql, max_results=5)
            
            if not results:
                logger.warning(f"⚠️ No issues found in KG or Jira for '{search_term}'")
                return {'status': 'not_found'}
            
            # Add found issues to knowledge graph for future searches
            logger.info(f"💾 Adding {len(results)} issues to Knowledge Graph for future searches")
            for issue in results:
                knowledge_graph_service.add_jira_issue(issue)
            
            if len(results) == 1:
                # Only one match - use it
                return {
                    'status': 'found',
                    'issue_key': results[0]['key'],
                    'source': 'jira'
                }
            
            # Multiple matches - show suggestions
            suggestions = []
            for issue in results:
                suggestions.append(f"- **{issue['key']}**: {issue['summary']} ({issue['status']})")
            
            message = f"""🔍 **Found {len(results)} matching issues:**

{chr(10).join(suggestions)}

Please type the issue key you want to update (e.g., `{results[0]['key']}`), or provide more details to narrow down the search."""
            
            return {
                'status': 'suggestions',
                'message': message,
                'suggestions': results,
                'source': 'jira'
            }
            
        except Exception as e:
            logger.error(f"Error searching issues: {e}")
            return {'status': 'error'}
    
    def _improve_summary(self, raw_summary: str, issue_type: str) -> str:
        """Use AI to improve a raw summary into a proper Jira issue title"""
        # Skip improvement if summary is already good (capitalized, no filler words at start)
        if raw_summary[0].isupper() and not raw_summary.lower().startswith(('about ', 'for ', 'to ')):
            return raw_summary
        
        try:
            prompt = f"""Convert this raw text into a professional Jira {issue_type} title.

Raw text: "{raw_summary}"

Rules:
- Remove filler words like "about", "for", "to" from the beginning
- Capitalize properly
- Be concise and action-oriented
- Maximum 10 words
- Return ONLY the improved title, no explanation

Improved title:"""
            
            response = self.llm.invoke(prompt)
            improved = response.content.strip().strip('"')
            
            # Validate the improvement
            if len(improved) > 0 and len(improved) < 150:
                logger.info(f"📝 Improved summary: '{raw_summary}' -> '{improved}'")
                return improved
        except Exception as e:
            logger.warning(f"Failed to improve summary: {e}")
        
        # Fallback: basic cleanup
        improved = re.sub(r'^(about|for|to)\s+', '', raw_summary, flags=re.IGNORECASE)
        improved = improved[0].upper() + improved[1:] if improved else raw_summary
        return improved
    
    def _extract_optional_batch(self, message: str, collected_info: Dict[str, Any]) -> None:
        """Extract multiple optional fields from a single message"""
        message_lower = message.lower()
        
        # Extract description (longest text, or after "description:")
        desc_patterns = [
            r'description[:\s]+([^.]+(?:\.[^.]+)?)',
            r'desc[:\s]+([^.]+)',
        ]
        for pattern in desc_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                collected_info['description'] = match.group(1).strip()
                break
        
        # Extract priority
        priorities = ['highest', 'high', 'medium', 'low', 'lowest']
        for priority in priorities:
            if priority in message_lower:
                collected_info['priority'] = priority.title()
                break
        
        # Extract assignee
        assignee_patterns = [
            r'assign(?:ee)?[:\s]+([A-Za-z][A-Za-z0-9._@-]+)',
            r'assign to ([A-Za-z][A-Za-z0-9._@-]+)',
        ]
        for pattern in assignee_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                collected_info['assignee'] = match.group(1).strip()
                break
        
        # Extract labels
        labels_patterns = [
            r'labels?[:\s]+([A-Za-z0-9,\s-]+)',
            r'tags?[:\s]+([A-Za-z0-9,\s-]+)',
        ]
        for pattern in labels_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                labels_str = match.group(1).strip()
                collected_info['labels'] = [l.strip() for l in labels_str.split(',')]
                break
        
        logger.info(f"📦 Extracted from batch: description={bool(collected_info.get('description'))}, "
                   f"priority={collected_info.get('priority')}, assignee={collected_info.get('assignee')}, "
                   f"labels={collected_info.get('labels')}")
    
    def _generate_operation_preview(self, operation: str, details: Dict[str, Any]) -> str:
        """Generate a preview of what the operation will do"""
        if operation == 'create':
            preview_lines = ["**📝 Create Operation Preview:**\n"]
            preview_lines.append(f"**Type:** {details.get('issue_type', 'Unknown')}")
            preview_lines.append(f"**Project:** {details.get('project', 'Unknown')}")
            preview_lines.append(f"**Summary:** {details.get('summary', 'No summary')}")
            
            if details.get('description'):
                desc = details['description'][:100] + '...' if len(details.get('description', '')) > 100 else details['description']
                preview_lines.append(f"**Description:** {desc}")
            
            if details.get('priority'):
                preview_lines.append(f"**Priority:** {details['priority']}")
            
            if details.get('assignee'):
                preview_lines.append(f"**Assignee:** {details['assignee']}")
            
            if details.get('labels'):
                labels = ', '.join(details['labels']) if isinstance(details['labels'], list) else details['labels']
                preview_lines.append(f"**Labels:** {labels}")
            
            return '\n'.join(preview_lines)
        
        elif operation == 'update':
            preview_lines = ["**✏️ Update Operation Preview:**\n"]
            preview_lines.append(f"**Issue:** `{details.get('issue_key', 'Unknown')}`")
            preview_lines.append(f"**Field:** {details.get('field', 'Unknown').title()}")
            preview_lines.append(f"**New Value:** {details.get('value', 'Unknown')}")
            return '\n'.join(preview_lines)
        
        elif operation == 'delete':
            return f"**🗑️ Delete Operation Preview:**\n\n**Issue:** `{details.get('issue_key', 'Unknown')}`"
        
        elif operation == 'transition':
            preview_lines = ["**🔄 Transition Operation Preview:**\n"]
            preview_lines.append(f"**Issue:** `{details.get('issue_key', 'Unknown')}`")
            preview_lines.append(f"**New Status:** {details.get('status', 'Unknown')}")
            return '\n'.join(preview_lines)
        
        else:
            return f"**Operation:** {operation}\n**Details:** {json.dumps(details, indent=2)}"
    
    def _answer_clarification_question(self, question: str, field: str, current_info: Dict[str, Any], operation: str) -> str:
        """Answer user's question about what they should provide"""
        question_lower = question.lower()
        
        if field == 'project':
            return f"""📋 **About Project Keys:**

The project key is a short code (usually 2-10 uppercase letters) that identifies your Jira project.

Examples: ACTHUB, LIFEOPS, PROJ, SE

**Where to find it:**
- Look at existing issue keys (e.g., **ACTHUB**-123)
- Check your Jira project list
- Ask your team lead

What's your project key?"""
        
        # Generic response
        return f"""❓ I'm here to help! 

For **{field.replace('_', ' ')}**: {self._ask_clarification_question(field, operation, current_info)}

Just provide the value, and we'll continue!"""


ai_agent_service = AIAgentService()

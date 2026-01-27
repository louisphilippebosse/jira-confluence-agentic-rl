from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from typing import Dict, Any, List
import logging
import json
import re

from app.config import settings
from app.services.jira_service import jira_service
from app.services.confluence_service import confluence_service
from app.services.knowledge_graph_service import knowledge_graph_service

logger = logging.getLogger(__name__)


class AIAgentService:
    """Agentic AI system for delivery intelligence and decision support with Knowledge Graph RAG"""
    
    def __init__(self):
        self.llm = self._initialize_llm()
    
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
        """Build a JQL query from natural language message"""
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
    
    async def chat(self, message: str, session_id: str, conversation_history: List = None, recommended_action: str = None) -> str:
        """Process a chat message and return response with intelligent tool routing and conversation memory
        
        Args:
            message: User message
            session_id: Session identifier
            conversation_history: Previous conversation messages
            recommended_action: Optional RL-recommended action to bias tool selection
        """
        try:
            logger.info(f"📨 Processing message: {message[:100]}...")
            if recommended_action:
                logger.info(f"🧠 RL recommends action: {recommended_action}")
            
            # Build conversation context from history (last 10 messages)
            context = ""
            if conversation_history and len(conversation_history) > 1:
                recent_history = conversation_history[-10:]  # Last 10 messages
                context = "\n\nConversation History:\n"
                for msg in recent_history:
                    context += f"{msg.role.capitalize()}: {msg.content[:200]}\n"
                logger.info(f"💭 Including {len(recent_history)} previous messages for context")
            
            # Use RL recommendation if available, otherwise fall back to keyword detection
            should_use_jira = (recommended_action in ["search_jira", "get_jira_issue", "get_child_issues"]) or self._should_search_jira(message)
            
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
                    # Build and execute JQL search
                    jql = self._build_jql_from_message(message)
                    logger.info(f"🔍 Built JQL query: {jql}")
                    jira_result = self._search_jira_issues(jql)
                
                logger.info(f"✅ Jira query completed, formatting response...")
                
                # Have LLM format the results nicely with context
                prompt = f"""User asked: {message}
{context}
Jira data retrieved:
{jira_result}

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
            elif any(word in message.lower() for word in ['confluence', 'documentation', 'docs', 'wiki', 'guide']):
                logger.info("📚 Detected Confluence query - routing to Confluence service")
                confluence_result = self._search_confluence(message)
                
                prompt = f"""User asked: {message}
{context}
Confluence data retrieved:
{confluence_result}

Please provide a clear, helpful response based on this Confluence data."""
                
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


ai_agent_service = AIAgentService()

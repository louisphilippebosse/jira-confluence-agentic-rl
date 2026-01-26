from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from typing import Dict, Any, List
import logging
import json

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
    
    async def chat(self, message: str, session_id: str) -> str:
        """Process a chat message and return response with Knowledge Graph RAG"""
        try:
            # Get knowledge graph context for RAG
            kg_context = self._get_knowledge_graph_context(message)
            
            # System prompt that guides the AI
            system_message = f"""You are an intelligent AI assistant specialized in delivery intelligence and decision support for engineering teams. 

You have access to:
- Jira (read-only) for issue tracking and project management
- Confluence (read-only) for documentation
- Knowledge Graph with relationships between issues, users, and documentation

Current Knowledge Graph Context:
{kg_context}

You can help with:
- Analyzing project delivery metrics and sprint progress
- Providing insights on team performance and blockers
- Searching and summarizing technical documentation
- Identifying risks and recommending actions
- Answering questions about project status and planning
- Finding relationships between issues, users, and documentation

When users ask about specific Jira issues, projects, or Confluence documentation, provide helpful guidance on how to use the system.

Always be helpful, professional, and provide actionable insights. Use the knowledge graph to provide context-aware responses.

Security note: You only have READ access to Jira and Confluence. You cannot create, modify, or delete any data."""

            # Create the full prompt
            full_prompt = f"{system_message}\n\nUser: {message}\n\nAssistant:"
            
            # Get response from LLM
            response = self.llm.invoke(full_prompt)
            return response.content
            
        except Exception as e:
            logger.error(f"Error in chat processing: {e}")
            return f"I apologize, but an error occurred: {str(e)}"


ai_agent_service = AIAgentService()

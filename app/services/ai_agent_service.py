from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.tools import Tool
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from langchain_community.chat_message_histories import SQLChatMessageHistory
from typing import Dict, Any, List
import logging
import json

from app.config import settings
from app.services.jira_service import jira_service
from app.services.confluence_service import confluence_service

logger = logging.getLogger(__name__)


class AIAgentService:
    """Agentic AI system for delivery intelligence and decision support"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.7,
            api_key=settings.openai_api_key
        )
        self.tools = self._create_tools()
    
    def _create_tools(self) -> List[Tool]:
        """Create tools for the AI agent to use"""
        return [
            Tool(
                name="search_jira_issues",
                func=self._search_jira_wrapper,
                description="Search Jira issues using JQL (Jira Query Language). Input should be a JQL query string. Example: 'project = PROJ AND status = Open'"
            ),
            Tool(
                name="get_jira_issue_details",
                func=self._get_jira_issue_wrapper,
                description="Get detailed information about a specific Jira issue. Input should be the issue key (e.g., 'PROJ-123')"
            ),
            Tool(
                name="search_confluence",
                func=self._search_confluence_wrapper,
                description="Search Confluence documentation. Input should be a search query string."
            ),
            Tool(
                name="get_confluence_page",
                func=self._get_confluence_page_wrapper,
                description="Get content from a specific Confluence page. Input should be the page ID."
            ),
            Tool(
                name="analyze_delivery_metrics",
                func=self._analyze_delivery_metrics,
                description="Analyze delivery metrics for a project. Input should be the project key."
            ),
        ]
    
    def _search_jira_wrapper(self, query: str) -> str:
        """Wrapper for Jira search tool"""
        try:
            results = jira_service.search_issues(query, max_results=20)
            if not results:
                return "No issues found matching your query."
            return json.dumps(results, indent=2)
        except Exception as e:
            logger.error(f"Error in Jira search: {e}")
            return f"Error searching Jira: {str(e)}"
    
    def _get_jira_issue_wrapper(self, issue_key: str) -> str:
        """Wrapper for getting Jira issue details"""
        try:
            result = jira_service.get_issue(issue_key.strip())
            if not result:
                return f"Issue {issue_key} not found."
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error getting Jira issue: {e}")
            return f"Error getting issue: {str(e)}"
    
    def _search_confluence_wrapper(self, query: str) -> str:
        """Wrapper for Confluence search tool"""
        try:
            results = confluence_service.search_content(query, limit=10)
            if not results:
                return "No Confluence pages found matching your query."
            return json.dumps(results, indent=2)
        except Exception as e:
            logger.error(f"Error in Confluence search: {e}")
            return f"Error searching Confluence: {str(e)}"
    
    def _get_confluence_page_wrapper(self, page_id: str) -> str:
        """Wrapper for getting Confluence page content"""
        try:
            result = confluence_service.get_page(page_id.strip())
            if not result:
                return f"Page {page_id} not found."
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error getting Confluence page: {e}")
            return f"Error getting page: {str(e)}"
    
    def _analyze_delivery_metrics(self, project_key: str) -> str:
        """Analyze delivery metrics for a project"""
        try:
            issues = jira_service.get_project_issues(project_key.strip(), max_results=100)
            if not issues:
                return f"No issues found for project {project_key}"
            
            # Calculate basic metrics
            total = len(issues)
            status_counts = {}
            for issue in issues:
                status = issue.get("status", "Unknown")
                status_counts[status] = status_counts.get(status, 0) + 1
            
            metrics = {
                "project": project_key,
                "total_issues": total,
                "status_breakdown": status_counts,
                "completion_rate": f"{(status_counts.get('Done', 0) / total * 100):.1f}%" if total > 0 else "0%"
            }
            
            return json.dumps(metrics, indent=2)
        except Exception as e:
            logger.error(f"Error analyzing delivery metrics: {e}")
            return f"Error analyzing metrics: {str(e)}"
    
    def create_agent(self, session_id: str) -> AgentExecutor:
        """Create an agent with conversation memory"""
        
        # System prompt for the agent
        system_prompt = """You are an intelligent AI assistant specialized in delivery intelligence and decision support for engineering teams. 

You have access to Jira and Confluence (read-only) and can help with:
- Analyzing project delivery metrics and sprint progress
- Providing insights on team performance and blockers
- Searching and summarizing technical documentation
- Identifying risks and recommending actions
- Answering questions about project status and planning

Always be helpful, professional, and provide actionable insights. When analyzing data, provide clear summaries and recommendations. If you don't have access to specific data, acknowledge it and suggest what information would be helpful.

Security note: You only have READ access to Jira and Confluence. You cannot create, modify, or delete any data."""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        agent = create_openai_functions_agent(self.llm, self.tools, prompt)
        
        # Use SQL-based memory for persistence
        message_history = SQLChatMessageHistory(
            session_id=session_id,
            connection_string=settings.database_url.replace("sqlite:///", "sqlite:///")
        )
        
        memory = ConversationBufferMemory(
            chat_memory=message_history,
            memory_key="chat_history",
            return_messages=True,
            output_key="output"
        )
        
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            memory=memory,
            verbose=True,
            return_intermediate_steps=False,
            max_iterations=5,
            handle_parsing_errors=True
        )
    
    async def chat(self, message: str, session_id: str) -> str:
        """Process a chat message and return response"""
        try:
            agent_executor = self.create_agent(session_id)
            response = agent_executor.invoke({"input": message})
            return response.get("output", "I apologize, but I couldn't process your request.")
        except Exception as e:
            logger.error(f"Error in chat processing: {e}")
            return f"I apologize, but an error occurred: {str(e)}"


ai_agent_service = AIAgentService()

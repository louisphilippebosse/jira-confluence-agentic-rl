# Services package

"""Services package for the application

Domain-based structure:
- core: Orchestration and coordination
- tools: Integration tools (Jira, Confluence, Web)
- intelligence: AI/LLM-powered services
- graphrag: Graph + Vector RAG services
"""

# Re-export commonly used services for convenience
from app.services.core import agent_orchestrator
from app.services.tools.jira.jira_service import jira_service
from app.services.tools.confluence.confluence_service import confluence_service
from app.services.tools.web.web_search_service import web_search_service
from app.services.intelligence import QueryAnalyzerService, JiraQueryBuilder, ResultVerifier
from app.services.graphrag import knowledge_graph_service, rl_service

__all__ = [
    'agent_orchestrator',
    'jira_service',
    'confluence_service',
    'web_search_service',
    'knowledge_graph_service',
    'rl_service',
    'QueryAnalyzerService',
    'JiraQueryBuilder',
    'ResultVerifier',
]

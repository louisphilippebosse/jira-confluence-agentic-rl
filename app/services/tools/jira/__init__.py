"""
Jira Tool Package - All Jira-related code consolidated here.

This package provides:
- JiraTool: Implements BaseTool interface for Jira operations
- JiraService: Direct Jira API calls
- JiraQueryBuilder: JQL query construction
- JiraWriteService: Create/Update operations
- JiraIntentDetector: Jira-specific intent detection
"""
from .jira_tool import JiraTool
from .jira_intent import JiraIntentDetector
from .jira_service import JiraService, jira_service
from .jira_query_builder import JiraQueryBuilder
from .jira_write_service import JiraWriteService

__all__ = [
    "JiraTool",
    "JiraIntentDetector",
    "JiraService",
    "jira_service",
    "JiraQueryBuilder",
    "JiraWriteService",
]

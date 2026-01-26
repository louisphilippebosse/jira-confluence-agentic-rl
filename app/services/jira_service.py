from jira import JIRA
from typing import List, Dict, Any, Optional
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class JiraService:
    """Read-only Jira integration service"""
    
    def __init__(self):
        self._client = None
    
    @property
    def client(self):
        """Lazy initialization of Jira client"""
        if self._client is None:
            try:
                self._client = JIRA(
                    server=settings.jira_url,
                    basic_auth=(settings.jira_username, settings.jira_api_token),
                    timeout=5
                )
                logger.info("Jira client initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Jira client: {e}")
                self._client = False  # Mark as failed
        return self._client if self._client is not False else None
    
    def search_issues(self, jql: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Search Jira issues using JQL (read-only)"""
        if not self.client:
            return []
        
        try:
            issues = self.client.search_issues(jql, maxResults=max_results)
            return [
                {
                    "key": issue.key,
                    "summary": issue.fields.summary,
                    "status": issue.fields.status.name,
                    "assignee": issue.fields.assignee.displayName if issue.fields.assignee else "Unassigned",
                    "created": str(issue.fields.created),
                    "updated": str(issue.fields.updated),
                    "priority": issue.fields.priority.name if issue.fields.priority else "None",
                }
                for issue in issues
            ]
        except Exception as e:
            logger.error(f"Error searching Jira issues: {e}")
            return []
    
    def get_issue(self, issue_key: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific issue"""
        if not self.client:
            return None
        
        try:
            issue = self.client.issue(issue_key)
            return {
                "key": issue.key,
                "summary": issue.fields.summary,
                "description": issue.fields.description or "No description",
                "status": issue.fields.status.name,
                "assignee": issue.fields.assignee.displayName if issue.fields.assignee else "Unassigned",
                "reporter": issue.fields.reporter.displayName if issue.fields.reporter else "Unknown",
                "created": str(issue.fields.created),
                "updated": str(issue.fields.updated),
                "priority": issue.fields.priority.name if issue.fields.priority else "None",
                "labels": issue.fields.labels,
            }
        except Exception as e:
            logger.error(f"Error getting Jira issue {issue_key}: {e}")
            return None
    
    def get_project_issues(self, project_key: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """Get all issues for a specific project"""
        jql = f"project = {project_key} ORDER BY created DESC"
        return self.search_issues(jql, max_results)
    
    def get_sprint_issues(self, sprint_name: str) -> List[Dict[str, Any]]:
        """Get issues for a specific sprint"""
        jql = f'sprint = "{sprint_name}" ORDER BY status'
        return self.search_issues(jql)


jira_service = JiraService()

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
                logger.info(f"Initializing Jira client - URL: {settings.jira_url}, Username: {settings.jira_username}")
                self._client = JIRA(
                    server=settings.jira_url,
                    basic_auth=(settings.jira_username, settings.jira_api_token),
                    timeout=10  # Increased timeout
                )
                logger.info("✅ Jira client initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Jira client: {e}", exc_info=True)
                self._client = False  # Mark as failed
        return self._client if self._client is not False else None
    
    def search_issues(self, jql: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Search Jira issues using JQL (read-only)"""
        logger.info(f"🔍 Searching Jira with JQL: {jql}")
        
        if not self.client:
            logger.error("❌ Jira client is not available - check your credentials in .env")
            return []
        
        try:
            logger.info(f"Executing Jira search...")
            issues = self.client.search_issues(jql, maxResults=max_results)
            logger.info(f"✅ Found {len(issues)} issues")
            
            results = []
            for issue in issues:
                # Extract epic link if available
                epic_key = None
                if hasattr(issue.fields, 'customfield_10014'):  # Common epic link field
                    epic_key = issue.fields.customfield_10014
                elif hasattr(issue.fields, 'parent') and issue.fields.parent:
                    # Check if parent is an Epic
                    if hasattr(issue.fields.parent.fields, 'issuetype'):
                        if issue.fields.parent.fields.issuetype.name == 'Epic':
                            epic_key = issue.fields.parent.key
                
                # Extract parent key if available
                parent_key = None
                if hasattr(issue.fields, 'parent') and issue.fields.parent:
                    parent_key = issue.fields.parent.key
                
                issue_data = {
                    "key": issue.key,
                    "summary": issue.fields.summary,
                    "status": issue.fields.status.name,
                    "assignee": issue.fields.assignee.displayName if issue.fields.assignee else "Unassigned",
                    "reporter": issue.fields.reporter.displayName if issue.fields.reporter else "Unknown",
                    "created": str(issue.fields.created),
                    "updated": str(issue.fields.updated),
                    "priority": issue.fields.priority.name if issue.fields.priority else "None",
                    "issue_type": issue.fields.issuetype.name if hasattr(issue.fields, 'issuetype') else "Unknown",
                    "parent": parent_key,
                    "epic_key": epic_key,
                }
                results.append(issue_data)
            return results
        except Exception as e:
            logger.error(f"❌ Error searching Jira issues: {e}", exc_info=True)
            return []
    
    def get_issue(self, issue_key: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific issue"""
        logger.info(f"🔍 Getting Jira issue: {issue_key}")
        
        if not self.client:
            logger.error("❌ Jira client is not available")
            return None
        
        try:
            issue = self.client.issue(issue_key)
            logger.info(f"✅ Retrieved issue: {issue.key}")
            
            # Get subtasks/child issues
            subtasks = []
            if hasattr(issue.fields, 'subtasks') and issue.fields.subtasks:
                for subtask in issue.fields.subtasks:
                    subtasks.append({
                        "key": subtask.key,
                        "summary": subtask.fields.summary,
                        "status": subtask.fields.status.name
                    })
                logger.info(f"📎 Found {len(subtasks)} child issues")
            
            # Extract epic link
            epic_key = None
            if hasattr(issue.fields, 'customfield_10014'):
                epic_key = issue.fields.customfield_10014
            elif hasattr(issue.fields, 'parent') and issue.fields.parent:
                if hasattr(issue.fields.parent.fields, 'issuetype'):
                    if issue.fields.parent.fields.issuetype.name == 'Epic':
                        epic_key = issue.fields.parent.key
            
            # Extract parent key
            parent_key = None
            if hasattr(issue.fields, 'parent') and issue.fields.parent:
                parent_key = issue.fields.parent.key
            
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
                "issue_type": issue.fields.issuetype.name if hasattr(issue.fields, 'issuetype') else "Unknown",
                "parent": parent_key,
                "epic_key": epic_key,
                "subtasks": subtasks,
                "has_subtasks": len(subtasks) > 0
            }
        except Exception as e:
            logger.error(f"❌ Error getting Jira issue {issue_key}: {e}", exc_info=True)
            return None
    
    def get_child_issues(self, parent_key: str) -> List[Dict[str, Any]]:
        """Get all child issues (subtasks) of a parent issue"""
        logger.info(f"👶 Getting child issues for: {parent_key}")
        
        if not self.client:
            logger.error("❌ Jira client is not available")
            return []
        
        try:
            # Search for issues with this parent
            jql = f'parent = {parent_key} ORDER BY created DESC'
            return self.search_issues(jql, max_results=50)
        except Exception as e:
            logger.error(f"❌ Error getting child issues: {e}", exc_info=True)
            return []
    
    def get_project_issues(self, project_key: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """Get all issues for a specific project"""
        jql = f"project = {project_key} ORDER BY created DESC"
        return self.search_issues(jql, max_results)
    
    def get_sprint_issues(self, sprint_name: str) -> List[Dict[str, Any]]:
        """Get issues for a specific sprint"""
        jql = f'sprint = "{sprint_name}" ORDER BY status'
        return self.search_issues(jql)
    
    def create_issue(self, project_key: str, summary: str, issue_type: str = "Task", 
                    description: str = "", parent_key: Optional[str] = None,
                    assignee: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Create a new Jira issue (WRITE operation - requires approval)"""
        logger.info(f"📝 Creating Jira issue in {project_key}: {summary}")
        
        if not self.client:
            logger.error("❌ Jira client is not available")
            return None
        
        try:
            fields = {
                'project': {'key': project_key},
                'summary': summary,
                'issuetype': {'name': issue_type},
            }
            
            if description:
                fields['description'] = description
            
            if parent_key:
                fields['parent'] = {'key': parent_key}
            
            if assignee:
                fields['assignee'] = {'name': assignee}
            
            new_issue = self.client.create_issue(fields=fields)
            
            result = {
                "key": new_issue.key,
                "summary": summary,
                "status": "To Do",
                "issue_type": issue_type,
                "url": f"{self.client._options['server']}/browse/{new_issue.key}"
            }
            
            logger.info(f"✅ Created issue {new_issue.key}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error creating issue: {e}", exc_info=True)
            return None
    
    def update_issue(self, issue_key: str, fields: Dict[str, Any]) -> bool:
        """Update an existing Jira issue (WRITE operation - requires approval)"""
        logger.info(f"✏️ Updating Jira issue {issue_key}")
        
        if not self.client:
            logger.error("❌ Jira client is not available")
            return False
        
        try:
            issue = self.client.issue(issue_key)
            issue.update(fields=fields)
            
            logger.info(f"✅ Updated issue {issue_key}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating issue: {e}", exc_info=True)
            return False
    
    def transition_issue(self, issue_key: str, transition_name: str) -> bool:
        """Transition issue to a new status (WRITE operation - requires approval)"""
        logger.info(f"🔄 Transitioning {issue_key} to {transition_name}")
        
        if not self.client:
            logger.error("❌ Jira client is not available")
            return False
        
        try:
            issue = self.client.issue(issue_key)
            transitions = self.client.transitions(issue)
            
            # Find the transition ID by name
            transition_id = None
            for t in transitions:
                if t['name'].lower() == transition_name.lower():
                    transition_id = t['id']
                    break
            
            if not transition_id:
                logger.error(f"❌ Transition '{transition_name}' not found")
                return False
            
            self.client.transition_issue(issue, transition_id)
            logger.info(f"✅ Transitioned {issue_key} to {transition_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error transitioning issue: {e}", exc_info=True)
            return False


jira_service = JiraService()

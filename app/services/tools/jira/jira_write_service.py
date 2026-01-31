"""
Jira Write Service - Handles Jira write operations with approval workflows.

This module was moved from orchestration/ to tools/jira/ for better
semantic organization. All Jira-related code is now in one place.
"""
from typing import Dict, Any, List, Optional
import logging
import json
import re
import uuid
from datetime import datetime

from .jira_service import jira_service
from app.services.graphrag.knowledge_graph_service import knowledge_graph_service

logger = logging.getLogger(__name__)


class JiraWriteService:
    """Handles all Jira write operations with validation and approval workflows"""
    
    def __init__(self, llm=None):
        """Initialize with optional LLM for intelligent summary improvement and suggestions"""
        self.llm = llm
    
    def extract_operation_details(self, message: str, operation: str) -> Dict[str, Any]:
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
                        groups = match.groups()
                        search_term = groups[-1].strip() if groups else ''
                        search_term = re.sub(r'\s+(to|in|for|the)$', '', search_term, flags=re.IGNORECASE)
                        if search_term:
                            details['issue_search'] = search_term
                            logger.info(f"Extracted search term: '{search_term}'")
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
            
            # Extract summary/title
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
                    summary = re.sub(r'\s+(in|for)$', '', summary, flags=re.IGNORECASE)
                    summary = self.improve_summary(summary, details.get('issue_type', 'Task'))
                    details['summary'] = summary
                    break
        
        # Extract project key
        proj_match = re.search(r'\b([A-Z]{2,})-?\d*\b', message)
        if proj_match:
            project_key = proj_match.group(1)
            if project_key not in ['TEST', 'NEW', 'CREATE']:
                details['project'] = project_key
        
        proj_keywords = re.search(r'(?:project|in) ([A-Z]{2,10})', message, re.IGNORECASE)
        if proj_keywords:
            details['project'] = proj_keywords.group(1).upper()
        
        # Extract description
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
        
        logger.info(f"Extracted from message: {details}")
        return details
    
    def get_required_fields(self, operation: str, issue_type: Optional[str] = None) -> List[str]:
        """Get list of required fields based on operation and issue type"""
        if operation == 'create':
            return ['project', 'issue_type', 'summary']
        elif operation == 'update':
            return ['issue_key', 'field', 'value']
        elif operation == 'delete':
            return ['issue_key', 'confirmation']
        elif operation == 'transition':
            return ['issue_key', 'status']
        return []
    
    def validate_project(self, project_key: str) -> Dict[str, Any]:
        """Validate that a project exists and suggest similar ones if not found"""
        logger.info(f"Validating project: {project_key}")
        
        exact_match = jira_service.find_project(project_key)
        if exact_match:
            logger.info(f"Project found: {exact_match['key']} - {exact_match['name']}")
            return {
                'status': 'valid',
                'project_key': exact_match['key'],
                'project_name': exact_match['name']
            }
        
        logger.warning(f"Project '{project_key}' not found, searching for similar projects...")
        similar = jira_service.find_similar_projects(project_key, limit=5)
        
        if similar:
            suggestions = "\n".join([f"- **{p['key']}** - {p['name']}" for p in similar])
            message = f"""Project '{project_key}' not found

Did you mean one of these?

{suggestions}

Please type the exact project key you want to use (e.g., `{similar[0]['key']}`), or type a different project name."""
            
            return {
                'status': 'not_found',
                'message': message,
                'suggestions': similar
            }
        else:
            all_projects = jira_service.get_all_projects()[:10]
            if all_projects:
                project_list = "\n".join([f"- **{p['key']}** - {p['name']}" for p in all_projects])
                message = f"""Project '{project_key}' not found

No similar projects found. Here are some available projects:

{project_list}

Please type the exact project key you want to use."""
            else:
                message = f"""Project '{project_key}' not found

Unable to retrieve available projects. Please check with your Jira administrator."""
            
            return {
                'status': 'not_found',
                'message': message
            }
    
    def search_and_suggest_issues(self, search_term: str, project: Optional[str] = None) -> Dict[str, Any]:
        """Search for issues and return suggestions, prioritizing knowledge graph (RAG)"""
        logger.info(f"Searching for issues: '{search_term}' in project: {project}")
        
        try:
            # FIRST: Search in Knowledge Graph (faster, local)
            logger.info("Searching Knowledge Graph first...")
            kg_results = knowledge_graph_service.search_by_text(search_term, entity_type="jira_issue", limit=5)
            
            if project and kg_results:
                kg_results = [r for r in kg_results if r['properties'].get('project') == project]
            
            if kg_results:
                logger.info(f"Found {len(kg_results)} matches in Knowledge Graph")
                
                suggestions = []
                for result in kg_results:
                    props = result['properties']
                    summary = props.get('summary', 'No summary')
                    status = props.get('status', 'Unknown')
                    issue_type = props.get('issue_type', '')
                    type_emoji = 'Epic' if issue_type == 'Epic' else 'Issue'
                    suggestions.append(f"**{result['id']}**: {summary} ({status})")
                
                message = f"""Found {len(kg_results)} matching issue{'s' if len(kg_results) > 1 else ''} in Knowledge Graph:

{chr(10).join(suggestions)}

Please type the issue key you want to update (e.g., `{kg_results[0]['id']}`), or provide more details to narrow down the search."""
                
                return {
                    'status': 'suggestions',
                    'message': message,
                    'suggestions': kg_results,
                    'source': 'knowledge_graph'
                }
            
            # SECOND: Search Jira directly
            logger.info("Knowledge Graph didn't have matches, searching Jira...")
            
            if project:
                jql = f'project = {project} AND (summary ~ "{search_term}" OR description ~ "{search_term}" OR key ~ "{search_term}") ORDER BY updated DESC'
            else:
                jql = f'(summary ~ "{search_term}" OR description ~ "{search_term}" OR key ~ "{search_term}") ORDER BY updated DESC'
            
            results = jira_service.search_issues(jql, max_results=5)
            
            if not results:
                logger.warning(f"No issues found in KG or Jira for '{search_term}'")
                return {'status': 'not_found'}
            
            logger.info(f"Adding {len(results)} issues to Knowledge Graph for future searches")
            for issue in results:
                knowledge_graph_service.add_jira_issue(issue)
            
            if len(results) == 1:
                return {
                    'status': 'found',
                    'issue_key': results[0]['key'],
                    'source': 'jira'
                }
            
            suggestions = []
            for issue in results:
                suggestions.append(f"- **{issue['key']}**: {issue['summary']} ({issue['status']})")
            
            message = f"""Found {len(results)} matching issues:

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
    
    def improve_summary(self, raw_summary: str, issue_type: str) -> str:
        """Use AI to improve a raw summary into a proper Jira issue title"""
        if not self.llm:
            # Fallback: basic cleanup
            improved = re.sub(r'^(about|for|to)\s+', '', raw_summary, flags=re.IGNORECASE)
            improved = improved[0].upper() + improved[1:] if improved else raw_summary
            return improved
        
        # Skip if already good
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
            
            if len(improved) > 0 and len(improved) < 150:
                logger.info(f"Improved summary: '{raw_summary}' -> '{improved}'")
                return improved
        except Exception as e:
            logger.warning(f"Failed to improve summary: {e}")
        
        # Fallback
        improved = re.sub(r'^(about|for|to)\s+', '', raw_summary, flags=re.IGNORECASE)
        improved = improved[0].upper() + improved[1:] if improved else raw_summary
        return improved
    
    def create_approval_request(self, session_id: str, operation: str, details: Dict[str, Any]) -> str:
        """Create an approval request that will appear in the UI"""
        from app.api.approvals import pending_approvals
        
        approval_id = str(uuid.uuid4())
        preview = self.generate_operation_preview(operation, details)
        
        # Map field names to Jira API format
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
            jira_parameters = {'issue_key': details.get('issue_key')}
        elif operation == 'transition':
            jira_parameters = {
                'issue_key': details.get('issue_key'),
                'status': details.get('status')
            }
        else:
            jira_parameters = {}
        
        jira_parameters = {k: v for k, v in jira_parameters.items() if v is not None}
        
        approval_data = {
            "id": approval_id,
            "action": f"{operation}_jira_issue",
            "parameters": jira_parameters,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "preview": details
        }
        pending_approvals[approval_id] = approval_data
        
        logger.info(f"APPROVAL REQUEST CREATED: {approval_id}")
        logger.info(f"Saved to approval queue. View at: http://localhost:8000/approvals")
        
        return f"""**All information collected!**

{preview}

---

**Approval Required**

This {operation} operation requires manual approval for security.

**Approval ID:** `{approval_id[:8]}...`

**Next Steps:**
1. Review the details above
2. Go to the **[Approval Queue](/approvals)** to approve or reject
3. Or click here: http://localhost:8000/approvals

*Note: Direct write operations require explicit approval to prevent unauthorized changes to your Jira instance.*

**What I can help with while you wait:**
- Search and view Jira issues
- Analyze project data and metrics  
- Query knowledge graph relationships
- Search Confluence documentation"""
    
    def generate_operation_preview(self, operation: str, details: Dict[str, Any]) -> str:
        """Generate a preview of what the operation will do"""
        if operation == 'create':
            preview_lines = ["**Create Operation Preview:**\n"]
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
            preview_lines = ["**Update Operation Preview:**\n"]
            preview_lines.append(f"**Issue:** `{details.get('issue_key', 'Unknown')}`")
            preview_lines.append(f"**Field:** {details.get('field', 'Unknown').title()}")
            preview_lines.append(f"**New Value:** {details.get('value', 'Unknown')}")
            return '\n'.join(preview_lines)
        
        elif operation == 'delete':
            return f"**Delete Operation Preview:**\n\n**Issue:** `{details.get('issue_key', 'Unknown')}`"
        
        elif operation == 'transition':
            preview_lines = ["**Transition Operation Preview:**\n"]
            preview_lines.append(f"**Issue:** `{details.get('issue_key', 'Unknown')}`")
            preview_lines.append(f"**New Status:** {details.get('status', 'Unknown')}")
            return '\n'.join(preview_lines)
        
        else:
            return f"**Operation:** {operation}\n**Details:** {json.dumps(details, indent=2)}"

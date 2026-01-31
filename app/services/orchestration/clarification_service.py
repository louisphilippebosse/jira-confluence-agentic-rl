"""Clarification workflow for interactive dialog management"""
from typing import Dict, Any, Optional
import logging
import re

from app.services.tools.jira.jira_service import jira_service
from app.services.graphrag.knowledge_graph_service import knowledge_graph_service

logger = logging.getLogger(__name__)


class ClarificationService:
    """Handles interactive clarification dialogs for collecting missing information"""
    
    def __init__(self, llm=None, write_service=None):
        """Initialize with optional LLM for intelligent suggestions"""
        self.llm = llm
        self.write_service = write_service
    
    def ask_clarification_question(self, field: str, operation: str, current_info: Dict[str, Any]) -> str:
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
        
        # Build summary of collected info
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
    
    def generate_value_suggestions(self, message: str, operation: str, current_info: Dict[str, Any]) -> Dict[str, Any]:
        """Generate AI-powered suggestions for field values"""
        if not self.llm:
            return {'message': self.ask_clarification_question('value', operation, current_info)}
        
        issue_key = current_info.get('issue_key')
        field = current_info.get('field')
        
        if not issue_key or not field:
            return {'message': self.ask_clarification_question('value', operation, current_info)}
        
        try:
            issue_data = jira_service.get_issue(issue_key)
            if not issue_data:
                return {'message': f"❌ Couldn't find issue {issue_key}. Please provide the new value for {field}:"}
            
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
            
            # Extract detected field
            detected_field_match = re.search(r'^FIELD:\s*(\w+)', suggestion_content, re.IGNORECASE | re.MULTILINE)
            detected_field = detected_field_match.group(1) if detected_field_match else field
            
            display_content = re.sub(r'^FIELD:\s*\w+\s*\n', '', suggestion_content, flags=re.IGNORECASE | re.MULTILINE)
            
            # Parse numbered suggestions
            suggestions_list = []
            for line in display_content.split('\n'):
                line = line.strip()
                match = re.match(r'^[1-3][\.\)]\s*(.+?)(?:\s*[-–—]\s*.*)?$', line)
                if match:
                    suggestion = match.group(1).strip().strip('"\'')
                    suggestions_list.append(suggestion)
            
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
            return {'message': self.ask_clarification_question('value', operation, current_info)}
    
    def extract_field_value(self, message: str, field: str) -> Any:
        """Extract specific field value from user's response"""
        message = message.strip()
        message_lower = message.lower()
        
        if field in ['summary', 'description']:
            return message
        
        if field == 'project':
            match = re.search(r'\b([A-Z]{2,10})\b', message)
            return match.group(1) if match else message.upper() if len(message) <= 10 else None
        
        if field == 'issue_key':
            key_match = re.search(r'\b([A-Z]{2,10}-\d+)\b', message)
            return key_match.group(1) if key_match else None
        
        if field == 'issue_type':
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
            return 'Task'
        
        if field == 'priority':
            priorities = ['Highest', 'High', 'Medium', 'Low', 'Lowest']
            for priority in priorities:
                if priority.lower() in message_lower:
                    return priority
            return None
        
        if field == 'labels':
            return [label.strip() for label in message.split(',')]
        
        return message
    
    def extract_optional_batch(self, message: str, collected_info: Dict[str, Any]) -> None:
        """Extract multiple optional fields from a single message"""
        message_lower = message.lower()
        
        # Extract description
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
    
    def answer_clarification_question(self, question: str, field: str, current_info: Dict[str, Any], operation: str) -> str:
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
        
        return f"""❓ I'm here to help! 

For **{field.replace('_', ' ')}**: {self.ask_clarification_question(field, operation, current_info)}

Just provide the value, and we'll continue!"""

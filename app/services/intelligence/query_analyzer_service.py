"""
Query Analyzer Service - Analyzes user queries to determine intent and extract entities.
Follows Single Responsibility Principle.
"""
import re
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class QueryIntent:
    """Represents the analyzed intent of a user query"""
    is_child_query: bool = False
    is_followup_query: bool = False
    issue_keys: List[str] = None
    target_status: Optional[str] = None  # 'done', 'in progress', 'to do'
    parent_epic_name: Optional[str] = None
    
    def __post_init__(self):
        if self.issue_keys is None:
            self.issue_keys = []


class QueryAnalyzerService:
    """Analyzes user queries to extract intent, entities, and context"""
    
    def __init__(self):
        self.child_keywords = [
            'child', 'children', 'subtask', 'sub-task', 'sub task', 
            'child issue', 'child issues', 'subtasks'
        ]
    
    def extract_issue_keys(self, text: str) -> List[str]:
        """
        Extract Jira issue keys from text.
        
        Args:
            text: Text to search for issue keys
            
        Returns:
            List of unique issue keys found
        """
        if not text:
            return []
        
        # Match pattern: UPPERCASE-NUMBER (e.g., ACTHUB-9, PROJ-123)
        keys = re.findall(r'\b([A-Z]+-\d+)\b', text)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_keys = []
        for key in keys:
            if key not in seen:
                seen.add(key)
                unique_keys.append(key)
        
        return unique_keys
    
    def extract_single_issue_key(self, message: str) -> Optional[str]:
        """
        Extract a single issue key from message.
        
        Args:
            message: User message
            
        Returns:
            First issue key found, or None
        """
        keys = self.extract_issue_keys(message)
        return keys[0] if keys else None
    
    def is_asking_for_children(self, message: str) -> bool:
        """
        Check if user is asking for child/subtask issues.
        
        Args:
            message: User message
            
        Returns:
            True if asking for child issues
        """
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in self.child_keywords)
    
    def extract_parent_epic_name(self, message: str) -> Optional[str]:
        """
        Extract parent epic/issue name from queries like "child issues of X".
        
        Args:
            message: User message
            
        Returns:
            Extracted epic name or None
        """
        # Try pattern: "child issues of/for <name>"
        match = re.search(r'child issues? (?:of|for) ([^,?]+)', message, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        # Try fallback patterns
        for word in ['child issues', 'children of', 'subtasks of', 'tell me about']:
            if word in message.lower():
                parts = message.lower().split(word)
                if len(parts) > 1:
                    # Take text after the keyword until comma or question mark
                    remaining = parts[1].strip()
                    for separator in [',', '?', '.', '\n']:
                        if separator in remaining:
                            remaining = remaining[:remaining.index(separator)]
                    if remaining:
                        return remaining.strip()
        
        return None
    
    def detect_status_filter(self, message: str) -> Optional[str]:
        """
        Detect if user is filtering by status.
        
        Args:
            message: User message
            
        Returns:
            'done', 'in_progress', 'to_do', or None
        """
        message_lower = message.lower()
        
        if any(phrase in message_lower for phrase in ['in progress', 'doing', 'working on']):
            return 'in_progress'
        elif any(phrase in message_lower for phrase in ['done', 'completed', 'finished', 'closed']):
            return 'done'
        elif any(phrase in message_lower for phrase in ['to do', 'todo', 'pending', 'backlog', 'open']):
            return 'to_do'
        
        return None
    
    def detect_followup_context(
        self, 
        message: str, 
        conversation_history: List[Any]
    ) -> Dict[str, Any]:
        """
        Detect if this is a follow-up question referencing previous results.
        
        Args:
            message: Current user message
            conversation_history: Previous messages
            
        Returns:
            Dict with is_followup, target_keys, and target_status
        """
        message_lower = message.lower()
        is_followup = False
        target_keys = []
        target_status = None
        
        # Check for status-based references
        if conversation_history and any(phrase in message_lower for phrase in 
                                       ['in progress', 'to do', 'done', 'the ']):
            logger.info("🤔 Analyzing if this is a follow-up question...")
            
            # Extract all issue keys from recent conversation
            found_keys = []
            for msg in reversed(conversation_history[-5:]):
                if hasattr(msg, 'role') and msg.role == "assistant":
                    keys = self.extract_issue_keys(msg.content)
                    found_keys.extend(keys)
            
            # Remove duplicates
            found_keys = list(dict.fromkeys(found_keys))
            logger.info(f"🎯 Total unique keys found: {found_keys}")
            
            # Check for status-specific follow-ups
            if found_keys:
                # "in progress" follow-up
                if any(phrase in message_lower for phrase in ['in progress', 'the in progress']):
                    target_status = 'in_progress'
                    is_followup = True
                    # Extract keys from "In Progress" section
                    target_keys = self._extract_keys_from_status_section(
                        conversation_history, found_keys, 'In Progress'
                    )
                
                # "to do" follow-up
                elif any(phrase in message_lower for phrase in ['to do', 'the to do', 'todo']):
                    target_status = 'to_do'
                    is_followup = True
                    target_keys = self._extract_keys_from_status_section(
                        conversation_history, found_keys, 'To Do'
                    )
                
                # "done" follow-up
                elif any(phrase in message_lower for phrase in ['the done', 'done items', 'completed']):
                    target_status = 'done'
                    is_followup = True
                    target_keys = self._extract_keys_from_status_section(
                        conversation_history, found_keys, 'Done'
                    )
        
        return {
            'is_followup': is_followup,
            'target_keys': target_keys,
            'target_status': target_status,
            'found_keys': found_keys if is_followup else []
        }
    
    def _extract_keys_from_status_section(
        self, 
        conversation_history: List[Any], 
        found_keys: List[str],
        status_section: str
    ) -> List[str]:
        """
        Extract issue keys from a specific status section in conversation.
        
        Args:
            conversation_history: Previous messages
            found_keys: All issue keys found in conversation
            status_section: 'In Progress', 'To Do', or 'Done'
            
        Returns:
            List of issue keys in that section
        """
        target_keys = []
        
        for msg in reversed(conversation_history[-3:]):
            if hasattr(msg, 'role') and msg.role == "assistant":
                content = msg.content
                
                # Look for the status section
                section_start = content.lower().find(status_section.lower())
                if section_start != -1:
                    # Find the next section or end
                    next_section = float('inf')
                    for other_status in ['In Progress', 'To Do', 'Done', '##', '###']:
                        pos = content.find(other_status, section_start + len(status_section))
                        if pos != -1 and pos < next_section:
                            next_section = pos
                    
                    section_content = content[section_start:
                                             next_section if next_section != float('inf') else len(content)]
                    
                    # Extract keys from this section
                    for key in found_keys:
                        if key in section_content and key not in target_keys:
                            target_keys.append(key)
                            logger.info(f"📌 Found {key} in {status_section} section")
        
        return target_keys
    
    def analyze_query(
        self, 
        message: str, 
        conversation_history: Optional[List[Any]] = None
    ) -> QueryIntent:
        """
        Perform comprehensive query analysis.
        
        Args:
            message: User message
            conversation_history: Previous conversation messages
            
        Returns:
            QueryIntent with all detected attributes
        """
        intent = QueryIntent()
        
        # Extract issue keys
        intent.issue_keys = self.extract_issue_keys(message)
        
        # Check if asking for child issues
        intent.is_child_query = self.is_asking_for_children(message)
        
        # Extract parent epic name if asking for children
        if intent.is_child_query:
            intent.parent_epic_name = self.extract_parent_epic_name(message)
        
        # Detect status filter
        intent.target_status = self.detect_status_filter(message)
        
        # Detect follow-up context
        if conversation_history:
            followup_info = self.detect_followup_context(message, conversation_history)
            intent.is_followup_query = followup_info['is_followup']
            if followup_info['target_keys']:
                intent.issue_keys = followup_info['target_keys']
            if followup_info['target_status']:
                intent.target_status = followup_info['target_status']
        
        logger.info(f"📊 Query Analysis: child={intent.is_child_query}, "
                   f"followup={intent.is_followup_query}, keys={intent.issue_keys}, "
                   f"status={intent.target_status}")
        
        return intent

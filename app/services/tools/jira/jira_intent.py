"""
Jira Intent Detector - Detects when Jira tool should be used.

Encapsulates all Jira-specific intent detection logic that was
previously scattered in ai_agent_service.py.
"""
import re
import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class JiraIntentDetector:
    """
    Detects if a user message is related to Jira.
    
    Provides confidence scores for intent matching, enabling
    intelligent routing without hard-coded logic in the orchestrator.
    """
    
    # Keywords strongly indicating Jira intent
    STRONG_KEYWORDS = {
        'jira', 'issue', 'ticket', 'issues', 'project', 'sprint', 
        'epic', 'story', 'bug', 'task', 'subtask', 'blocker',
        'assigned', 'assignee', 'reporter'
    }
    
    # Keywords moderately indicating Jira intent
    MODERATE_KEYWORDS = {
        'show', 'find', 'search', 'list', 'get', 'details', 
        'status', 'information', 'about', 'open', 'closed', 
        'blocked', 'child', 'parent', 'children', 'update',
        'create', 'modify', 'change'
    }
    
    # Status-related terms
    STATUS_KEYWORDS = {
        'to do', 'in progress', 'done', 'closed', 'open', 
        'resolved', 'backlog', 'blocked'
    }
    
    # Meta-conversation phrases (NOT Jira queries)
    META_PHRASES = {
        'you said', 'you mentioned', 'explain yourself', 'what do you mean',
        'i only see', "that doesn't make sense", "you're wrong", 'incorrect',
        'why did you say', 'can you clarify', 'what are you talking about'
    }
    
    # Jira issue key pattern (e.g., PROJ-123, LIFEOPS-7)
    ISSUE_KEY_PATTERN = re.compile(r'\b([A-Z]{2,10}-\d+)\b')
    
    def score(self, intent: str, message: str, context: Optional[Dict] = None) -> float:
        """
        Calculate confidence score (0.0-1.0) that this is a Jira request.
        
        Args:
            intent: Classified intent from IntentClassifier
            message: User message
            context: Optional context (conversation history, etc.)
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        message_lower = message.lower()
        score = 0.0
        
        # Check for meta-conversation (NOT a Jira query)
        if self._is_meta_conversation(message_lower):
            logger.debug("Detected meta-conversation, not Jira query")
            return 0.0
        
        # Check for Jira issue key (strongest indicator)
        if self.extract_issue_key(message):
            score += 0.5
            logger.debug("Found Jira issue key, +0.5 score")
        
        # Check for strong keywords
        strong_matches = sum(1 for kw in self.STRONG_KEYWORDS if kw in message_lower)
        if strong_matches > 0:
            score += min(0.4, strong_matches * 0.15)
            logger.debug(f"Found {strong_matches} strong keywords, +{min(0.4, strong_matches * 0.15):.2f} score")
        
        # Check for moderate keywords
        moderate_matches = sum(1 for kw in self.MODERATE_KEYWORDS if kw in message_lower)
        if moderate_matches > 0:
            score += min(0.2, moderate_matches * 0.05)
        
        # Check for status keywords
        status_matches = sum(1 for kw in self.STATUS_KEYWORDS if kw in message_lower)
        if status_matches > 0:
            score += min(0.1, status_matches * 0.05)
        
        # Intent-based boost
        if intent in ['search_issues', 'get_issue', 'get_child_issues', 'update_issue', 'create_issue']:
            score += 0.3
            logger.debug(f"Intent '{intent}' matches Jira, +0.3 score")
        
        # Check context for recent Jira issues
        if context and self._has_recent_jira_context(context):
            score += 0.1
            logger.debug("Found recent Jira context, +0.1 score")
        
        # Cap at 1.0
        final_score = min(1.0, score)
        logger.debug(f"Jira intent score for '{message[:50]}...': {final_score:.2f}")
        
        return final_score
    
    def _is_meta_conversation(self, message_lower: str) -> bool:
        """Check if message is about the conversation itself, not a query"""
        return any(phrase in message_lower for phrase in self.META_PHRASES)
    
    def _has_recent_jira_context(self, context: Dict) -> bool:
        """Check if conversation history has recent Jira issues"""
        history = context.get('conversation_history', [])
        if not history:
            return False
        
        # Check last 3 messages for Jira issue keys
        for msg in history[-3:]:
            content = msg.get('content', '') if isinstance(msg, dict) else str(msg)
            if self.ISSUE_KEY_PATTERN.search(content):
                return True
        
        return False
    
    def extract_issue_key(self, message: str) -> Optional[str]:
        """
        Extract Jira issue key from message.
        
        Args:
            message: User message
            
        Returns:
            Issue key (e.g., 'PROJ-123') or None
        """
        match = self.ISSUE_KEY_PATTERN.search(message)
        return match.group(1) if match else None
    
    def extract_all_issue_keys(self, message: str) -> List[str]:
        """
        Extract all Jira issue keys from message.
        
        Args:
            message: User message
            
        Returns:
            List of issue keys
        """
        return self.ISSUE_KEY_PATTERN.findall(message)
    
    def is_asking_for_children(self, message: str) -> bool:
        """
        Check if user is asking for child/subtask issues.
        
        Args:
            message: User message
            
        Returns:
            True if asking for children
        """
        message_lower = message.lower()
        
        child_patterns = [
            r'child\s*(issues?|tasks?)',
            r'(subtasks?|sub-tasks?)',
            r'children\s*(of|for)',
            r'what\s*(issues?|tasks?)\s*are\s*(under|in|part of)',
            r'(break\s*down|breakdown)\s*(of|for)?',
            r'(items?|issues?)\s*(under|in)\s*\w+-\d+',
        ]
        
        for pattern in child_patterns:
            if re.search(pattern, message_lower):
                return True
        
        return False
    
    def is_asking_about_status(self, message: str) -> Optional[str]:
        """
        Check if user is asking about a specific status.
        
        Args:
            message: User message
            
        Returns:
            Status string ('to_do', 'in_progress', 'done') or None
        """
        message_lower = message.lower()
        
        if 'in progress' in message_lower or 'in-progress' in message_lower:
            return 'in_progress'
        elif 'to do' in message_lower or 'todo' in message_lower:
            return 'to_do'
        elif 'done' in message_lower or 'closed' in message_lower or 'resolved' in message_lower:
            return 'done'
        
        return None
    
    def is_write_operation(self, message: str) -> Optional[str]:
        """
        Detect if user wants to write/modify Jira.
        
        Args:
            message: User message
            
        Returns:
            Operation type ('create', 'update', 'delete') or None
        """
        message_lower = message.lower()
        
        create_patterns = [
            r'\b(create|add|new|make)\b.*\b(issue|task|bug|story|epic|ticket)\b',
            r'\b(issue|task|bug|story|epic|ticket)\b.*\b(create|add|new|make)\b',
        ]
        
        update_patterns = [
            r'\b(update|change|modify|edit|set|move)\b.*\b(issue|task|bug|story|epic|ticket|status|priority)\b',
            r'\b(mark|move)\b.*\b(as|to)\b',
        ]
        
        delete_patterns = [
            r'\b(delete|remove)\b.*\b(issue|task|bug|story|epic|ticket)\b',
        ]
        
        for pattern in create_patterns:
            if re.search(pattern, message_lower):
                return 'create'
        
        for pattern in update_patterns:
            if re.search(pattern, message_lower):
                return 'update'
        
        for pattern in delete_patterns:
            if re.search(pattern, message_lower):
                return 'delete'
        
        return None

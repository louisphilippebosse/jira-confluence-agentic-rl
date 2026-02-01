"""
Intent Classifier - Classifies user intent for tool routing.

This is a tool-agnostic classifier that determines the user's intent
without being coupled to specific tool implementations.
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class ClassifiedIntent:
    """Result of intent classification"""
    primary_intent: str  # Main intent (e.g., 'search', 'get_details', 'create')
    action: str  # Specific action (e.g., 'search_issues', 'get_documentation')
    confidence: float  # 0.0 - 1.0
    entities: List[Dict[str, Any]]  # Extracted entities
    is_multi_step: bool  # Requires multiple steps/tools
    is_write_operation: bool  # Modifies data
    reasoning: str  # Explanation for classification


class IntentClassifier:
    """
    Classifies user intent from natural language.
    
    Does NOT determine which tool to use - that's the ToolRouter's job.
    This classifier focuses on understanding WHAT the user wants,
    not HOW to accomplish it.
    """
    
    def __init__(self, llm=None):
        """
        Initialize classifier.
        
        Args:
            llm: Optional LLM for complex intent classification
        """
        self.llm = llm
    
    async def classify(self, message: str, 
                       conversation_history: Optional[List] = None) -> ClassifiedIntent:
        """
        Classify user intent from message.
        
        Args:
            message: User message
            conversation_history: Optional conversation history
            
        Returns:
            ClassifiedIntent with classification details
        """
        message_lower = message.lower()
        
        # Check for write operations first
        write_op = self._detect_write_operation(message_lower)
        if write_op:
            return ClassifiedIntent(
                primary_intent="write",
                action=write_op,
                confidence=0.8,
                entities=self._extract_entities(message),
                is_multi_step=True,  # Write ops need confirmation
                is_write_operation=True,
                reasoning=f"Detected {write_op} operation"
            )
        
        # Check for specific retrieval (issue key, page ID, etc.)
        specific_entity = self._detect_specific_retrieval(message)
        if specific_entity:
            return ClassifiedIntent(
                primary_intent="get_details",
                action=specific_entity["action"],
                confidence=0.9,
                entities=[specific_entity],
                is_multi_step=False,
                is_write_operation=False,
                reasoning=f"Found specific entity: {specific_entity['value']}"
            )
        
        # Check for relationship/comparison queries
        if self._is_relationship_query(message_lower):
            return ClassifiedIntent(
                primary_intent="analyze",
                action="find_relationships",
                confidence=0.7,
                entities=self._extract_entities(message),
                is_multi_step=True,
                is_write_operation=False,
                reasoning="Query asks about relationships between entities"
            )
        
        # Check for multi-step/investigation queries
        if self._is_complex_query(message_lower):
            return ClassifiedIntent(
                primary_intent="investigate",
                action="multi_step_search",
                confidence=0.6,
                entities=self._extract_entities(message),
                is_multi_step=True,
                is_write_operation=False,
                reasoning="Complex query requiring multiple steps"
            )
        
        # Default to search
        return ClassifiedIntent(
            primary_intent="search",
            action="search",
            confidence=0.5,
            entities=self._extract_entities(message),
            is_multi_step=False,
            is_write_operation=False,
            reasoning="Default search intent"
        )
    
    def _detect_write_operation(self, message_lower: str) -> Optional[str]:
        """Detect if message is a write operation"""
        create_patterns = [
            r'\b(create|add|new|make)\b.*\b(issue|task|bug|story|epic|ticket)\b',
        ]
        update_patterns = [
            r'\b(update|change|modify|edit|set|move|rename)\b',
            r'\b(mark|move)\b.*\b(as|to)\b',
        ]
        delete_patterns = [
            r'\b(delete|remove)\b.*\b(issue|task)\b',
        ]
        
        for pattern in create_patterns:
            if re.search(pattern, message_lower):
                return "create"
        
        for pattern in update_patterns:
            if re.search(pattern, message_lower):
                return "update"
        
        for pattern in delete_patterns:
            if re.search(pattern, message_lower):
                return "delete"
        
        return None
    
    def _detect_specific_retrieval(self, message: str) -> Optional[Dict[str, Any]]:
        """Detect if asking for a specific entity"""
        # Jira issue key
        jira_match = re.search(r'\b([A-Z]{2,10}-\d+)\b', message)
        if jira_match:
            return {
                "type": "jira_issue",
                "value": jira_match.group(1),
                "action": "get_issue"
            }
        
        # Could add more patterns for Confluence page IDs, etc.
        
        return None
    
    def _is_relationship_query(self, message_lower: str) -> bool:
        """Check if query is about relationships"""
        relationship_phrases = [
            'link between', 'relationship between', 'connection between',
            'related to', 'connects', 'linked to', 'associated with',
            'blocks', 'blocked by', 'depends on', 'parent of', 'child of'
        ]
        return any(phrase in message_lower for phrase in relationship_phrases)
    
    def _is_complex_query(self, message_lower: str) -> bool:
        """Check if query is complex/multi-step"""
        complex_patterns = [
            r'\b(and then|after that|based on|using that)\b',
            r'\b(first.*then|find.*and.*also)\b',
            r'\b(investigate|research|analyze|deep dive)\b',
            r'\b(compare|contrast|difference between)\b',
            r'\b(all.*related|everything about|comprehensive)\b',
        ]
        
        for pattern in complex_patterns:
            if re.search(pattern, message_lower):
                return True
        
        # Long queries are often complex
        if len(message_lower.split()) > 25:
            return True
        
        return False
    
    def _extract_entities(self, message: str) -> List[Dict[str, Any]]:
        """Extract named entities from message"""
        entities = []
        
        # Extract Jira issue keys
        jira_keys = re.findall(r'\b([A-Z]{2,10}-\d+)\b', message)
        for key in jira_keys:
            entities.append({
                "type": "jira_issue",
                "value": key
            })
        
        # Extract project keys (uppercase words that might be project keys)
        project_matches = re.findall(r'\b(project|in)\s+([A-Z]{2,10})\b', message, re.IGNORECASE)
        for _, key in project_matches:
            entities.append({
                "type": "project",
                "value": key
            })
        
        return entities


# Singleton instance
intent_classifier = IntentClassifier()

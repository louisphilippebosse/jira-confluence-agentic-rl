"""
Confluence Intent Detector - Detects when Confluence tool should be used.

Encapsulates all Confluence-specific intent detection logic.
"""
import re
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class ConfluenceIntentDetector:
    """
    Detects if a user message is related to Confluence.
    
    Provides confidence scores for intent matching, enabling
    intelligent routing without hard-coded logic in the orchestrator.
    """
    
    # Keywords strongly indicating Confluence intent
    STRONG_KEYWORDS = {
        'confluence', 'wiki', 'documentation', 'docs', 'document',
        'page', 'space', 'knowledge base'
    }
    
    # Keywords moderately indicating Confluence intent  
    MODERATE_KEYWORDS = {
        'guide', 'how to', 'tutorial', 'manual', 'readme',
        'instruction', 'procedure', 'process', 'runbook',
        'onboarding', 'setup guide', 'architecture', 'design doc'
    }
    
    # Documentation-seeking phrases
    DOC_PHRASES = {
        'how do i', 'how to', 'what is the process',
        'where can i find', 'documentation for', 'guide for',
        'instructions for', 'steps to', 'procedure for'
    }
    
    def score(self, intent: str, message: str, context: Optional[Dict] = None) -> float:
        """
        Calculate confidence score (0.0-1.0) that this is a Confluence request.
        
        Args:
            intent: Classified intent from IntentClassifier
            message: User message
            context: Optional context
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        message_lower = message.lower()
        score = 0.0
        
        # Check for strong keywords
        strong_matches = sum(1 for kw in self.STRONG_KEYWORDS if kw in message_lower)
        if strong_matches > 0:
            score += min(0.5, strong_matches * 0.2)
            logger.debug(f"Found {strong_matches} strong Confluence keywords")
        
        # Check for moderate keywords
        moderate_matches = sum(1 for kw in self.MODERATE_KEYWORDS if kw in message_lower)
        if moderate_matches > 0:
            score += min(0.3, moderate_matches * 0.1)
        
        # Check for doc-seeking phrases
        phrase_matches = sum(1 for phrase in self.DOC_PHRASES if phrase in message_lower)
        if phrase_matches > 0:
            score += min(0.2, phrase_matches * 0.1)
        
        # Intent-based boost
        if intent in ['search_confluence', 'get_documentation', 'find_guide']:
            score += 0.3
            logger.debug(f"Intent '{intent}' matches Confluence")
        
        # Negative signal: if message has Jira issue key, less likely Confluence
        if re.search(r'\b[A-Z]+-\d+\b', message):
            score *= 0.5  # Reduce by 50%
            logger.debug("Found Jira key, reducing Confluence score")
        
        final_score = min(1.0, score)
        logger.debug(f"Confluence intent score: {final_score:.2f}")
        
        return final_score
    
    def extract_space_key(self, message: str) -> Optional[str]:
        """
        Extract Confluence space key from message if mentioned.
        
        Args:
            message: User message
            
        Returns:
            Space key or None
        """
        # Pattern for space key (usually uppercase letters)
        match = re.search(r'(?:space|in)\s+([A-Z]{2,10})\b', message, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return None
    
    def is_asking_for_page_content(self, message: str) -> bool:
        """
        Check if user wants full page content vs just search results.
        
        Args:
            message: User message
            
        Returns:
            True if asking for full content
        """
        message_lower = message.lower()
        
        content_phrases = [
            'full content', 'entire page', 'read the page',
            'show me the page', 'what does it say', 'content of'
        ]
        
        return any(phrase in message_lower for phrase in content_phrases)

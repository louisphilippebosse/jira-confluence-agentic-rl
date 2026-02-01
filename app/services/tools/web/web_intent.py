"""
Web Intent Detector - Detects when web search should be used.
"""
import re
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class WebIntentDetector:
    """
    Detects if a user message requires web search.
    """
    
    # Strong web search indicators
    WEB_PHRASES = {
        'search web', 'search the web', 'google', 'look up online',
        'find online', 'web search', 'internet search', 'search online'
    }
    
    # Topics that typically need web search
    WEB_TOPICS = {
        'weather', 'news', 'latest', 'current events',
        'when is', 'where is', 'what time', 'schedule',
        'competition', 'event', 'tournament', 'championship',
        'price', 'cost', 'review', 'comparison'
    }
    
    # General knowledge questions
    GENERAL_KNOWLEDGE = {
        'what is', 'who is', 'why does', 'how does',
        'define', 'meaning of', 'history of'
    }
    
    def score(self, intent: str, message: str, context: Optional[Dict] = None) -> float:
        """
        Calculate confidence score for web search.
        """
        message_lower = message.lower()
        score = 0.0
        
        # Check for explicit web search phrases
        if any(phrase in message_lower for phrase in self.WEB_PHRASES):
            score += 0.6
            logger.debug("Found explicit web search phrase")
        
        # Check for web-appropriate topics
        topic_matches = sum(1 for topic in self.WEB_TOPICS if topic in message_lower)
        if topic_matches > 0:
            score += min(0.3, topic_matches * 0.15)
        
        # Check for general knowledge questions
        if any(phrase in message_lower for phrase in self.GENERAL_KNOWLEDGE):
            score += 0.2
        
        # Intent-based boost
        if intent in ['web_search', 'find_external_info', 'lookup']:
            score += 0.3
        
        # Reduce score if message has internal system indicators
        if re.search(r'\b[A-Z]+-\d+\b', message):  # Jira key
            score *= 0.3
        if any(word in message_lower for word in ['jira', 'confluence', 'issue', 'ticket', 'documentation']):
            score *= 0.5
        
        return min(1.0, score)
    
    def get_search_query(self, message: str) -> str:
        """
        Clean up message for web search query.
        """
        # Remove command-like prefixes
        query = re.sub(r'^(search|find|look up|google)\s+', '', message, flags=re.IGNORECASE)
        query = re.sub(r'\s+(online|on the web|on internet)\s*$', '', query, flags=re.IGNORECASE)
        return query.strip()

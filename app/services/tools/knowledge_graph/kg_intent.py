"""
Knowledge Graph Intent Detector - Detects when KG tool should be used.
"""
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class KGIntentDetector:
    """
    Detects if a user message should query the Knowledge Graph.
    
    The Knowledge Graph is used for:
    - Relationship queries (what relates to what)
    - Historical context (previously seen issues/pages)
    - Pattern analysis
    - Community detection
    """
    
    # Relationship-indicating phrases
    RELATIONSHIP_PHRASES = {
        'link between', 'relationship between', 'connection between',
        'related to', 'connects', 'linked to', 'associated with',
        'delivered by', 'delivers', 'blocks', 'blocked by', 'depends on',
        'parent of', 'child of', 'similar to'
    }
    
    # Analysis/pattern phrases
    ANALYSIS_PHRASES = {
        'pattern', 'trends', 'common', 'frequently', 'usually',
        'community', 'cluster', 'group', 'category', 'overview',
        'summary of all', 'all related', 'everything about'
    }
    
    def score(self, intent: str, message: str, context: Optional[Dict] = None) -> float:
        """
        Calculate confidence score for Knowledge Graph query.
        """
        message_lower = message.lower()
        score = 0.0
        
        # Check for relationship phrases
        relationship_matches = sum(1 for phrase in self.RELATIONSHIP_PHRASES 
                                    if phrase in message_lower)
        if relationship_matches > 0:
            score += min(0.5, relationship_matches * 0.2)
            logger.debug(f"Found {relationship_matches} relationship phrases")
        
        # Check for analysis phrases
        analysis_matches = sum(1 for phrase in self.ANALYSIS_PHRASES 
                               if phrase in message_lower)
        if analysis_matches > 0:
            score += min(0.3, analysis_matches * 0.15)
        
        # Intent-based boost
        if intent in ['find_relationships', 'analyze_patterns', 'get_context']:
            score += 0.3
        
        # KG is often used alongside other tools, so base score is lower
        # It's typically a supplementary source
        
        return min(1.0, score)
    
    def is_relationship_query(self, message: str) -> bool:
        """Check if this is specifically asking about relationships."""
        message_lower = message.lower()
        return any(phrase in message_lower for phrase in self.RELATIONSHIP_PHRASES)

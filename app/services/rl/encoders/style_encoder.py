"""
Style Encoder - Encodes features for response style selection.

Single Responsibility: Extracts features relevant to response formatting.
"""
import re
import logging
from typing import List, Dict, Optional
import numpy as np

from .base_encoder import BaseEncoder

logger = logging.getLogger(__name__)


class StyleEncoder(BaseEncoder):
    """Encodes context into features for style selection.
    
    Features focus on:
    - Query complexity (simple vs complex)
    - User's implicit style preferences
    - Content type (technical, summary, list)
    - Historical style feedback
    """
    
    OUTPUT_SIZE = 15
    
    @property
    def output_size(self) -> int:
        return self.OUTPUT_SIZE
    
    def encode(
        self,
        message: str,
        conversation_history: List[Dict],
        session_context: Optional[Dict] = None
    ) -> np.ndarray:
        """Encode context for style selection."""
        features = []
        message_lower = message.lower()
        
        # === Query complexity features ===
        # Word count (normalized)
        word_count = len(message.split())
        features.append(min(word_count / 50.0, 1.0))
        
        # Is simple query (short, direct)
        is_simple = word_count <= 10 and '?' not in message
        features.append(1.0 if is_simple else 0.0)
        
        # Is complex query (long, multiple parts)
        has_multiple_parts = any(w in message_lower for w in ['and', 'also', 'as well', 'plus'])
        features.append(1.0 if has_multiple_parts else 0.0)
        
        # === Implicit style preferences ===
        # User asks for list/bullets
        wants_list = any(w in message_lower for w in ['list', 'bullet', 'enumerate', 'all the'])
        features.append(1.0 if wants_list else 0.0)
        
        # User asks for summary/brief
        wants_brief = any(w in message_lower for w in ['brief', 'quick', 'summary', 'short', 'tldr'])
        features.append(1.0 if wants_brief else 0.0)
        
        # User asks for details/explanation
        wants_detail = any(w in message_lower for w in ['explain', 'detail', 'why', 'how does', 'elaborate'])
        features.append(1.0 if wants_detail else 0.0)
        
        # User asks for examples
        wants_examples = any(w in message_lower for w in ['example', 'show me', 'like what', 'such as'])
        features.append(1.0 if wants_examples else 0.0)
        
        # === Content type indicators ===
        # Technical content
        is_technical = any(w in message_lower for w in ['code', 'api', 'config', 'deploy', 'error', 'debug'])
        features.append(1.0 if is_technical else 0.0)
        
        # Status/metrics content
        is_status = any(w in message_lower for w in ['status', 'progress', 'done', 'pending', 'count', 'how many'])
        features.append(1.0 if is_status else 0.0)
        
        # Comparison content
        is_comparison = any(w in message_lower for w in ['compare', 'difference', 'vs', 'versus', 'between'])
        features.append(1.0 if is_comparison else 0.0)
        
        # === Historical context ===
        # Average response length user engages with
        if conversation_history:
            assistant_msgs = [m for m in conversation_history if m.get('role') == 'assistant']
            if assistant_msgs:
                avg_response_len = np.mean([len(m.get('content', '')) for m in assistant_msgs[-5:]])
                features.append(min(avg_response_len / 1000.0, 1.0))
            else:
                features.append(0.5)  # Default mid-range
        else:
            features.append(0.5)
        
        # User message pattern (short responses = prefers concise)
        if conversation_history:
            user_msgs = [m for m in conversation_history if m.get('role') == 'user']
            if len(user_msgs) >= 2:
                avg_user_len = np.mean([len(m.get('content', '')) for m in user_msgs[-5:]])
                features.append(min(avg_user_len / 200.0, 1.0))
            else:
                features.append(0.5)
        else:
            features.append(0.5)
        
        # === Session feedback ===
        if session_context:
            features.append(session_context.get('style_preference_score', 0.5))
            features.append(session_context.get('avg_feedback', 0.0))
        else:
            features.append(0.5)
            features.append(0.0)
        
        return self._pad_or_truncate(features, self.OUTPUT_SIZE)
    
    def get_style_hints(self, message: str) -> Dict[str, bool]:
        """Extract explicit style hints from the message.
        
        Returns dict of detected style preferences.
        """
        message_lower = message.lower()
        
        return {
            "wants_list": any(w in message_lower for w in ['list', 'bullet', 'enumerate']),
            "wants_brief": any(w in message_lower for w in ['brief', 'quick', 'summary', 'short']),
            "wants_detail": any(w in message_lower for w in ['explain', 'detail', 'elaborate']),
            "wants_examples": any(w in message_lower for w in ['example', 'show me']),
            "wants_table": any(w in message_lower for w in ['table', 'compare', 'grid']),
        }

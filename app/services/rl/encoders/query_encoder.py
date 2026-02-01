"""
Query Encoder - Encodes query features for tool selection.

Single Responsibility: Extracts features relevant to choosing which tool to use.
"""
import re
import logging
from typing import List, Dict, Optional
import numpy as np

from .base_encoder import BaseEncoder

logger = logging.getLogger(__name__)


class QueryEncoder(BaseEncoder):
    """Encodes user queries into features for tool selection.
    
    Features focus on:
    - Keywords indicating Jira/Confluence/KG usage
    - Query type (search, get, analyze)
    - Issue key patterns
    - Conversation context
    """
    
    OUTPUT_SIZE = 20
    
    @property
    def output_size(self) -> int:
        return self.OUTPUT_SIZE
    
    def encode(
        self,
        message: str,
        conversation_history: List[Dict],
        session_context: Optional[Dict] = None
    ) -> np.ndarray:
        """Encode query for tool selection."""
        features = []
        message_lower = message.lower()
        
        # === Message content features ===
        # Length (normalized)
        features.append(min(len(message) / 500.0, 1.0))
        
        # Platform keywords
        features.append(1.0 if 'jira' in message_lower else 0.0)
        features.append(1.0 if 'confluence' in message_lower else 0.0)
        features.append(1.0 if 'wiki' in message_lower or 'page' in message_lower else 0.0)
        
        # Issue-related keywords
        features.append(1.0 if 'issue' in message_lower or 'ticket' in message_lower else 0.0)
        features.append(1.0 if 'bug' in message_lower or 'defect' in message_lower else 0.0)
        features.append(1.0 if 'task' in message_lower or 'story' in message_lower else 0.0)
        
        # Issue key pattern (PROJ-123)
        has_issue_key = bool(re.search(r'\b[A-Z]{2,10}-\d+\b', message))
        features.append(1.0 if has_issue_key else 0.0)
        
        # Action keywords
        features.append(1.0 if any(w in message_lower for w in ['show', 'get', 'find', 'fetch']) else 0.0)
        features.append(1.0 if any(w in message_lower for w in ['search', 'query', 'look']) else 0.0)
        features.append(1.0 if any(w in message_lower for w in ['child', 'subtask', 'sub-task']) else 0.0)
        features.append(1.0 if any(w in message_lower for w in ['parent', 'epic', 'linked']) else 0.0)
        features.append(1.0 if any(w in message_lower for w in ['analyze', 'summary', 'report']) else 0.0)
        
        # Question indicators
        features.append(1.0 if '?' in message else 0.0)
        features.append(1.0 if message_lower.startswith(('what', 'how', 'why', 'when', 'where', 'who')) else 0.0)
        
        # === Conversation context features ===
        features.append(min(len(conversation_history) / 20.0, 1.0))
        
        # Recent tool mentions in history
        recent_msgs = conversation_history[-3:] if conversation_history else []
        recent_text = ' '.join(m.get('content', '') for m in recent_msgs).lower()
        features.append(1.0 if 'jira' in recent_text else 0.0)
        features.append(1.0 if 'confluence' in recent_text else 0.0)
        
        # === Session context features ===
        if session_context:
            features.append(min(session_context.get('message_count', 0) / 50.0, 1.0))
            features.append(session_context.get('avg_feedback', 0.0))
        else:
            features.append(0.0)
            features.append(0.0)
        
        return self._pad_or_truncate(features, self.OUTPUT_SIZE)

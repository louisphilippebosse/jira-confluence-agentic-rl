"""
Base Encoder Interface - Defines contract for state encoders.

Following Interface Segregation Principle (ISP).
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import numpy as np


class BaseEncoder(ABC):
    """Abstract base class for state encoders.
    
    Encoders transform raw input (messages, context) into fixed-size
    feature vectors for RL agents.
    """
    
    @property
    @abstractmethod
    def output_size(self) -> int:
        """Return the size of the encoded feature vector."""
        pass
    
    @abstractmethod
    def encode(
        self,
        message: str,
        conversation_history: List[Dict],
        session_context: Optional[Dict] = None
    ) -> np.ndarray:
        """Encode input into feature vector.
        
        Args:
            message: Current user message
            conversation_history: List of previous messages
            session_context: Optional session metadata
            
        Returns:
            Feature vector of size `output_size`
        """
        pass
    
    def _pad_or_truncate(self, features: List[float], target_size: int) -> np.ndarray:
        """Pad or truncate feature list to target size."""
        if len(features) < target_size:
            features.extend([0.0] * (target_size - len(features)))
        return np.array(features[:target_size], dtype=np.float32)

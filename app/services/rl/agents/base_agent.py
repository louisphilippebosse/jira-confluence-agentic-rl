"""
Base Agent Interface - Defines contract for all RL agents.

Following Interface Segregation Principle (ISP) and Dependency Inversion (DIP).
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import numpy as np


class BaseAgent(ABC):
    """Abstract base class for RL agents.
    
    All agents must implement these methods, allowing the RLService
    to work with any agent implementation (DIP).
    """
    
    @property
    @abstractmethod
    def actions(self) -> List[str]:
        """Return list of available actions."""
        pass
    
    @property
    @abstractmethod
    def state_size(self) -> int:
        """Return expected state vector size."""
        pass
    
    @abstractmethod
    def select_action(self, state: np.ndarray, training: bool = True) -> int:
        """Select an action given the current state.
        
        Args:
            state: Current state vector
            training: If True, use exploration; if False, use greedy policy
            
        Returns:
            Action index
        """
        pass
    
    @abstractmethod
    def get_action_name(self, action_idx: int) -> str:
        """Convert action index to human-readable name."""
        pass
    
    @abstractmethod
    def get_action_index(self, action_name: str) -> int:
        """Convert action name to index."""
        pass
    
    @abstractmethod
    def remember(self, state: np.ndarray, action: int, reward: float,
                 next_state: np.ndarray, done: bool) -> None:
        """Store experience in replay buffer."""
        pass
    
    @abstractmethod
    def train_step(self) -> None:
        """Perform one training step."""
        pass
    
    @abstractmethod
    def save_model(self, path: str) -> None:
        """Save model to disk."""
        pass
    
    @abstractmethod
    def load_model(self, path: str) -> None:
        """Load model from disk."""
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Return agent statistics."""
        pass

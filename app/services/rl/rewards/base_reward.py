"""
Base Reward Interface - Defines contract for reward calculators.

Following Interface Segregation Principle (ISP).
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseReward(ABC):
    """Abstract base class for reward calculators.
    
    Reward calculators transform user feedback and interaction metrics
    into numerical rewards for RL training.
    """
    
    @abstractmethod
    def calculate(
        self,
        feedback_value: int,
        interaction_data: Optional[Dict[str, Any]] = None
    ) -> float:
        """Calculate reward from feedback and interaction data.
        
        Args:
            feedback_value: Raw feedback (e.g., -1, 0, 1 for thumbs)
            interaction_data: Optional additional context
            
        Returns:
            Normalized reward value
        """
        pass
    
    @abstractmethod
    def get_reward_range(self) -> tuple:
        """Return (min_reward, max_reward) tuple."""
        pass

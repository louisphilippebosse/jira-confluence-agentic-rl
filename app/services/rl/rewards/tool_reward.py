"""
Tool Reward - Calculates rewards for tool selection.

Single Responsibility: Converts feedback into tool selection rewards.
"""
import logging
from typing import Dict, Any, Optional

from .base_reward import BaseReward

logger = logging.getLogger(__name__)


class ToolReward(BaseReward):
    """Reward calculator for tool selection agent.
    
    Rewards based on:
    - User thumbs up/down feedback
    - Whether results were found
    - Response time (optional)
    """
    
    # Reward scale
    POSITIVE_REWARD = 1.0
    NEGATIVE_REWARD = -1.0
    NEUTRAL_REWARD = 0.0
    
    # Bonus/penalty modifiers
    NO_RESULTS_PENALTY = -0.3
    FAST_RESPONSE_BONUS = 0.1
    
    def calculate(
        self,
        feedback_value: int,
        interaction_data: Optional[Dict[str, Any]] = None
    ) -> float:
        """Calculate reward for tool selection.
        
        Args:
            feedback_value: -1 (thumbs down), 0 (neutral), 1 (thumbs up)
            interaction_data: Optional dict with 'results_found', 'response_time_ms'
        """
        # Base reward from feedback
        if feedback_value > 0:
            reward = self.POSITIVE_REWARD
        elif feedback_value < 0:
            reward = self.NEGATIVE_REWARD
        else:
            reward = self.NEUTRAL_REWARD
        
        # Apply modifiers based on interaction data
        if interaction_data:
            # Penalty if no results were found
            if not interaction_data.get('results_found', True):
                reward += self.NO_RESULTS_PENALTY
            
            # Bonus for fast responses (< 2 seconds)
            response_time = interaction_data.get('response_time_ms', 0)
            if response_time > 0 and response_time < 2000:
                reward += self.FAST_RESPONSE_BONUS
        
        # Clamp to range
        min_r, max_r = self.get_reward_range()
        reward = max(min_r, min(max_r, reward))
        
        logger.debug(f"🎯 Tool reward: {reward:.2f} (feedback={feedback_value})")
        return reward
    
    def get_reward_range(self) -> tuple:
        return (-1.5, 1.5)

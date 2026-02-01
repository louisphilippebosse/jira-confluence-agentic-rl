"""
Style Reward - Calculates rewards for response style selection.

Single Responsibility: Converts feedback into style preference rewards.
"""
import logging
from typing import Dict, Any, Optional

from .base_reward import BaseReward

logger = logging.getLogger(__name__)


class StyleReward(BaseReward):
    """Reward calculator for style selection agent.
    
    Rewards based on:
    - User feedback (primary signal)
    - Implicit engagement signals
    - Style-specific feedback if available
    """
    
    # Reward scale
    POSITIVE_REWARD = 1.0
    NEGATIVE_REWARD = -1.0
    NEUTRAL_REWARD = 0.0
    
    # Style-specific modifiers
    ENGAGEMENT_BONUS = 0.2  # User asks follow-up
    COPY_BONUS = 0.15       # User copies response (if tracked)
    TOO_LONG_PENALTY = -0.1 # Response was very long and got negative feedback
    
    def calculate(
        self,
        feedback_value: int,
        interaction_data: Optional[Dict[str, Any]] = None
    ) -> float:
        """Calculate reward for style selection.
        
        Args:
            feedback_value: -1, 0, 1 feedback
            interaction_data: Optional dict with style-specific signals
        """
        # Base reward
        if feedback_value > 0:
            reward = self.POSITIVE_REWARD
        elif feedback_value < 0:
            reward = self.NEGATIVE_REWARD
        else:
            reward = self.NEUTRAL_REWARD
        
        if interaction_data:
            # Engagement bonus - user continued conversation
            if interaction_data.get('had_followup', False):
                reward += self.ENGAGEMENT_BONUS
            
            # Copy bonus - user copied the response
            if interaction_data.get('response_copied', False):
                reward += self.COPY_BONUS
            
            # Length penalty for negative feedback on long responses
            if feedback_value < 0:
                response_length = interaction_data.get('response_length', 0)
                if response_length > 2000:  # Very long response
                    reward += self.TOO_LONG_PENALTY
            
            # Style-specific feedback override
            if 'style_rating' in interaction_data:
                # Direct style rating from user (1-5 scale)
                style_rating = interaction_data['style_rating']
                reward = (style_rating - 3) / 2.0  # Map 1-5 to -1 to 1
        
        # Clamp to range
        min_r, max_r = self.get_reward_range()
        reward = max(min_r, min(max_r, reward))
        
        logger.debug(f"🎨 Style reward: {reward:.2f}")
        return reward
    
    def get_reward_range(self) -> tuple:
        return (-1.5, 1.5)
    
    def calculate_implicit_reward(
        self,
        response_length: int,
        user_read_time_ms: int,
        had_followup: bool
    ) -> float:
        """Calculate implicit reward from user behavior.
        
        Useful when no explicit feedback is given.
        """
        reward = 0.0
        
        # Estimate if user read the response
        # Assume ~200 words/min reading speed, ~5 chars/word
        expected_read_time = (response_length / 5) / 200 * 60 * 1000  # ms
        
        if user_read_time_ms > 0:
            read_ratio = user_read_time_ms / max(expected_read_time, 1)
            
            if read_ratio > 0.8:
                # User spent enough time reading
                reward += 0.3
            elif read_ratio < 0.3:
                # User quickly skipped (might be too long)
                reward -= 0.2
        
        # Follow-up indicates engagement
        if had_followup:
            reward += 0.2
        
        return reward

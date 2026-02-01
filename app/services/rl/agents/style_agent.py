"""
Style Agent - Learns user's preferred response style.

Single Responsibility: Manages Q-learning for response style selection.
"""
import numpy as np
import json
import logging
import random
from typing import Dict, List, Any
from collections import deque

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class StyleAgent(BaseAgent):
    """Agent for learning optimal response style preferences.
    
    Learns from user feedback which response styles work best:
    - Verbosity (concise vs detailed)
    - Format (prose vs bullets vs tables)
    - Tone (formal vs casual)
    - Code inclusion (with examples vs without)
    """
    
    # Style action space
    DEFAULT_ACTIONS = [
        # Verbosity
        "concise",           # Brief, to-the-point
        "detailed",          # Comprehensive explanation
        "balanced",          # Medium detail
        
        # Format
        "prose",             # Paragraph form
        "bullets",           # Bullet points
        "table",             # Tabular format
        "mixed",             # Combination
        
        # Extras
        "with_examples",     # Include code/examples
        "with_context",      # Include background context
        "direct_answer",     # Just answer, no context
    ]
    
    DEFAULT_STATE_SIZE = 15
    
    def __init__(
        self,
        actions: List[str] = None,
        state_size: int = None,
        learning_rate: float = 0.01,  # Higher LR for faster style learning
        gamma: float = 0.9,
        epsilon: float = 0.3,  # Lower epsilon - less exploration needed
        epsilon_decay: float = 0.99,
        epsilon_min: float = 0.05,
        memory_size: int = 1000,
        batch_size: int = 16
    ):
        """Initialize the Style agent."""
        self._actions = actions or self.DEFAULT_ACTIONS
        self._state_size = state_size or self.DEFAULT_STATE_SIZE
        
        self.learning_rate = learning_rate
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        self.batch_size = batch_size
        
        # Q-table for style preferences
        self.q_table: Dict[str, np.ndarray] = {}
        
        # Experience replay
        self.memory = deque(maxlen=memory_size)
        
        # Track style preferences over time
        self.style_history: List[Dict] = []
        
        logger.info(f"🎨 Style Agent initialized: {len(self._actions)} styles")
    
    @property
    def actions(self) -> List[str]:
        return self._actions
    
    @property
    def state_size(self) -> int:
        return self._state_size
    
    def _hash_state(self, state: np.ndarray) -> str:
        """Create hash of state for Q-table lookup."""
        rounded = np.round(state, decimals=2)
        return str(rounded.tolist())
    
    def get_q_values(self, state: np.ndarray) -> np.ndarray:
        """Get Q-values for all style actions."""
        state_hash = self._hash_state(state)
        
        if state_hash not in self.q_table:
            # Initialize with slight preference for balanced/bullets
            initial = np.zeros(len(self._actions))
            if "balanced" in self._actions:
                initial[self._actions.index("balanced")] = 0.1
            if "bullets" in self._actions:
                initial[self._actions.index("bullets")] = 0.1
            self.q_table[state_hash] = initial
        
        return self.q_table[state_hash]
    
    def select_action(self, state: np.ndarray, training: bool = True) -> int:
        """Select style using epsilon-greedy policy."""
        if training and random.random() < self.epsilon:
            action_idx = random.randint(0, len(self._actions) - 1)
            logger.debug(f"🎲 Exploring style: {self._actions[action_idx]}")
        else:
            q_values = self.get_q_values(state)
            action_idx = int(np.argmax(q_values))
            logger.debug(f"🎯 Selected style: {self._actions[action_idx]}")
        
        return action_idx
    
    def select_multiple_styles(self, state: np.ndarray, top_k: int = 3) -> List[str]:
        """Select top-k compatible styles for response generation.
        
        Returns multiple style preferences that can be combined.
        """
        q_values = self.get_q_values(state)
        
        # Get indices of top-k actions
        top_indices = np.argsort(q_values)[-top_k:][::-1]
        
        return [self._actions[i] for i in top_indices]
    
    def get_action_name(self, action_idx: int) -> str:
        """Convert action index to name."""
        if 0 <= action_idx < len(self._actions):
            return self._actions[action_idx]
        return "balanced"
    
    def get_action_index(self, action_name: str) -> int:
        """Convert action name to index."""
        try:
            return self._actions.index(action_name)
        except ValueError:
            return self._actions.index("balanced") if "balanced" in self._actions else 0
    
    def remember(self, state: np.ndarray, action: int, reward: float,
                 next_state: np.ndarray, done: bool) -> None:
        """Store experience in replay buffer."""
        self.memory.append((state, action, reward, next_state, done))
        
        # Track style history
        self.style_history.append({
            "style": self._actions[action],
            "reward": reward
        })
        
        # Keep only recent history
        if len(self.style_history) > 100:
            self.style_history = self.style_history[-100:]
    
    def train_step(self) -> None:
        """Perform one training step."""
        if len(self.memory) < self.batch_size:
            return
        
        batch = random.sample(self.memory, self.batch_size)
        
        for state, action, reward, next_state, done in batch:
            q_values = self.get_q_values(state)
            
            if done:
                target = reward
            else:
                next_q_values = self.get_q_values(next_state)
                target = reward + self.gamma * np.max(next_q_values)
            
            q_values[action] += self.learning_rate * (target - q_values[action])
            
            state_hash = self._hash_state(state)
            self.q_table[state_hash] = q_values
        
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay
        
        logger.debug(f"🎨 Style trained, epsilon={self.epsilon:.3f}")
    
    def save_model(self, path: str) -> None:
        """Save style model to disk."""
        try:
            data = {
                'q_table': {k: v.tolist() for k, v in self.q_table.items()},
                'epsilon': self.epsilon,
                'actions': self._actions,
                'style_history': self.style_history[-50:]  # Keep recent history
            }
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"💾 Saved style model to {path}")
        except Exception as e:
            logger.error(f"❌ Error saving style model: {e}")
    
    def load_model(self, path: str) -> None:
        """Load style model from disk."""
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            
            self.q_table = {k: np.array(v) for k, v in data.get('q_table', {}).items()}
            self.epsilon = data.get('epsilon', self.epsilon)
            self.style_history = data.get('style_history', [])
            logger.info(f"📂 Loaded style model ({len(self.q_table)} states)")
        except FileNotFoundError:
            logger.info(f"ℹ️ No saved style model, starting fresh")
        except Exception as e:
            logger.error(f"❌ Error loading style model: {e}")
    
    def get_preferred_styles(self) -> Dict[str, float]:
        """Analyze style history to find user's preferred styles."""
        if not self.style_history:
            return {}
        
        # Count positive feedback per style
        style_scores: Dict[str, List[float]] = {}
        for entry in self.style_history:
            style = entry["style"]
            reward = entry["reward"]
            if style not in style_scores:
                style_scores[style] = []
            style_scores[style].append(reward)
        
        # Calculate average reward per style
        return {
            style: np.mean(rewards) 
            for style, rewards in style_scores.items()
            if len(rewards) >= 2  # Need at least 2 samples
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Return agent statistics."""
        return {
            "type": "Style",
            "epsilon": self.epsilon,
            "q_table_size": len(self.q_table),
            "memory_size": len(self.memory),
            "styles": self._actions,
            "preferred_styles": self.get_preferred_styles()
        }

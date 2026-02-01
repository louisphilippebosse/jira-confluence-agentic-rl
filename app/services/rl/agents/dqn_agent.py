"""
DQN Agent - Deep Q-Network implementation for tool selection.

Single Responsibility: Manages Q-learning for action selection.
"""
import numpy as np
import json
import logging
import random
from typing import Dict, List, Any
from collections import deque

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class DQNAgent(BaseAgent):
    """Deep Q-Network agent for learning optimal action selection.
    
    Uses epsilon-greedy policy with Q-table (can be extended to neural network).
    """
    
    # Default action space for tool selection
    DEFAULT_ACTIONS = [
        "search_jira",
        "get_jira_issue",
        "get_child_issues",
        "search_confluence",
        "query_knowledge_graph",
        "general_response"
    ]
    
    DEFAULT_STATE_SIZE = 20
    
    def __init__(
        self,
        actions: List[str] = None,
        state_size: int = None,
        learning_rate: float = 0.001,
        gamma: float = 0.95,
        epsilon: float = 1.0,
        epsilon_decay: float = 0.995,
        epsilon_min: float = 0.01,
        memory_size: int = 2000,
        batch_size: int = 32
    ):
        """Initialize the DQN agent.
        
        Args:
            actions: List of action names (uses default if None)
            state_size: Size of state feature vector
            learning_rate: Learning rate for Q-value updates
            gamma: Discount factor for future rewards
            epsilon: Initial exploration rate
            epsilon_decay: Rate at which epsilon decreases
            epsilon_min: Minimum epsilon value
            memory_size: Experience replay buffer size
            batch_size: Training batch size
        """
        self._actions = actions or self.DEFAULT_ACTIONS
        self._state_size = state_size or self.DEFAULT_STATE_SIZE
        
        self.learning_rate = learning_rate
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        self.batch_size = batch_size
        
        # Q-table: state_hash -> action -> q_value
        self.q_table: Dict[str, np.ndarray] = {}
        
        # Experience replay buffer
        self.memory = deque(maxlen=memory_size)
        
        logger.info(f"🧠 DQN Agent initialized: {len(self._actions)} actions, state_size={self._state_size}")
    
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
        """Get Q-values for all actions given a state."""
        state_hash = self._hash_state(state)
        
        if state_hash not in self.q_table:
            self.q_table[state_hash] = np.zeros(len(self._actions))
        
        return self.q_table[state_hash]
    
    def select_action(self, state: np.ndarray, training: bool = True) -> int:
        """Select action using epsilon-greedy policy."""
        if training and random.random() < self.epsilon:
            # Explore: random action
            action_idx = random.randint(0, len(self._actions) - 1)
            logger.debug(f"🎲 Exploring: {self._actions[action_idx]}")
        else:
            # Exploit: best action according to Q-values
            q_values = self.get_q_values(state)
            action_idx = int(np.argmax(q_values))
            logger.debug(f"🎯 Exploiting: {self._actions[action_idx]} (Q={q_values[action_idx]:.3f})")
        
        return action_idx
    
    def get_action_name(self, action_idx: int) -> str:
        """Convert action index to name."""
        if 0 <= action_idx < len(self._actions):
            return self._actions[action_idx]
        return self._actions[-1]  # Default to last action
    
    def get_action_index(self, action_name: str) -> int:
        """Convert action name to index."""
        try:
            return self._actions.index(action_name)
        except ValueError:
            return len(self._actions) - 1  # Default to last action
    
    def remember(self, state: np.ndarray, action: int, reward: float,
                 next_state: np.ndarray, done: bool) -> None:
        """Store experience in replay buffer."""
        self.memory.append((state, action, reward, next_state, done))
    
    def train_step(self) -> None:
        """Perform one training step using experience replay."""
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
            
            # Q-learning update
            q_values[action] += self.learning_rate * (target - q_values[action])
            
            state_hash = self._hash_state(state)
            self.q_table[state_hash] = q_values
        
        # Decay epsilon
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay
        
        logger.debug(f"📚 Trained batch, epsilon={self.epsilon:.3f}")
    
    def save_model(self, path: str) -> None:
        """Save Q-table to disk."""
        try:
            data = {
                'q_table': {k: v.tolist() for k, v in self.q_table.items()},
                'epsilon': self.epsilon,
                'actions': self._actions,
                'state_size': self._state_size
            }
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"💾 Saved model to {path}")
        except Exception as e:
            logger.error(f"❌ Error saving model: {e}")
    
    def load_model(self, path: str) -> None:
        """Load Q-table from disk."""
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            
            self.q_table = {k: np.array(v) for k, v in data.get('q_table', {}).items()}
            self.epsilon = data.get('epsilon', self.epsilon)
            logger.info(f"📂 Loaded model from {path} ({len(self.q_table)} states)")
        except FileNotFoundError:
            logger.info(f"ℹ️ No saved model at {path}, starting fresh")
        except Exception as e:
            logger.error(f"❌ Error loading model: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Return agent statistics."""
        return {
            "type": "DQN",
            "epsilon": self.epsilon,
            "q_table_size": len(self.q_table),
            "memory_size": len(self.memory),
            "actions": self._actions,
            "state_size": self._state_size
        }

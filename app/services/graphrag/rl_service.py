"""Reinforcement Learning service for learning optimal tool/skill selection"""
import numpy as np
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from collections import deque
import random

from app.models.database import RLState, Feedback, Conversation
from app.config import settings

logger = logging.getLogger(__name__)


class DQNAgent:
    """Deep Q-Network agent for learning optimal action selection"""
    
    # Action space: different tools/skills the agent can use
    ACTIONS = [
        "search_jira",
        "get_jira_issue", 
        "get_child_issues",
        "search_confluence",
        "query_knowledge_graph",
        "general_response"
    ]
    
    # State features (will be extracted from conversation context)
    STATE_SIZE = 20  # Feature vector size
    ACTION_SIZE = len(ACTIONS)
    
    def __init__(self, learning_rate: float = 0.001, gamma: float = 0.95, 
                 epsilon: float = 1.0, epsilon_decay: float = 0.995, epsilon_min: float = 0.01):
        """Initialize the DQN agent
        
        Args:
            learning_rate: Learning rate for Q-value updates
            gamma: Discount factor for future rewards
            epsilon: Initial exploration rate
            epsilon_decay: Rate at which epsilon decreases
            epsilon_min: Minimum epsilon value
        """
        self.learning_rate = learning_rate
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        
        # Simple Q-table (state_hash -> action -> q_value)
        # In production, replace with neural network
        self.q_table: Dict[str, np.ndarray] = {}
        
        # Experience replay buffer
        self.memory = deque(maxlen=2000)
        self.batch_size = 32
        
        logger.info(f"🧠 Initialized DQN Agent with {self.ACTION_SIZE} actions")
    
    def _hash_state(self, state: np.ndarray) -> str:
        """Create a hash of the state for Q-table lookup"""
        # Round to reduce dimensionality
        rounded = np.round(state, decimals=2)
        return str(rounded.tolist())
    
    def get_q_values(self, state: np.ndarray) -> np.ndarray:
        """Get Q-values for all actions given a state"""
        state_hash = self._hash_state(state)
        
        if state_hash not in self.q_table:
            # Initialize Q-values for new state
            self.q_table[state_hash] = np.zeros(self.ACTION_SIZE)
        
        return self.q_table[state_hash]
    
    def select_action(self, state: np.ndarray, training: bool = True) -> int:
        """Select an action using epsilon-greedy policy
        
        Args:
            state: Current state vector
            training: If True, use epsilon-greedy; if False, use greedy policy
            
        Returns:
            Action index
        """
        if training and random.random() < self.epsilon:
            # Explore: random action
            action_idx = random.randint(0, self.ACTION_SIZE - 1)
            logger.debug(f"🎲 Exploring: action {self.ACTIONS[action_idx]}")
        else:
            # Exploit: best action according to Q-values
            q_values = self.get_q_values(state)
            action_idx = int(np.argmax(q_values))
            logger.debug(f"🎯 Exploiting: action {self.ACTIONS[action_idx]} (Q={q_values[action_idx]:.3f})")
        
        return action_idx
    
    def get_action_name(self, action_idx: int) -> str:
        """Convert action index to action name"""
        return self.ACTIONS[action_idx]
    
    def get_action_index(self, action_name: str) -> int:
        """Convert action name to index"""
        try:
            return self.ACTIONS.index(action_name)
        except ValueError:
            # Default to general_response if action not found
            return self.ACTIONS.index("general_response")
    
    def remember(self, state: np.ndarray, action: int, reward: float, 
                 next_state: np.ndarray, done: bool):
        """Store experience in replay buffer"""
        self.memory.append((state, action, reward, next_state, done))
    
    def train_step(self):
        """Perform one training step using experience replay"""
        if len(self.memory) < self.batch_size:
            return
        
        # Sample random batch from memory
        batch = random.sample(self.memory, self.batch_size)
        
        for state, action, reward, next_state, done in batch:
            # Current Q-value
            q_values = self.get_q_values(state)
            
            if done:
                # Terminal state: Q-value is just the reward
                target = reward
            else:
                # Q-learning update: Q(s,a) = r + gamma * max(Q(s',a'))
                next_q_values = self.get_q_values(next_state)
                target = reward + self.gamma * np.max(next_q_values)
            
            # Update Q-value using learning rate
            q_values[action] = q_values[action] + self.learning_rate * (target - q_values[action])
            
            # Store updated Q-values
            state_hash = self._hash_state(state)
            self.q_table[state_hash] = q_values
        
        # Decay epsilon
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay
        
        logger.debug(f"📚 Trained on batch of {self.batch_size}, epsilon={self.epsilon:.3f}")
    
    def save_model(self, path: str):
        """Save Q-table to disk"""
        try:
            data = {
                'q_table': {k: v.tolist() for k, v in self.q_table.items()},
                'epsilon': self.epsilon,
                'actions': self.ACTIONS
            }
            with open(path, 'w') as f:
                json.dump(data, f)
            logger.info(f"💾 Saved RL model to {path}")
        except Exception as e:
            logger.error(f"❌ Error saving model: {e}")
    
    def load_model(self, path: str):
        """Load Q-table from disk"""
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            
            self.q_table = {k: np.array(v) for k, v in data['q_table'].items()}
            self.epsilon = data.get('epsilon', self.epsilon)
            logger.info(f"📂 Loaded RL model from {path} ({len(self.q_table)} states)")
        except FileNotFoundError:
            logger.info(f"ℹ️ No saved model found at {path}, starting fresh")
        except Exception as e:
            logger.error(f"❌ Error loading model: {e}")


class RLService:
    """Service for reinforcement learning-based agent optimization"""
    
    def __init__(self):
        self.agent = DQNAgent()
        self.model_path = "./data/rl_model.json"
        
        # Load saved model if exists
        self.agent.load_model(self.model_path)
        
        # Training config
        self.training_enabled = True
        self.auto_train_interval = 10  # Train every N interactions
        self.interaction_count = 0
        
        logger.info("🎓 Initialized RL Service")
    
    def encode_state(self, message: str, conversation_history: List[Dict], 
                     session_context: Optional[Dict] = None) -> np.ndarray:
        """Encode current conversation state into feature vector
        
        Features include:
        - Message length
        - Presence of keywords (jira, confluence, issue key patterns)
        - Conversation length
        - Recent feedback scores
        - Time since last interaction
        """
        features = []
        
        # Message features
        message_lower = message.lower()
        features.append(len(message) / 1000.0)  # Normalized message length
        features.append(1.0 if 'jira' in message_lower else 0.0)
        features.append(1.0 if 'confluence' in message_lower else 0.0)
        features.append(1.0 if 'issue' in message_lower or 'ticket' in message_lower else 0.0)
        features.append(1.0 if any(c.isupper() and '-' in message and any(d.isdigit() for d in message) for c in message) else 0.0)  # Has issue key pattern
        features.append(1.0 if 'show' in message_lower or 'get' in message_lower or 'find' in message_lower else 0.0)
        features.append(1.0 if 'child' in message_lower or 'subtask' in message_lower else 0.0)
        features.append(1.0 if 'search' in message_lower or 'query' in message_lower else 0.0)
        features.append(1.0 if '?' in message else 0.0)  # Is question
        
        # Conversation history features
        features.append(len(conversation_history) / 50.0)  # Normalized history length
        
        # Count recent user messages
        recent_user_msgs = sum(1 for msg in conversation_history[-5:] if msg.get('role') == 'user')
        features.append(recent_user_msgs / 5.0)
        
        # Session context features
        if session_context:
            features.append(session_context.get('message_count', 0) / 100.0)
            features.append(session_context.get('avg_feedback', 0.0))
        else:
            features.append(0.0)
            features.append(0.0)
        
        # Pad to STATE_SIZE
        while len(features) < DQNAgent.STATE_SIZE:
            features.append(0.0)
        
        return np.array(features[:DQNAgent.STATE_SIZE], dtype=np.float32)
    
    def recommend_action(self, message: str, conversation_history: List[Dict], 
                        session_context: Optional[Dict] = None) -> str:
        """Recommend which action/tool to use based on current state
        
        Returns:
            Action name (e.g., 'search_jira', 'get_jira_issue')
        """
        state = self.encode_state(message, conversation_history, session_context)
        action_idx = self.agent.select_action(state, training=self.training_enabled)
        action_name = self.agent.get_action_name(action_idx)
        
        logger.info(f"🤖 RL Agent recommends: {action_name}")
        return action_name
    
    def record_interaction(self, db, session_id: str, message_id: int, 
                          state_vector: np.ndarray, action_taken: str):
        """Record an RL state-action pair in the database"""
        try:
            rl_state = RLState(
                session_id=session_id,
                message_id=message_id,
                state_vector=json.dumps(state_vector.tolist()),
                action_taken=action_taken,
                reward=0.0  # Will be updated when feedback is received
            )
            db.add(rl_state)
            db.commit()
            
            self.interaction_count += 1
            
            # Auto-train periodically
            if self.interaction_count % self.auto_train_interval == 0:
                self.train_from_database(db)
            
        except Exception as e:
            logger.error(f"❌ Error recording RL interaction: {e}")
            db.rollback()
    
    def update_reward_from_feedback(self, db, message_id: int, feedback_value: int):
        """Update reward for a previous interaction based on user feedback"""
        try:
            # Find the RL state for this message
            rl_state = db.query(RLState).filter(RLState.message_id == message_id).first()
            if not rl_state:
                logger.warning(f"⚠️ No RL state found for message {message_id}")
                return
            
            # Update reward
            rl_state.reward = float(feedback_value)
            db.commit()
            
            # Add to agent's memory for training
            state = np.array(json.loads(rl_state.state_vector))
            action_idx = self.agent.get_action_index(rl_state.action_taken)
            
            # Get next state if exists
            next_rl_state = db.query(RLState).filter(
                RLState.session_id == rl_state.session_id,
                RLState.id > rl_state.id
            ).first()
            
            if next_rl_state:
                next_state = np.array(json.loads(next_rl_state.state_vector))
                done = False
            else:
                next_state = state  # Terminal state
                done = True
            
            self.agent.remember(state, action_idx, float(feedback_value), next_state, done)
            
            logger.info(f"✅ Updated reward for message {message_id}: {feedback_value}")
            
            # Train immediately on negative feedback
            if feedback_value < 0:
                self.agent.train_step()
                self.agent.save_model(self.model_path)
            
        except Exception as e:
            logger.error(f"❌ Error updating reward: {e}")
            db.rollback()
    
    def train_from_database(self, db, num_episodes: int = 5):
        """Train the agent using historical data from database"""
        try:
            logger.info(f"🎓 Starting training from database...")
            
            # Get recent RL states with feedback
            rl_states = db.query(RLState).filter(RLState.reward != 0.0).order_by(RLState.id.desc()).limit(100).all()
            
            if len(rl_states) < 10:
                logger.info("ℹ️ Not enough training data yet")
                return
            
            # Build training episodes
            for _ in range(num_episodes):
                for rl_state in rl_states:
                    state = np.array(json.loads(rl_state.state_vector))
                    action_idx = self.agent.get_action_index(rl_state.action_taken)
                    
                    # Find next state
                    next_state_record = db.query(RLState).filter(
                        RLState.session_id == rl_state.session_id,
                        RLState.id > rl_state.id
                    ).first()
                    
                    if next_state_record:
                        next_state = np.array(json.loads(next_state_record.state_vector))
                        done = False
                    else:
                        next_state = state
                        done = True
                    
                    self.agent.remember(state, action_idx, rl_state.reward, next_state, done)
                
                # Train on batch
                self.agent.train_step()
            
            # Save updated model
            self.agent.save_model(self.model_path)
            logger.info(f"✅ Training complete! Epsilon: {self.agent.epsilon:.3f}")
            
        except Exception as e:
            logger.error(f"❌ Error during training: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get RL service statistics"""
        return {
            "enabled": self.training_enabled,
            "epsilon": self.agent.epsilon,
            "q_table_size": len(self.agent.q_table),
            "memory_size": len(self.agent.memory),
            "interaction_count": self.interaction_count,
            "actions": self.agent.ACTIONS
        }


# Global RL service instance
rl_service = RLService()

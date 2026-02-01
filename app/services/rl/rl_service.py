"""
RL Service - Main orchestrator for reinforcement learning.

Following Single Responsibility Principle:
- This service ONLY coordinates between agents, encoders, and rewards
- Actual logic is delegated to specialized components

Following Dependency Inversion Principle:
- Depends on abstractions (BaseAgent, BaseEncoder, BaseReward)
- Can swap implementations without changing this service
"""
import json
import logging
from typing import Dict, List, Optional, Any
import numpy as np

from app.models.database import RLState, Feedback
from app.config import settings

from .agents import DQNAgent, StyleAgent, BaseAgent
from .encoders import QueryEncoder, StyleEncoder, BaseEncoder
from .rewards import ToolReward, StyleReward, BaseReward

logger = logging.getLogger(__name__)


class RLService:
    """Unified RL service managing both tool selection and style learning.
    
    Architecture:
    - Tool Agent: Learns which tool (Jira, Confluence, KG) to use
    - Style Agent: Learns user's preferred response format
    
    Both agents learn from user feedback (thumbs up/down).
    """
    
    def __init__(
        self,
        tool_agent: Optional[BaseAgent] = None,
        style_agent: Optional[BaseAgent] = None,
        query_encoder: Optional[BaseEncoder] = None,
        style_encoder: Optional[BaseEncoder] = None,
        tool_reward: Optional[BaseReward] = None,
        style_reward: Optional[BaseReward] = None,
        model_dir: str = "./data/rl"
    ):
        """Initialize RL service with pluggable components.
        
        Args:
            tool_agent: Agent for tool selection (default: DQNAgent)
            style_agent: Agent for style selection (default: StyleAgent)
            query_encoder: Encoder for tool selection (default: QueryEncoder)
            style_encoder: Encoder for style selection (default: StyleEncoder)
            tool_reward: Reward calculator for tools (default: ToolReward)
            style_reward: Reward calculator for style (default: StyleReward)
            model_dir: Directory to save/load models
        """
        # Initialize components with defaults (DIP - can inject dependencies)
        self.tool_agent = tool_agent or DQNAgent()
        self.style_agent = style_agent or StyleAgent()
        self.query_encoder = query_encoder or QueryEncoder()
        self.style_encoder = style_encoder or StyleEncoder()
        self.tool_reward_calc = tool_reward or ToolReward()
        self.style_reward_calc = style_reward or StyleReward()
        
        # Model paths
        self.model_dir = model_dir
        self.tool_model_path = f"{model_dir}/tool_model.json"
        self.style_model_path = f"{model_dir}/style_model.json"
        
        # Load saved models
        self._load_models()
        
        # Training config
        self.training_enabled = True
        self.auto_train_interval = 10
        self.interaction_count = 0
        
        logger.info("🎓 RL Service initialized with tool + style learning")
    
    # =========================================================================
    # Backward Compatibility API
    # =========================================================================
    
    def encode_state(
        self,
        message: str,
        conversation_history: List[Dict],
        session_context: Optional[Dict] = None
    ) -> np.ndarray:
        """Backward compatible: Encode state for RL.
        
        Uses query encoder for tool selection state.
        """
        return self.query_encoder.encode(message, conversation_history, session_context)
    
    def recommend_action(
        self,
        message: str,
        conversation_history: List[Dict],
        session_context: Optional[Dict] = None
    ) -> str:
        """Backward compatible: Recommend action (tool).
        
        Wraps recommend_tool for legacy callers.
        """
        return self.recommend_tool(message, conversation_history, session_context)
    
    def _load_models(self):
        """Load saved models from disk."""
        import os
        os.makedirs(self.model_dir, exist_ok=True)
        
        self.tool_agent.load_model(self.tool_model_path)
        self.style_agent.load_model(self.style_model_path)
    
    def _save_models(self):
        """Save models to disk."""
        self.tool_agent.save_model(self.tool_model_path)
        self.style_agent.save_model(self.style_model_path)
    
    # =========================================================================
    # Tool Selection API
    # =========================================================================
    
    def recommend_tool(
        self,
        message: str,
        conversation_history: List[Dict],
        session_context: Optional[Dict] = None
    ) -> str:
        """Recommend which tool to use based on current state.
        
        Args:
            message: User's current message
            conversation_history: Previous messages in session
            session_context: Optional session metadata
            
        Returns:
            Tool name (e.g., 'search_jira', 'query_knowledge_graph')
        """
        state = self.query_encoder.encode(message, conversation_history, session_context)
        action_idx = self.tool_agent.select_action(state, training=self.training_enabled)
        tool_name = self.tool_agent.get_action_name(action_idx)
        
        logger.info(f"🤖 RL recommends tool: {tool_name}")
        return tool_name
    
    # =========================================================================
    # Style Selection API
    # =========================================================================
    
    def recommend_style(
        self,
        message: str,
        conversation_history: List[Dict],
        session_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Recommend response style based on user preferences.
        
        Args:
            message: User's current message
            conversation_history: Previous messages
            session_context: Optional session metadata
            
        Returns:
            Dict with 'primary_style' and 'style_hints'
        """
        state = self.style_encoder.encode(message, conversation_history, session_context)
        
        # Get top styles
        if hasattr(self.style_agent, 'select_multiple_styles'):
            top_styles = self.style_agent.select_multiple_styles(state, top_k=3)
        else:
            action_idx = self.style_agent.select_action(state, training=self.training_enabled)
            top_styles = [self.style_agent.get_action_name(action_idx)]
        
        # Get explicit hints from message
        style_hints = {}
        if hasattr(self.style_encoder, 'get_style_hints'):
            style_hints = self.style_encoder.get_style_hints(message)
        
        result = {
            'primary_style': top_styles[0] if top_styles else 'balanced',
            'recommended_styles': top_styles,
            'style_hints': style_hints
        }
        
        logger.info(f"🎨 RL recommends style: {result['primary_style']}")
        return result
    
    def get_style_prompt_modifier(
        self,
        message: str,
        conversation_history: List[Dict],
        session_context: Optional[Dict] = None
    ) -> str:
        """Get a prompt modifier string for the LLM based on style preferences.
        
        This can be appended to the system prompt to guide response style.
        """
        style_rec = self.recommend_style(message, conversation_history, session_context)
        
        modifiers = []
        primary = style_rec['primary_style']
        hints = style_rec.get('style_hints', {})
        
        # Map styles to prompt instructions
        style_instructions = {
            'concise': "Be concise and direct. Avoid unnecessary elaboration.",
            'detailed': "Provide comprehensive explanations with context.",
            'balanced': "Provide clear, moderately detailed responses.",
            'prose': "Write in paragraph form with flowing text.",
            'bullets': "Use bullet points for clarity and easy scanning.",
            'table': "Use tables when comparing or listing structured data.",
            'mixed': "Mix prose with bullet points as appropriate.",
            'with_examples': "Include concrete examples to illustrate points.",
            'with_context': "Provide background context before answering.",
            'direct_answer': "Answer directly without preamble.",
        }
        
        if primary in style_instructions:
            modifiers.append(style_instructions[primary])
        
        # Apply explicit hints
        if hints.get('wants_brief'):
            modifiers.append("Keep the response brief.")
        if hints.get('wants_list'):
            modifiers.append("Format as a list.")
        if hints.get('wants_examples'):
            modifiers.append("Include examples.")
        
        return " ".join(modifiers) if modifiers else ""
    
    # =========================================================================
    # Learning & Feedback API
    # =========================================================================
    
    def record_interaction(
        self,
        db,
        session_id: str,
        message_id: int,
        message: str,
        conversation_history: List[Dict],
        tool_used: str,
        style_used: str,
        session_context: Optional[Dict] = None
    ):
        """Record an interaction for future learning.
        
        Args:
            db: Database session
            session_id: Current session ID
            message_id: Message ID
            message: User message
            conversation_history: Conversation history
            tool_used: Tool that was used
            style_used: Style that was used
            session_context: Optional session context
        """
        try:
            # Encode states
            tool_state = self.query_encoder.encode(message, conversation_history, session_context)
            style_state = self.style_encoder.encode(message, conversation_history, session_context)
            
            # Create RL state record
            rl_state = RLState(
                session_id=session_id,
                message_id=message_id,
                state_vector=json.dumps({
                    'tool_state': tool_state.tolist(),
                    'style_state': style_state.tolist()
                }),
                action_taken=json.dumps({
                    'tool': tool_used,
                    'style': style_used
                }),
                reward=0.0  # Updated when feedback received
            )
            db.add(rl_state)
            db.commit()
            
            self.interaction_count += 1
            
            # Auto-train periodically
            if self.interaction_count % self.auto_train_interval == 0:
                self._auto_train()
            
        except Exception as e:
            logger.error(f"❌ Error recording interaction: {e}")
            db.rollback()
    
    def update_from_feedback(
        self,
        db,
        message_id: int,
        feedback_value: int,
        interaction_data: Optional[Dict] = None
    ):
        """Update agents based on user feedback.
        
        Args:
            db: Database session
            message_id: Message that received feedback
            feedback_value: -1 (thumbs down), 0 (neutral), 1 (thumbs up)
            interaction_data: Optional additional context
        """
        try:
            # Find the RL state
            rl_state = db.query(RLState).filter(RLState.message_id == message_id).first()
            if not rl_state:
                logger.warning(f"⚠️ No RL state for message {message_id}")
                return
            
            # Calculate rewards
            tool_reward = self.tool_reward_calc.calculate(feedback_value, interaction_data)
            style_reward = self.style_reward_calc.calculate(feedback_value, interaction_data)
            
            # Update stored reward
            rl_state.reward = (tool_reward + style_reward) / 2
            db.commit()
            
            # Parse states and actions
            states = json.loads(rl_state.state_vector)
            actions = json.loads(rl_state.action_taken)
            
            tool_state = np.array(states['tool_state'])
            style_state = np.array(states['style_state'])
            tool_action = self.tool_agent.get_action_index(actions['tool'])
            style_action = self.style_agent.get_action_index(actions['style'])
            
            # Find next state if exists
            next_rl_state = db.query(RLState).filter(
                RLState.session_id == rl_state.session_id,
                RLState.id > rl_state.id
            ).first()
            
            done = next_rl_state is None
            
            if next_rl_state:
                next_states = json.loads(next_rl_state.state_vector)
                next_tool_state = np.array(next_states['tool_state'])
                next_style_state = np.array(next_states['style_state'])
            else:
                next_tool_state = tool_state
                next_style_state = style_state
            
            # Store experiences
            self.tool_agent.remember(tool_state, tool_action, tool_reward, next_tool_state, done)
            self.style_agent.remember(style_state, style_action, style_reward, next_style_state, done)
            
            logger.info(f"✅ Feedback processed: tool_reward={tool_reward:.2f}, style_reward={style_reward:.2f}")
            
            # Immediate training on negative feedback
            if feedback_value < 0:
                self.tool_agent.train_step()
                self.style_agent.train_step()
                self._save_models()
            
        except Exception as e:
            logger.error(f"❌ Error updating from feedback: {e}")
            db.rollback()
    
    def _auto_train(self):
        """Perform automatic training."""
        self.tool_agent.train_step()
        self.style_agent.train_step()
        self._save_models()
        logger.info("🔄 Auto-training completed")
    
    def train_from_database(self, db, num_episodes: int = 5):
        """Train agents using historical data."""
        try:
            logger.info("🎓 Training from database...")
            
            rl_states = db.query(RLState).filter(
                RLState.reward != 0.0
            ).order_by(RLState.id.desc()).limit(100).all()
            
            if len(rl_states) < 10:
                logger.info("ℹ️ Not enough training data")
                return
            
            for _ in range(num_episodes):
                for rl_state in rl_states:
                    try:
                        states = json.loads(rl_state.state_vector)
                        actions = json.loads(rl_state.action_taken)
                        
                        tool_state = np.array(states['tool_state'])
                        style_state = np.array(states['style_state'])
                        tool_action = self.tool_agent.get_action_index(actions['tool'])
                        style_action = self.style_agent.get_action_index(actions['style'])
                        
                        # Use stored reward for both
                        reward = rl_state.reward
                        
                        # Simplified: use same state as next_state for terminal
                        self.tool_agent.remember(tool_state, tool_action, reward, tool_state, True)
                        self.style_agent.remember(style_state, style_action, reward, style_state, True)
                        
                    except (json.JSONDecodeError, KeyError):
                        continue
                
                self.tool_agent.train_step()
                self.style_agent.train_step()
            
            self._save_models()
            logger.info(f"✅ Training complete!")
            
        except Exception as e:
            logger.error(f"❌ Training error: {e}")
    
    # =========================================================================
    # Statistics API
    # =========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive RL statistics."""
        return {
            "enabled": self.training_enabled,
            "interaction_count": self.interaction_count,
            "tool_agent": self.tool_agent.get_stats(),
            "style_agent": self.style_agent.get_stats(),
            "model_dir": self.model_dir
        }


# Global singleton (lazy initialization)
_rl_service: Optional[RLService] = None


def get_rl_service() -> RLService:
    """Get or create the global RL service instance."""
    global _rl_service
    if _rl_service is None:
        _rl_service = RLService()
    return _rl_service


# Backward compatibility alias
rl_service = property(lambda self: get_rl_service())

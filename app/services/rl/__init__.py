"""
Reinforcement Learning module for agentic AI optimization.

This module provides:
- Tool selection learning (which tool to use for a query)
- Style learning (how to format responses based on user preferences)

Architecture follows SOLID principles:
- S: Each component has single responsibility
- O: Open for extension via base classes
- L: All agents/encoders/rewards are substitutable
- I: Segregated interfaces for different concerns
- D: High-level RLService depends on abstractions

Usage:
    from app.services.rl import get_rl_service
    
    rl = get_rl_service()
    tool = rl.recommend_tool(message, history)
    style = rl.recommend_style(message, history)
"""
from .rl_service import RLService, get_rl_service
from .agents import BaseAgent, DQNAgent, StyleAgent
from .encoders import BaseEncoder, QueryEncoder, StyleEncoder
from .rewards import BaseReward, ToolReward, StyleReward

__all__ = [
    # Main service
    "RLService",
    "get_rl_service",
    
    # Agents
    "BaseAgent",
    "DQNAgent", 
    "StyleAgent",
    
    # Encoders
    "BaseEncoder",
    "QueryEncoder",
    "StyleEncoder",
    
    # Rewards
    "BaseReward",
    "ToolReward",
    "StyleReward",
]

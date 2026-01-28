"""
RL Metrics API for exposing learning progress and Q-values
"""
from fastapi import APIRouter
from typing import Dict, Any
import logging

from app.services.rl_service import rl_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/metrics")
async def get_rl_metrics() -> Dict[str, Any]:
    """Get reinforcement learning metrics and statistics"""
    try:
        # Get basic stats from RL service
        stats = rl_service.get_stats()
        
        metrics = {
            "training_enabled": stats["enabled"],
            "q_table_size": stats["q_table_size"],
            "total_actions": len(stats["actions"]),
            "actions": stats["actions"],
            "exploration_rate": stats["epsilon"],
            "memory_size": stats["memory_size"],
            "interaction_count": stats["interaction_count"],
            "learning_stats": {}
        }
        
        # Calculate statistics per action from Q-table
        action_stats = {}
        agent = rl_service.agent
        
        for action_name in agent.ACTIONS:
            action_idx = agent.get_action_index(action_name)
            q_values = []
            
            for state_hash in agent.q_table:
                q_values.append(agent.q_table[state_hash][action_idx])
            
            if q_values:
                action_stats[action_name] = {
                    "num_states": len(q_values),
                    "avg_q_value": float(sum(q_values) / len(q_values)),
                    "max_q_value": float(max(q_values)),
                    "min_q_value": float(min(q_values))
                }
        
        metrics["action_statistics"] = action_stats
        
        # Get top 10 most valuable state-action pairs
        top_pairs = []
        for state_hash in agent.q_table:
            for action_idx, q_value in enumerate(agent.q_table[state_hash]):
                top_pairs.append({
                    "state": state_hash,
                    "action": agent.ACTIONS[action_idx],
                    "q_value": float(q_value)
                })
        
        top_pairs.sort(key=lambda x: x["q_value"], reverse=True)
        metrics["top_state_actions"] = top_pairs[:10]
        
        # Get worst performing pairs (negative learning)
        worst_pairs = sorted(top_pairs, key=lambda x: x["q_value"])[:10]
        metrics["worst_state_actions"] = worst_pairs
        
        return metrics
    
    except Exception as e:
        logger.error(f"Error getting RL metrics: {e}", exc_info=True)
        return {"error": str(e)}


@router.get("/action-distribution")
async def get_action_distribution() -> Dict[str, int]:
    """Get distribution of actions taken (based on Q-table)"""
    agent = rl_service.agent
    action_counts = {action: 0 for action in agent.ACTIONS}
    
    for state_hash in agent.q_table:
        # Find action with highest Q-value for each state
        best_action_idx = int(agent.q_table[state_hash].argmax())
        best_action = agent.ACTIONS[best_action_idx]
        action_counts[best_action] += 1
    
    return action_counts


@router.get("/learning-progress")
async def get_learning_progress() -> Dict[str, Any]:
    """Get learning progress over time"""
    stats = rl_service.get_stats()
    agent = rl_service.agent
    
    progress = {
        "total_states_explored": stats["q_table_size"],
        "exploration_rate": stats["epsilon"],
        "discount_factor": agent.gamma,
        "learning_rate": agent.learning_rate,
        "memory_size": stats["memory_size"],
        "interaction_count": stats["interaction_count"],
        "status": "Learning in progress" if stats["epsilon"] > 0.1 else "Mostly exploiting"
    }
    
    # Calculate average Q-value per action (shows learning progress)
    avg_q_per_action = {}
    for action_name in agent.ACTIONS:
        action_idx = agent.get_action_index(action_name)
        q_values = []
        for state_hash in agent.q_table:
            q_values.append(agent.q_table[state_hash][action_idx])
        if q_values:
            avg_q_per_action[action_name] = float(sum(q_values) / len(q_values))
    
    progress["average_q_values"] = avg_q_per_action
    
    return progress

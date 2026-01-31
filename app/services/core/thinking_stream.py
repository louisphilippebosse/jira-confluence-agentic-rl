"""
Thinking Stream Service

Provides real-time thinking process updates to the UI.
Shows what the AI is doing: planning, searching, reflecting, etc.
"""

import logging
from typing import Dict, Any, Callable, Optional, Union
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)


class ThinkingStream:
    """
    Manages thinking process updates that can be sent to the UI
    """
    
    def __init__(self):
        self.callbacks = []
        self.current_session = None
    
    def register_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Register a callback function to receive thinking updates"""
        self.callbacks.append(callback)
    
    def clear_callbacks(self):
        """Clear all registered callbacks"""
        self.callbacks.clear()
    
    async def emit(self, event_data: Union[str, Dict[str, Any]], session_id: str = None, data: Dict[str, Any] = None):
        """
        Emit a thinking process event
        
        Can be called two ways:
        1. emit({"type": "planning", "message": "..."}, session_id)
        2. emit("planning", session_id, {"message": "..."})
        
        Event types:
        - "thinking_start": AI is beginning to think
        - "planning": AI is creating a search plan
        - "executing": AI is executing a search step
        - "reflecting": AI is evaluating results
        - "adapting": AI is modifying the plan
        - "complete": Search complete
        - "thinking_error": An error occurred
        """
        # Handle both calling conventions
        if isinstance(event_data, dict):
            event_type = event_data.get("type", "unknown")
            event_content = event_data
        else:
            event_type = event_data
            event_content = data or {}
        
        event = {
            "type": event_type,
            "data": event_content,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
        # Log the event
        logger.info(f"💭 {event_type.upper()}: {data.get('message', '')}")
        
        # Send to all registered callbacks
        for callback in self.callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Error in thinking stream callback: {e}")
    
    async def plan_created(self, plan: Dict[str, Any], session_id: str = None):
        """Emit when a search plan is created"""
        await self.emit("planning", {
            "message": f"📋 Created plan with {len(plan.get('steps', []))} steps",
            "reasoning": plan.get("reasoning", ""),
            "steps": [s.get("action") for s in plan.get("steps", [])]
        }, session_id)
    
    async def step_executing(self, step: Dict[str, Any], iteration: int, session_id: str = None):
        """Emit when executing a search step"""
        action = step.get("action", "unknown")
        icons = {
            "search_jira": "🔍",
            "search_web": "🌐",
            "follow_web_links": "🔗",
            "search_kg": "🕸️",
            "get_jira_issue": "📋"
        }
        icon = icons.get(action, "⚙️")
        
        await self.emit("executing", {
            "message": f"{icon} Step {iteration}: {action}",
            "action": action,
            "reason": step.get("reason", ""),
            "iteration": iteration
        }, session_id)
    
    async def reflection(self, reflection: Dict[str, Any], iteration: int, session_id: str = None):
        """Emit when AI reflects on results"""
        assessment = reflection.get("assessment", "unknown")
        next_action = reflection.get("next_action", "unknown")
        
        icons = {
            "complete": "✅",
            "partial": "⏳",
            "insufficient": "⚠️",
            "none": "❌"
        }
        icon = icons.get(assessment, "🤔")
        
        await self.emit("reflecting", {
            "message": f"{icon} Assessment: {assessment} → {next_action}",
            "assessment": assessment,
            "next_action": next_action,
            "reasoning": reflection.get("reasoning", ""),
            "iteration": iteration
        }, session_id)
    
    async def adapting(self, modification: Dict[str, Any], session_id: str = None):
        """Emit when AI adapts the plan"""
        await self.emit("adapting", {
            "message": f"🔧 Modifying plan: {modification.get('reason', '')}",
            "new_action": modification.get("action", ""),
            "reason": modification.get("reason", "")
        }, session_id)
    
    async def complete(self, total_iterations: int, session_id: str = None):
        """Emit when search is complete"""
        await self.emit("complete", {
            "message": f"🎉 Search complete ({total_iterations} iterations)",
            "iterations": total_iterations
        }, session_id)
    
    async def simple_action(self, action: str, details: str = "", session_id: str = None):
        """Emit a simple action message (for non-agentic searches)"""
        icons = {
            "searching_jira": "🔍",
            "searching_web": "🌐",
            "analyzing": "🤔",
            "synthesizing": "📝",
            "verifying": "✓"
        }
        icon = icons.get(action, "⚙️")
        
        await self.emit("executing", {
            "message": f"{icon} {action.replace('_', ' ').title()}{': ' + details if details else ''}",
            "action": action
        }, session_id)


# Global singleton
thinking_stream = ThinkingStream()

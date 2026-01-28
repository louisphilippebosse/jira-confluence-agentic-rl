"""
Approval API for AI agent write operations
Handles user approval workflow for create/update/delete operations
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging
import uuid
from datetime import datetime

from app.services.jira_service import jira_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/approvals", tags=["approvals"])

# In-memory approval queue (use Redis/DB in production)
pending_approvals: Dict[str, Dict[str, Any]] = {}


class ApprovalRequest(BaseModel):
    action: str
    parameters: Dict[str, Any]
    reason: Optional[str] = None


class ApprovalResponse(BaseModel):
    approval_id: str
    approved: bool
    reason: Optional[str] = None


@router.post("/request")
async def request_approval(request: ApprovalRequest):
    """
    Agent requests approval for a write operation
    Returns approval_id for tracking
    """
    approval_id = str(uuid.uuid4())
    
    approval_data = {
        "id": approval_id,
        "action": request.action,
        "parameters": request.parameters,
        "reason": request.reason,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "preview": _generate_preview(request.action, request.parameters)
    }
    
    pending_approvals[approval_id] = approval_data
    
    logger.info(f"📋 Approval requested: {approval_id} - {request.action}")
    
    return {
        "approval_id": approval_id,
        "status": "pending",
        "message": "Waiting for user approval",
        "preview": approval_data["preview"]
    }


@router.get("/pending")
async def get_pending_approvals():
    """Get all pending approval requests"""
    return {
        "pending": [
            {
                "id": aid,
                "action": data["action"],
                "parameters": data["parameters"],
                "preview": data["preview"],
                "created_at": data["created_at"]
            }
            for aid, data in pending_approvals.items()
            if data["status"] == "pending"
        ]
    }


@router.post("/approve/{approval_id}")
async def approve_request(approval_id: str, response: ApprovalResponse):
    """
    User approves or rejects a write operation
    If approved, executes the action
    """
    if approval_id not in pending_approvals:
        raise HTTPException(status_code=404, detail="Approval request not found")
    
    approval = pending_approvals[approval_id]
    
    if approval["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Request already {approval['status']}")
    
    if response.approved:
        # Execute the approved action
        logger.info(f"✅ Executing approved action: {approval['action']}")
        
        try:
            result = await _execute_action(approval["action"], approval["parameters"])
            
            approval["status"] = "approved"
            approval["executed_at"] = datetime.utcnow().isoformat()
            approval["result"] = result
            
            return {
                "status": "executed",
                "result": result,
                "message": f"Action {approval['action']} completed successfully"
            }
            
        except Exception as e:
            logger.error(f"❌ Error executing action: {e}", exc_info=True)
            approval["status"] = "failed"
            approval["error"] = str(e)
            
            raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")
    
    else:
        # User rejected
        approval["status"] = "rejected"
        approval["rejected_at"] = datetime.utcnow().isoformat()
        approval["rejection_reason"] = response.reason
        
        logger.info(f"❌ Action rejected: {approval['action']}")
        
        return {
            "status": "rejected",
            "message": "Action cancelled by user"
        }


async def _execute_action(action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Execute an approved action"""
    
    if action == "create_jira_issue":
        result = jira_service.create_issue(
            project_key=parameters["project_key"],
            summary=parameters["summary"],
            issue_type=parameters.get("issue_type", "Task"),
            description=parameters.get("description", ""),
            parent_key=parameters.get("parent_key"),
            assignee=parameters.get("assignee"),
            priority=parameters.get("priority"),
            labels=parameters.get("labels")
        )
        
        # Add newly created issue to knowledge graph
        if result and result.get("key"):
            from app.services.knowledge_graph_service import knowledge_graph_service
            logger.info(f"💾 Adding newly created issue {result['key']} to Knowledge Graph")
            knowledge_graph_service.add_jira_issue(result)
        
        return result or {"error": "Failed to create issue"}
    
    elif action == "update_jira_issue":
        issue_key = parameters.pop("issue_key")
        # Remove internal flags
        parameters.pop("approval_required", None)
        
        fields = {}
        
        # Handle generic field/value pattern (from AI agent)
        if "field" in parameters and "value" in parameters:
            field_name = parameters["field"]
            field_value = parameters["value"]
            
            # Map common field names to Jira field format
            if field_name == "priority":
                fields["priority"] = {"name": field_value}
            elif field_name == "summary":
                fields["summary"] = field_value
            elif field_name == "description":
                fields["description"] = field_value
            elif field_name == "assignee":
                fields["assignee"] = {"name": field_value}
            elif field_name == "labels":
                fields["labels"] = field_value if isinstance(field_value, list) else [field_value]
            else:
                # Generic field update
                fields[field_name] = field_value
        else:
            # Handle direct field parameters (backward compatibility)
            if "summary" in parameters:
                fields["summary"] = parameters["summary"]
            if "description" in parameters:
                fields["description"] = parameters["description"]
            if "assignee" in parameters:
                fields["assignee"] = {"name": parameters["assignee"]}
            if "priority" in parameters:
                fields["priority"] = {"name": parameters["priority"]}
            if "labels" in parameters:
                fields["labels"] = parameters["labels"]
        
        success = jira_service.update_issue(issue_key, fields)
        return {"success": success, "issue_key": issue_key, "updated_fields": list(fields.keys())}
    
    elif action == "transition_jira_issue":
        success = jira_service.transition_issue(
            issue_key=parameters["issue_key"],
            transition_name=parameters["transition_name"]
        )
        return {"success": success, "issue_key": parameters["issue_key"]}
    
    else:
        raise ValueError(f"Unknown action: {action}")


def _generate_preview(action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a human-readable preview of the action"""
    
    if action == "create_jira_issue":
        return {
            "type": "Create Issue",
            "project": parameters["project_key"],
            "summary": parameters["summary"],
            "issue_type": parameters.get("issue_type", "Task"),
            "description_preview": parameters.get("description", "")[:200]
        }
    
    elif action == "update_jira_issue":
        changes = {k: v for k, v in parameters.items() if k not in ["issue_key", "approval_required"]}
        return {
            "type": "Update Issue",
            "issue": parameters["issue_key"],
            "changes": changes
        }
    
    elif action == "transition_jira_issue":
        return {
            "type": "Change Status",
            "issue": parameters["issue_key"],
            "new_status": parameters["transition_name"]
        }
    
    return {}

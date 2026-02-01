"""
Skill Orchestration API - Skill-based query execution
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging

from app.models.database import get_db
from app.services.core.skill_orchestrator import SkillOrchestrator
from app.services.core.skill_registry import get_skill_registry
from app.services.core.agent_orchestrator import agent_orchestrator
from app.services.tools.jira.jira_service import jira_service
from app.services.tools.confluence.confluence_service import confluence_service
from app.services.graphrag.knowledge_graph_service import knowledge_graph_service

logger = logging.getLogger(__name__)

router = APIRouter()


class SkillQueryRequest(BaseModel):
    """Request for skill-based query"""
    query: str
    context: Optional[Dict[str, Any]] = None


class SkillQueryResponse(BaseModel):
    """Response from skill orchestration"""
    answer: str
    sources: List[str]
    skill_results: List[Dict[str, Any]]
    reasoning: str


class SkillListResponse(BaseModel):
    """Response listing available skills"""
    skills: List[Dict[str, str]]


@router.get("/skills/available", response_model=SkillListResponse)
async def list_available_skills():
    """List all available skills from the registry"""
    try:
        registry = get_skill_registry()
        skills_metadata = registry.get_skills_metadata()
        logger.info(f"📋 Listing {len(skills_metadata)} skills")
        return SkillListResponse(skills=skills_metadata)
    except Exception as e:
        logger.error(f"❌ Error listing skills: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills/query", response_model=SkillQueryResponse)
async def query_with_skills(request: SkillQueryRequest, db: Session = Depends(get_db)):
    """
    Execute a query using skill-based orchestration.
    
    This endpoint uses the skill architecture:
    1. Skill Registry discovers relevant skills
    2. Skill Orchestrator executes them
    3. Multi-source synthesis combines results
    """
    try:
        logger.info(f"🎯 Skill-based query: {request.query}")
        
        orchestrator = SkillOrchestrator(
            llm=agent_orchestrator.llm,
            jira_service=jira_service,
            confluence_service=confluence_service,
            kg_service=knowledge_graph_service
        )
        
        result = await orchestrator.execute_query(request.query, request.context)
        logger.info(f"✅ Skill orchestration complete - used {len(result['sources'])} skill(s)")
        
        return SkillQueryResponse(**result)
        
    except Exception as e:
        logger.error(f"❌ Skill orchestration failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills/{skill_name}")
async def get_skill_details(skill_name: str):
    """Get detailed information about a specific skill"""
    try:
        registry = get_skill_registry()
        skill = registry.get_skill(skill_name)
        
        if not skill:
            raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
        
        return {
            "name": skill.name,
            "description": skill.description,
            "instructions": skill.instructions,
            "metadata": skill.metadata,
            "has_references": skill.references_dir is not None,
            "has_scripts": skill.scripts_dir is not None,
            "has_assets": skill.assets_dir is not None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting skill details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

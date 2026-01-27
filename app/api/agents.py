"""API endpoints for managing skills and agents"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
import logging

from app.models.database import get_db, Agent, Skill, AgentSkill
from app.models.schemas import (
    SkillCreate, SkillUpdate, SkillResponse,
    AgentCreate, AgentUpdate, AgentResponse, AgentSkillAdd
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ============ SKILLS ENDPOINTS ============

@router.post("/skills", response_model=SkillResponse, status_code=201)
async def create_skill(skill: SkillCreate, db: Session = Depends(get_db)):
    """Create a new skill"""
    try:
        # Check if skill name already exists
        existing = db.query(Skill).filter(Skill.name == skill.name).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Skill '{skill.name}' already exists")
        
        db_skill = Skill(**skill.dict())
        db.add(db_skill)
        db.commit()
        db.refresh(db_skill)
        logger.info(f"✨ Created skill: {skill.name}")
        return db_skill
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating skill: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills", response_model=List[SkillResponse])
async def list_skills(
    category: str = None,
    enabled: bool = None,
    db: Session = Depends(get_db)
):
    """List all skills with optional filtering"""
    try:
        query = db.query(Skill)
        
        if category:
            query = query.filter(Skill.category == category)
        if enabled is not None:
            query = query.filter(Skill.enabled == enabled)
        
        skills = query.all()
        return skills
        
    except Exception as e:
        logger.error(f"❌ Error listing skills: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills/{skill_id}", response_model=SkillResponse)
async def get_skill(skill_id: int, db: Session = Depends(get_db)):
    """Get a specific skill"""
    try:
        skill = db.query(Skill).filter(Skill.id == skill_id).first()
        if not skill:
            raise HTTPException(status_code=404, detail="Skill not found")
        return skill
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting skill: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/skills/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: int,
    skill_update: SkillUpdate,
    db: Session = Depends(get_db)
):
    """Update a skill"""
    try:
        skill = db.query(Skill).filter(Skill.id == skill_id).first()
        if not skill:
            raise HTTPException(status_code=404, detail="Skill not found")
        
        update_data = skill_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(skill, field, value)
        
        db.commit()
        db.refresh(skill)
        logger.info(f"✏️ Updated skill: {skill.name}")
        return skill
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating skill: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/skills/{skill_id}")
async def delete_skill(skill_id: int, db: Session = Depends(get_db)):
    """Delete a skill"""
    try:
        skill = db.query(Skill).filter(Skill.id == skill_id).first()
        if not skill:
            raise HTTPException(status_code=404, detail="Skill not found")
        
        skill_name = skill.name
        db.delete(skill)
        db.commit()
        logger.info(f"🗑️ Deleted skill: {skill_name}")
        return {"message": f"Skill '{skill_name}' deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting skill: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============ AGENTS ENDPOINTS ============

@router.post("/agents", response_model=AgentResponse, status_code=201)
async def create_agent(agent: AgentCreate, db: Session = Depends(get_db)):
    """Create a new agent"""
    try:
        # Check if agent name already exists
        existing = db.query(Agent).filter(Agent.name == agent.name).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Agent '{agent.name}' already exists")
        
        # Create agent
        agent_data = agent.dict(exclude={'skill_ids'})
        db_agent = Agent(**agent_data)
        db.add(db_agent)
        db.flush()  # Get the agent ID
        
        # Add skills
        if agent.skill_ids:
            for skill_id in agent.skill_ids:
                skill = db.query(Skill).filter(Skill.id == skill_id).first()
                if not skill:
                    raise HTTPException(status_code=404, detail=f"Skill {skill_id} not found")
                
                agent_skill = AgentSkill(agent_id=db_agent.id, skill_id=skill_id)
                db.add(agent_skill)
        
        db.commit()
        db.refresh(db_agent)
        logger.info(f"🤖 Created agent: {agent.name} with {len(agent.skill_ids or [])} skills")
        return db_agent
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating agent: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents", response_model=List[AgentResponse])
async def list_agents(is_active: bool = None, db: Session = Depends(get_db)):
    """List all agents"""
    try:
        query = db.query(Agent)
        
        if is_active is not None:
            query = query.filter(Agent.is_active == is_active)
        
        agents = query.all()
        return agents
        
    except Exception as e:
        logger.error(f"❌ Error listing agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: int, db: Session = Depends(get_db)):
    """Get a specific agent with its skills"""
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return agent
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/agents/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: int,
    agent_update: AgentUpdate,
    db: Session = Depends(get_db)
):
    """Update an agent"""
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        update_data = agent_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(agent, field, value)
        
        db.commit()
        db.refresh(agent)
        logger.info(f"✏️ Updated agent: {agent.name}")
        return agent
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating agent: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/{agent_id}/skills")
async def add_skill_to_agent(
    agent_id: int,
    skill_add: AgentSkillAdd,
    db: Session = Depends(get_db)
):
    """Add a skill to an agent"""
    try:
        # Verify agent exists
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # Verify skill exists
        skill = db.query(Skill).filter(Skill.id == skill_add.skill_id).first()
        if not skill:
            raise HTTPException(status_code=404, detail="Skill not found")
        
        # Check if already linked
        existing = db.query(AgentSkill).filter(
            AgentSkill.agent_id == agent_id,
            AgentSkill.skill_id == skill_add.skill_id
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail="Skill already linked to agent")
        
        # Add the skill
        agent_skill = AgentSkill(
            agent_id=agent_id,
            skill_id=skill_add.skill_id,
            priority=skill_add.priority,
            enabled=skill_add.enabled
        )
        db.add(agent_skill)
        db.commit()
        
        logger.info(f"🔗 Added skill '{skill.name}' to agent '{agent.name}'")
        return {"message": f"Skill '{skill.name}' added to agent '{agent.name}'"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error adding skill to agent: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/agents/{agent_id}/skills/{skill_id}")
async def remove_skill_from_agent(
    agent_id: int,
    skill_id: int,
    db: Session = Depends(get_db)
):
    """Remove a skill from an agent"""
    try:
        agent_skill = db.query(AgentSkill).filter(
            AgentSkill.agent_id == agent_id,
            AgentSkill.skill_id == skill_id
        ).first()
        
        if not agent_skill:
            raise HTTPException(status_code=404, detail="Skill not linked to agent")
        
        db.delete(agent_skill)
        db.commit()
        
        logger.info(f"🔓 Removed skill {skill_id} from agent {agent_id}")
        return {"message": "Skill removed from agent successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error removing skill from agent: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: int, db: Session = Depends(get_db)):
    """Delete an agent"""
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        agent_name = agent.name
        db.delete(agent)
        db.commit()
        logger.info(f"🗑️ Deleted agent: {agent_name}")
        return {"message": f"Agent '{agent_name}' deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting agent: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

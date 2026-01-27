from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from app.config import settings

Base = declarative_base()


class Conversation(Base):
    """Model to store conversation history"""
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=False)
    role = Column(String, nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    extra_data = Column(Text, nullable=True)  # JSON string for additional data


class Session(Base):
    """Model to store session metadata"""
    __tablename__ = "sessions"
    
    session_id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=True)  # Auto-generated title
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    message_count = Column(Integer, default=0)


class Feedback(Base):
    """Model to store user feedback on AI responses"""
    __tablename__ = "feedback"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=False)
    message_id = Column(Integer, ForeignKey('conversations.id'), nullable=False)
    feedback_value = Column(Integer, nullable=False)  # 1 for thumbs up, -1 for thumbs down
    timestamp = Column(DateTime, default=datetime.utcnow)
    comment = Column(Text, nullable=True)  # Optional user comment


class Agent(Base):
    """Model to store AI agents with their configurations"""
    __tablename__ = "agents"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    model_name = Column(String, nullable=False)  # e.g., 'llama3.2:latest'
    system_prompt = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    skills = relationship("AgentSkill", back_populates="agent", cascade="all, delete-orphan")


class Skill(Base):
    """Model to store skills that agents can have"""
    __tablename__ = "skills"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=True)  # e.g., 'jira', 'confluence', 'knowledge_graph'
    function_name = Column(String, nullable=False)  # Name of the Python function to call
    parameters_schema = Column(Text, nullable=True)  # JSON schema for parameters
    returns_schema = Column(Text, nullable=True)  # JSON schema for return value
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    agents = relationship("AgentSkill", back_populates="skill", cascade="all, delete-orphan")


class AgentSkill(Base):
    """Junction table linking agents to their skills"""
    __tablename__ = "agent_skills"
    
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey('agents.id'), nullable=False)
    skill_id = Column(Integer, ForeignKey('skills.id'), nullable=False)
    priority = Column(Integer, default=0)  # Higher priority skills are tried first
    enabled = Column(Boolean, default=True)
    added_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    agent = relationship("Agent", back_populates="skills")
    skill = relationship("Skill", back_populates="agents")


class RLState(Base):
    """Model to store RL agent states and actions for training"""
    __tablename__ = "rl_states"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=False)
    message_id = Column(Integer, ForeignKey('conversations.id'), nullable=False)
    state_vector = Column(Text, nullable=False)  # JSON array of state features
    action_taken = Column(String, nullable=False)  # Which tool/skill was used
    reward = Column(Float, default=0.0)  # Reward from user feedback
    next_state_vector = Column(Text, nullable=True)  # State after action
    timestamp = Column(DateTime, default=datetime.utcnow)


# Database setup
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency for getting database sessions"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

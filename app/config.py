from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings with security-first approach"""
    
    # OpenAI Configuration
    openai_api_key: str
    
    # Jira Configuration (Read-Only)
    jira_url: str
    jira_username: str
    jira_api_token: str
    
    # Confluence Configuration (Read-Only)
    confluence_url: str
    confluence_username: str
    confluence_api_token: str
    
    # Application Configuration
    database_url: str = "sqlite:///./data/conversations.db"
    secret_key: str
    environment: str = "production"
    
    # Security Settings
    allowed_origins: str = "http://localhost:8000"
    max_conversation_history: int = 50
    
    @property
    def allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",")]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

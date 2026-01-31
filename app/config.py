from pydantic_settings import BaseSettings
from typing import List, Literal


class Settings(BaseSettings):
    """Application settings with security-first approach"""
    
    # OpenAI Configuration (optional)
    openai_api_key: str = ""
    
    # Ollama Configuration (for local LLM)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:latest"
    
    # LLM Provider Selection
    llm_provider: Literal["openai", "ollama"] = "ollama"
    
    # Jira Configuration (Read-Only)
    jira_url: str
    jira_username: str
    jira_api_token: str
    
    # Confluence Configuration (Read-Only)
    confluence_url: str
    confluence_username: str
    confluence_api_token: str
    confluence_personal_space: str = ""  # Optional: Filter searches to personal space (e.g., ~accountid)
    
    # Application Configuration
    database_url: str = "sqlite:///./data/conversations.db"
    secret_key: str
    environment: str = "production"
    
    # Security Settings
    allowed_origins: str = "http://localhost:8000"
    max_conversation_history: int = 50
    
    # Knowledge Graph Configuration
    enable_knowledge_graph: bool = True
    knowledge_graph_path: str = "./data/knowledge_graph.gpickle"
    
    # Nano-GraphRAG Configuration (unified Graph + Vector RAG)
    enable_nano_graphrag: bool = True
    nano_graphrag_working_dir: str = "./data/nano_graphrag"
    ollama_embedding_model: str = "nomic-embed-text"
    
    # MCP (Model Context Protocol) Configuration
    enable_mcp: bool = True
    mcp_proxy_url: str = "http://localhost:3000"
    
    @property
    def allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",")]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

"""Data storage and learning services"""
from app.services.graphrag.knowledge_graph_service import KnowledgeGraphService, knowledge_graph_service
from app.services.rl.rl_service import RLService, rl_service

# Nano-GraphRAG (unified Graph + Vector RAG) - primary service
try:
    from app.services.graphrag.nano_graphrag_service import NanoGraphRAGService, nano_graphrag_service
except ImportError:
    # nano-graphrag not installed
    NanoGraphRAGService = None
    nano_graphrag_service = None

__all__ = [
    # Legacy (now delegates to nano-graphrag when enabled)
    'KnowledgeGraphService', 'knowledge_graph_service',
    # RL service
    'RLService', 'rl_service',
    # Primary Graph+Vector RAG service
    'NanoGraphRAGService', 'nano_graphrag_service'
]

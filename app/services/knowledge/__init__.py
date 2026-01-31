"""Knowledge graph services - DEPRECATED: Use app.services.tools.knowledge_graph instead

This module re-exports from the new canonical location for backward compatibility.
New code should import directly from app.services.tools.knowledge_graph.
"""
# Re-export from new canonical location
from app.services.tools.knowledge_graph import KGQueryService, kg_query_service

__all__ = ['KGQueryService', 'kg_query_service']

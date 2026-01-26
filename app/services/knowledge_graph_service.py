import networkx as nx
import pickle
import os
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class KnowledgeGraphService:
    """Knowledge Graph service using NetworkX for RAG"""
    
    def __init__(self):
        self.graph = nx.DiGraph()
        self.graph_path = settings.knowledge_graph_path
        self.enabled = settings.enable_knowledge_graph
        
        if self.enabled:
            self._load_graph()
    
    def _load_graph(self):
        """Load knowledge graph from disk if it exists"""
        if os.path.exists(self.graph_path):
            try:
                # Security note: Using pickle for graph storage
                # Only load graphs from trusted sources
                # For production, consider using JSON or GraphML formats
                with open(self.graph_path, 'rb') as f:
                    self.graph = pickle.load(f)
                logger.info(f"Loaded knowledge graph with {self.graph.number_of_nodes()} nodes")
            except Exception as e:
                logger.error(f"Error loading knowledge graph: {e}")
                self.graph = nx.DiGraph()
        else:
            logger.info("No existing knowledge graph found, starting fresh")
    
    def _save_graph(self):
        """Save knowledge graph to disk"""
        if not self.enabled:
            return
        
        try:
            os.makedirs(os.path.dirname(self.graph_path), exist_ok=True)
            # Security note: Pickle is used for convenience but has security implications
            # In production, ensure only trusted processes can write to this file
            # Alternative: Use nx.write_graphml() for safer serialization
            with open(self.graph_path, 'wb') as f:
                pickle.dump(self.graph, f)
            logger.info(f"Saved knowledge graph with {self.graph.number_of_nodes()} nodes")
        except Exception as e:
            logger.error(f"Error saving knowledge graph: {e}")
    
    def add_entity(self, entity_id: str, entity_type: str, properties: Dict[str, Any]):
        """Add or update an entity in the knowledge graph"""
        if not self.enabled:
            return
        
        self.graph.add_node(
            entity_id,
            entity_type=entity_type,
            properties=properties,
            updated_at=datetime.utcnow().isoformat()
        )
        self._save_graph()
    
    def add_relationship(self, source_id: str, target_id: str, relationship_type: str, properties: Optional[Dict] = None):
        """Add a relationship between two entities"""
        if not self.enabled:
            return
        
        self.graph.add_edge(
            source_id,
            target_id,
            relationship_type=relationship_type,
            properties=properties or {},
            created_at=datetime.utcnow().isoformat()
        )
        self._save_graph()
    
    def add_jira_issue(self, issue_data: Dict[str, Any]):
        """Add a Jira issue to the knowledge graph"""
        if not self.enabled:
            return
        
        issue_key = issue_data.get("key")
        if not issue_key:
            return
        
        # Add issue node
        self.add_entity(
            entity_id=issue_key,
            entity_type="jira_issue",
            properties={
                "summary": issue_data.get("summary"),
                "status": issue_data.get("status"),
                "priority": issue_data.get("priority"),
                "assignee": issue_data.get("assignee"),
                "created": issue_data.get("created"),
                "updated": issue_data.get("updated"),
            }
        )
        
        # Add relationships to assignee
        if issue_data.get("assignee"):
            assignee = issue_data["assignee"]
            self.add_entity(
                entity_id=f"user:{assignee}",
                entity_type="user",
                properties={"name": assignee}
            )
            self.add_relationship(issue_key, f"user:{assignee}", "assigned_to")
    
    def add_confluence_page(self, page_data: Dict[str, Any]):
        """Add a Confluence page to the knowledge graph"""
        if not self.enabled:
            return
        
        page_id = page_data.get("id")
        if not page_id:
            return
        
        # Add page node
        self.add_entity(
            entity_id=f"confluence:{page_id}",
            entity_type="confluence_page",
            properties={
                "title": page_data.get("title"),
                "space": page_data.get("space"),
                "type": page_data.get("type"),
            }
        )
    
    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get an entity from the knowledge graph"""
        if not self.enabled or entity_id not in self.graph:
            return None
        
        node_data = self.graph.nodes[entity_id]
        return {
            "id": entity_id,
            "type": node_data.get("entity_type"),
            "properties": node_data.get("properties", {}),
            "updated_at": node_data.get("updated_at")
        }
    
    def get_related_entities(self, entity_id: str, relationship_type: Optional[str] = None, max_depth: int = 2) -> List[Dict[str, Any]]:
        """Get entities related to a given entity"""
        if not self.enabled or entity_id not in self.graph:
            return []
        
        related = []
        
        # Get direct neighbors
        for neighbor in self.graph.neighbors(entity_id):
            edge_data = self.graph.edges[entity_id, neighbor]
            if relationship_type is None or edge_data.get("relationship_type") == relationship_type:
                entity_data = self.get_entity(neighbor)
                if entity_data:
                    entity_data["relationship"] = edge_data.get("relationship_type")
                    related.append(entity_data)
        
        return related
    
    def search_entities(self, entity_type: Optional[str] = None, property_filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search for entities in the knowledge graph"""
        if not self.enabled:
            return []
        
        results = []
        for node_id, node_data in self.graph.nodes(data=True):
            # Filter by type if specified
            if entity_type and node_data.get("entity_type") != entity_type:
                continue
            
            # Filter by properties if specified
            if property_filter:
                properties = node_data.get("properties", {})
                match = all(
                    properties.get(key) == value
                    for key, value in property_filter.items()
                )
                if not match:
                    continue
            
            results.append({
                "id": node_id,
                "type": node_data.get("entity_type"),
                "properties": node_data.get("properties", {}),
                "updated_at": node_data.get("updated_at")
            })
        
        return results
    
    def get_graph_stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge graph"""
        if not self.enabled:
            return {"enabled": False}
        
        entity_types = {}
        for _, node_data in self.graph.nodes(data=True):
            entity_type = node_data.get("entity_type", "unknown")
            entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
        
        return {
            "enabled": True,
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "entity_types": entity_types,
            "graph_path": self.graph_path
        }
    
    def find_path(self, source_id: str, target_id: str) -> Optional[List[str]]:
        """Find shortest path between two entities"""
        if not self.enabled:
            return None
        
        try:
            path = nx.shortest_path(self.graph, source_id, target_id)
            return path
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
    
    def get_central_entities(self, limit: int = 10) -> List[Tuple[str, float]]:
        """Get most central entities using PageRank"""
        if not self.enabled or self.graph.number_of_nodes() == 0:
            return []
        
        try:
            pagerank = nx.pagerank(self.graph)
            sorted_entities = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)
            return sorted_entities[:limit]
        except Exception as e:
            logger.error(f"Error calculating PageRank: {e}")
            return []


knowledge_graph_service = KnowledgeGraphService()

"""
Knowledge Graph Query Service - KG query and context extraction.

This module was moved from knowledge/ to tools/knowledge_graph/ for better
semantic organization. All KG-related code is now in one place.
"""
from typing import Optional
import logging
import json

from app.services.graphrag.knowledge_graph_service import knowledge_graph_service

logger = logging.getLogger(__name__)


class KGQueryService:
    """Handles all Knowledge Graph queries and context extraction"""
    
    def __init__(self, llm=None):
        """Initialize KG query service with optional LLM for community queries"""
        self.llm = llm
        self.kg_service = knowledge_graph_service
    
    def search_knowledge_graph_direct(self, query: str) -> str:
        """
        Direct search in Knowledge Graph for entities and relationships
        Returns actual stored data, not just context
        """
        try:
            # Search for nodes matching the query
            matching_nodes = []
            query_lower = query.lower()
            query_terms = set(query_lower.split())
            
            # Use the knowledge_graph_service
            for node_id, node_data in self.kg_service.graph.nodes(data=True):
                node_text = f"{node_id} {node_data.get('type', '')} {node_data.get('summary', '')} {node_data.get('description', '')}"
                node_text_lower = node_text.lower()
                
                # Check if any query terms match
                if any(term in node_text_lower for term in query_terms if len(term) > 2):
                    matching_nodes.append({
                        "id": node_id,
                        "type": node_data.get("type"),
                        "summary": node_data.get("summary"),
                        "status": node_data.get("status"),
                        "updated": node_data.get("updated"),
                        "source": node_data.get("source", "knowledge_graph")
                    })
            
            if not matching_nodes:
                return "No matching entries found in Knowledge Graph."
            
            # Sort by updated date if available
            matching_nodes.sort(key=lambda x: x.get("updated", ""), reverse=True)
            
            return json.dumps(matching_nodes[:10], indent=2)
        except Exception as e:
            logger.error(f"Error searching Knowledge Graph: {e}")
            return f"Error searching Knowledge Graph: {str(e)}"
    
    def analyze_delivery_metrics(self, project_key: str) -> str:
        """Analyze delivery metrics for a project using knowledge graph"""
        try:
            # Import jira_service lazily to avoid circular imports
            from app.services.tools.jira.jira_service import jira_service
            
            issues = jira_service.get_project_issues(project_key.strip(), max_results=100)
            if not issues:
                return f"No issues found for project {project_key}"
            
            # Add all issues to knowledge graph
            for issue in issues:
                self.kg_service.add_jira_issue(issue)
            
            # Calculate basic metrics
            total = len(issues)
            status_counts = {}
            assignee_counts = {}
            
            for issue in issues:
                status = issue.get("status", "Unknown")
                status_counts[status] = status_counts.get(status, 0) + 1
                
                assignee = issue.get("assignee", "Unassigned")
                assignee_counts[assignee] = assignee_counts.get(assignee, 0) + 1
            
            # Get knowledge graph insights
            kg_stats = self.kg_service.get_graph_stats()
            central_entities = self.kg_service.get_central_entities(limit=5)
            
            metrics = {
                "project": project_key,
                "total_issues": total,
                "status_breakdown": status_counts,
                "assignee_breakdown": assignee_counts,
                "completion_rate": f"{(status_counts.get('Done', 0) / total * 100):.1f}%" if total > 0 else "0%",
                "knowledge_graph": {
                    "total_entities": kg_stats.get("total_nodes", 0),
                    "total_relationships": kg_stats.get("total_edges", 0),
                    "central_entities": [{"id": eid, "score": f"{score:.4f}"} for eid, score in central_entities]
                }
            }
            
            return json.dumps(metrics, indent=2)
        except Exception as e:
            logger.error(f"Error analyzing delivery metrics: {e}")
            return f"Error analyzing metrics: {str(e)}"
    
    def get_knowledge_graph_context(self, query: str) -> str:
        """Get relevant context from knowledge graph for RAG"""
        try:
            # Search for relevant entities
            jira_entities = self.kg_service.search_entities(entity_type="jira_issue")
            confluence_entities = self.kg_service.search_entities(entity_type="confluence_page")
            
            context = {
                "total_jira_issues": len(jira_entities),
                "total_confluence_pages": len(confluence_entities),
                "recent_issues": jira_entities[:5] if jira_entities else [],
                "graph_stats": self.kg_service.get_graph_stats()
            }
            
            return json.dumps(context, indent=2)
        except Exception as e:
            logger.error(f"Error getting knowledge graph context: {e}")
            return "{}"
    
    def get_kg_context_for_query(self, query: str, entity_type_filter: Optional[str] = None) -> str:
        """
        Get Knowledge Graph context to enrich query results.
        Uses community summaries for high-level insights.
        Returns insights about related entities, not the data itself.
        
        Args:
            query: User's query
            entity_type_filter: Optional filter to focus on specific entity types 
                              (e.g., 'confluence_page', 'jira_issue')
            
        Returns:
            Context string with KG insights or empty string
        """
        try:
            context_parts = []
            
            # Check if we have community summaries
            if hasattr(self.kg_service, 'community_summaries') and self.kg_service.community_summaries:
                # Find relevant communities for the query
                if self.llm:
                    relevant_communities = self.kg_service.get_community_for_query(query, self.llm)
                    
                    if relevant_communities:
                        context_parts.append("Relevant Knowledge Communities:")
                        for community_id, summary, score in relevant_communities[:3]:  # Top 3
                            context_parts.append(f"  - {summary} (relevance: {score:.2f})")
            
            # Search for related entities with optional type filtering
            kg_results = self.kg_service.search_by_text(query, entity_type=entity_type_filter)
            
            if kg_results and len(kg_results) > 0:
                # Extract keys/identifiers based on entity type
                if entity_type_filter == 'confluence_page':
                    # Show Confluence page titles
                    page_titles = [r.get('properties', {}).get('title', r.get('id')) for r in kg_results[:5]]
                    if page_titles:
                        context_parts.append(f"\nRelated Confluence pages: {', '.join(page_titles)}")
                else:
                    # Show Jira issue keys
                    related_keys = [r.get('properties', {}).get('key', r.get('id')) for r in kg_results[:5]]
                    if related_keys:
                        context_parts.append(f"\nRelated issues in graph: {', '.join(related_keys)}")
                
                # Get central entities that might be relevant (filtered by type if specified)
                central = self.kg_service.get_central_entities(limit=3)
                if central:
                    central_keys = [key for key, score in central]
                    context_parts.append(f"Central entities: {', '.join(central_keys)}")
            
            # For time-based queries, mention we have historical data
            query_lower = query.lower()
            if any(word in query_lower for word in ['latest', 'recent', 'updated', 'new']):
                stats = self.kg_service.get_graph_stats()
                total = stats.get('total_nodes', 0)
                entity_info = f" ({entity_type_filter} entities)" if entity_type_filter else " entities"
                context_parts.append(f"\nGraph contains {total}{entity_info} with historical relationships")
            
            return "\n".join(context_parts) if context_parts else ""
            
        except Exception as e:
            logger.error(f"Error getting KG context: {e}")
            return ""
    
    def get_entity(self, entity_id: str) -> Optional[dict]:
        """Get a specific entity and its relationships from the KG"""
        try:
            if entity_id in self.kg_service.graph:
                node_data = dict(self.kg_service.graph.nodes[entity_id])
                
                # Get relationships
                relationships = []
                for neighbor in self.kg_service.graph.neighbors(entity_id):
                    edge_data = self.kg_service.graph.edges[entity_id, neighbor]
                    relationships.append({
                        "target": neighbor,
                        "type": edge_data.get("type", "related_to"),
                        "properties": edge_data
                    })
                
                return {
                    "id": entity_id,
                    "properties": node_data,
                    "relationships": relationships
                }
            return None
        except Exception as e:
            logger.error(f"Error getting entity {entity_id}: {e}")
            return None


# Singleton instance
kg_query_service = KGQueryService()

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
    
    def add_entity(self, entity_id: str, entity_type: str, properties: Dict[str, Any], auto_save: bool = False):
        """Add or update an entity in the knowledge graph"""
        if not self.enabled:
            return
        
        self.graph.add_node(
            entity_id,
            entity_type=entity_type,
            properties=properties,
            updated_at=datetime.utcnow().isoformat()
        )
        if auto_save:
            self._save_graph()
    
    def add_relationship(self, source_id: str, target_id: str, relationship_type: str, properties: Optional[Dict] = None, auto_save: bool = False):
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
        if auto_save:
            self._save_graph()
    
    def add_jira_issue(self, issue_data: Dict[str, Any]):
        """Add a Jira issue to the knowledge graph with enhanced metadata extraction"""
        if not self.enabled:
            return
        
        issue_key = issue_data.get("key")
        if not issue_key:
            return
        
        # Extract project key (e.g., "ACTHUB" from "ACTHUB-9")
        project_key = issue_key.split('-')[0] if '-' in issue_key else None
        
        # Extract comprehensive metadata
        properties = {
            "summary": issue_data.get("summary"),
            "status": issue_data.get("status"),
            "priority": issue_data.get("priority"),
            "assignee": issue_data.get("assignee"),
            "reporter": issue_data.get("reporter"),
            "created": issue_data.get("created"),
            "updated": issue_data.get("updated"),
            "issue_type": issue_data.get("issue_type"),
            "description": issue_data.get("description", "")[:500],  # First 500 chars
            "labels": issue_data.get("labels", []),
            "components": issue_data.get("components", []),
            "fix_versions": issue_data.get("fix_versions", []),
            "parent": issue_data.get("parent"),  # For subtasks
            "epic_key": issue_data.get("epic_key"),  # Link to Epic
            "project_key": project_key,
            "has_subtasks": issue_data.get("has_subtasks", False),
        }
        
        # Add issue node
        self.add_entity(
            entity_id=issue_key,
            entity_type="jira_issue",
            properties=properties
        )
        
        # Add Project entity and relationship
        if project_key:
            project_id = f"project:{project_key}"
            self.add_entity(
                entity_id=project_id,
                entity_type="project",
                properties={"key": project_key, "name": project_key}
            )
            self.add_relationship(issue_key, project_id, "belongs_to_project")
        
        # Add relationships
        assignee = issue_data.get("assignee")
        if assignee and assignee != "Unassigned":
            self.add_entity(
                entity_id=f"user:{assignee}",
                entity_type="user",
                properties={"name": assignee}
            )
            self.add_relationship(issue_key, f"user:{assignee}", "assigned_to")
        
        # Add reporter relationship
        reporter = issue_data.get("reporter")
        if reporter:
            self.add_entity(
                entity_id=f"user:{reporter}",
                entity_type="user",
                properties={"name": reporter}
            )
            self.add_relationship(issue_key, f"user:{reporter}", "reported_by")
        
        # Link to parent issue if exists (for subtasks)
        parent_key = issue_data.get("parent")
        if parent_key:
            self.add_relationship(issue_key, parent_key, "child_of")
            # Also add reverse relationship
            self.add_relationship(parent_key, issue_key, "has_child")
        
        # Link to Epic if exists
        epic_key = issue_data.get("epic_key")
        if epic_key and epic_key != issue_key:  # Avoid self-reference
            # Ensure epic exists as an entity
            self.add_entity(
                entity_id=epic_key,
                entity_type="jira_issue",
                properties={"summary": f"Epic {epic_key}", "issue_type": "Epic"}
            )
            self.add_relationship(issue_key, epic_key, "belongs_to_epic")
            # Add reverse relationship
            self.add_relationship(epic_key, issue_key, "contains_issue")
        
        # Add subtasks if present
        subtasks = issue_data.get("subtasks", [])
        for subtask in subtasks:
            subtask_key = subtask.get("key")
            if subtask_key:
                self.add_relationship(issue_key, subtask_key, "has_child")
                self.add_relationship(subtask_key, issue_key, "child_of")
        
        # Link to components
        for component in issue_data.get("components", []):
            component_id = f"component:{component}"
            self.add_entity(
                entity_id=component_id,
                entity_type="component",
                properties={"name": component}
            )
            self.add_relationship(issue_key, component_id, "has_component")
        
        # Link to labels
        for label in issue_data.get("labels", []):
            label_id = f"label:{label}"
            self.add_entity(
                entity_id=label_id,
                entity_type="label",
                properties={"name": label}
            )
            self.add_relationship(issue_key, label_id, "has_label")
    
    def add_confluence_page(self, page_data: Dict[str, Any]):
        """Add a Confluence page to the knowledge graph with enhanced metadata"""
        if not self.enabled:
            return
        
        page_id = page_data.get("id")
        if not page_id:
            return
        
        # Extract comprehensive metadata
        properties = {
            "title": page_data.get("title"),
            "space": page_data.get("space"),
            "type": page_data.get("type"),
            "content_excerpt": page_data.get("content", "")[:500],  # First 500 chars
            "created": page_data.get("created"),
            "updated": page_data.get("updated"),
            "author": page_data.get("author"),
            "labels": page_data.get("labels", []),
        }
        
        # Add page node
        self.add_entity(
            entity_id=f"confluence:{page_id}",
            entity_type="confluence_page",
            properties=properties
        )
        
        # Link to author
        author = page_data.get("author")
        if author:
            self.add_entity(
                entity_id=f"user:{author}",
                entity_type="user",
                properties={"name": author}
            )
            self.add_relationship(f"confluence:{page_id}", f"user:{author}", "authored_by")
        
        # Link to space
        space = page_data.get("space")
        space_name = page_data.get("space_name", space)
        if space:
            space_id = f"space:{space}"
            self.add_entity(
                entity_id=space_id,
                entity_type="confluence_space",
                properties={"key": space, "name": space_name}
            )
            self.add_relationship(f"confluence:{page_id}", space_id, "in_space")
    
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
    
    def bulk_populate_jira_issues(self, issues: List[Dict[str, Any]]) -> int:
        """Bulk populate knowledge graph with Jira issues - NO AUTO-SAVE"""
        if not self.enabled:
            return 0
        
        count = 0
        
        # Temporarily disable auto-save during bulk load
        orig_enabled_state = self.enabled
        
        for issue in issues:
            try:
                self.add_jira_issue(issue)
                count += 1
            except Exception as e:
                logger.error(f"Error adding issue {issue.get('key', 'unknown')}: {e}")
        
        # Save once at the end of the batch
        self._save_graph()
        
        return count
    
    def bulk_populate_confluence_pages(self, pages: List[Dict[str, Any]]) -> int:
        """Bulk populate knowledge graph with Confluence pages"""
        if not self.enabled:
            return 0
        
        count = 0
        logger.info(f"📊 Starting bulk population of {len(pages)} Confluence pages...")
        
        for page in pages:
            try:
                self.add_confluence_page(page)
                count += 1
                if count % 10 == 0:
                    logger.info(f"  Processed {count}/{len(pages)} pages...")
            except Exception as e:
                logger.error(f"Error adding page {page.get('id', 'unknown')}: {e}")
        
        logger.info(f"✅ Bulk population complete: {count} pages added")
        return count
    
    def populate_from_services(self) -> Dict[str, int]:
        """Populate knowledge graph from ALL Jira projects and Confluence
        
        Returns:
            Dict with counts of issues, pages, and projects added
        """
        if not self.enabled:
            return {"jira_issues": 0, "confluence_pages": 0, "projects": 0}
        
        # Import here to avoid circular dependency
        from app.services.jira_service import jira_service
        from app.services.confluence_service import confluence_service
        
        results = {"jira_issues": 0, "confluence_pages": 0, "projects": 0}
        projects = set()
        
        # Populate ALL Jira issues across ALL projects (no limits)
        logger.info("🔍 Fetching ALL Jira issues from ALL projects...")
        print("🔍 Fetching ALL Jira issues from ALL projects...", flush=True)
        try:
            # First, get all projects
            if jira_service.client:
                all_projects = jira_service.client.projects()
                project_keys = [p.key for p in all_projects]
                logger.info(f"📦 Found {len(project_keys)} projects: {', '.join(project_keys)}")
                print(f"📦 Found {len(project_keys)} projects: {', '.join(project_keys)}", flush=True)
                
                # Iterate through each project
                for project_key in project_keys:
                    logger.info(f"\n📂 Loading all issues from project {project_key}...")
                    print(f"\n📂 Loading all issues from project {project_key}...", flush=True)
                    batch_size = 100
                    start_at = 0
                    project_issues = 0
                    
                    # Build JQL for this project only (required by Jira Cloud)
                    jql = f"project = {project_key} ORDER BY key ASC"
                    
                    while True:
                        logger.info(f"  Fetching issues {start_at} to {start_at + batch_size}...")
                        print(f"  Fetching batch starting at {start_at}...", end='', flush=True)
                        
                        # Use the search API
                        try:
                            issues = jira_service.client.search_issues(
                                jql, 
                                startAt=start_at, 
                                maxResults=batch_size,
                                fields='*all'
                            )
                            print(f" got {len(issues)} issues", flush=True)
                        except Exception as e:
                            logger.warning(f"search_issues failed for {project_key}: {e}")
                            print(f" ERROR: {e}", flush=True)
                            issues = []
                        
                        if not issues:
                            break
                        
                        # Convert to dict format
                        batch_issues = []
                        for issue in issues:
                            # Extract epic link
                            epic_key = None
                            if hasattr(issue.fields, 'customfield_10014'):
                                epic_key = issue.fields.customfield_10014
                            elif hasattr(issue.fields, 'parent') and issue.fields.parent:
                                if hasattr(issue.fields.parent.fields, 'issuetype'):
                                    if issue.fields.parent.fields.issuetype.name == 'Epic':
                                        epic_key = issue.fields.parent.key
                            
                            # Extract parent key
                            parent_key = None
                            if hasattr(issue.fields, 'parent') and issue.fields.parent:
                                parent_key = issue.fields.parent.key
                            
                            # Extract subtasks
                            subtasks = []
                            if hasattr(issue.fields, 'subtasks') and issue.fields.subtasks:
                                for subtask in issue.fields.subtasks:
                                    subtasks.append({
                                        "key": subtask.key,
                                        "summary": subtask.fields.summary,
                                        "status": subtask.fields.status.name
                                    })
                            
                            # Track project
                            proj_key = issue.key.split('-')[0]
                            projects.add(proj_key)
                            
                            batch_issues.append({
                                "key": issue.key,
                                "summary": issue.fields.summary,
                                "status": issue.fields.status.name,
                                "assignee": issue.fields.assignee.displayName if issue.fields.assignee else "Unassigned",
                                "reporter": issue.fields.reporter.displayName if issue.fields.reporter else "Unknown",
                                "created": str(issue.fields.created),
                                "updated": str(issue.fields.updated),
                                "priority": issue.fields.priority.name if issue.fields.priority else "None",
                                "issue_type": issue.fields.issuetype.name if issue.fields.issuetype else "Unknown",
                                "description": issue.fields.description if issue.fields.description else "",
                                "labels": issue.fields.labels if hasattr(issue.fields, 'labels') else [],
                                "components": [c.name for c in issue.fields.components] if hasattr(issue.fields, 'components') else [],
                                "parent": parent_key,
                                "epic_key": epic_key,
                                "subtasks": subtasks,
                                "has_subtasks": len(subtasks) > 0
                            })
                        
                        # Add batch to knowledge graph
                        if batch_issues:
                            count = self.bulk_populate_jira_issues(batch_issues)
                            project_issues += count
                            results["jira_issues"] += count
                            print(f"    ✓ Processed {count} issues (total: {project_issues})", flush=True)
                        
                        # Check if we got fewer results than batch size (last batch)
                        if len(issues) < batch_size:
                            break
                        
                        start_at += batch_size
                
                logger.info(f"  ✅ Loaded {project_issues} issues from {project_key}")
                print(f"  ✅ Loaded {project_issues} issues from {project_key}\n", flush=True)
            else:
                logger.error("Jira client not available")
            
            results["projects"] = len(projects)
            logger.info(f"✅ Loaded {results['jira_issues']} issues from {len(projects)} projects: {', '.join(sorted(projects))}")
            
        except Exception as e:
            logger.error(f"Error fetching Jira issues: {e}", exc_info=True)
        
        # Populate Confluence pages from ALL spaces
        logger.info("\n🔍 Fetching ALL Confluence pages from ALL spaces...")
        print("\n🔍 Fetching ALL Confluence pages from ALL spaces...", flush=True)
        try:
            confluence_pages = confluence_service.get_all_pages(limit=1000)
            if confluence_pages:
                logger.info(f"📄 Processing {len(confluence_pages)} Confluence pages...")
                print(f"📄 Processing {len(confluence_pages)} Confluence pages...", flush=True)
                results["confluence_pages"] = self.bulk_populate_confluence_pages(confluence_pages)
                logger.info(f"  ✅ Loaded {results['confluence_pages']} Confluence pages")
                print(f"  ✅ Loaded {results['confluence_pages']} Confluence pages\n", flush=True)
            else:
                logger.warning("No Confluence pages found")
                print("  ⚠️ No Confluence pages found", flush=True)
        except Exception as e:
            logger.error(f"Error fetching Confluence pages: {e}", exc_info=True)
            print(f"  ⚠️ Error loading Confluence: {e}", flush=True)
        
        # Final save of the complete graph
        print("\n💾 Saving knowledge graph to disk...", flush=True)
        self._save_graph()
        print("✅ Knowledge graph saved!\n", flush=True)
        
        logger.info(f"✅ Knowledge graph populated: {results}")
        return results
    
    def clear_graph(self):
        """Clear all data from the knowledge graph"""
        if not self.enabled:
            return
        
        logger.warning("🗑️ Clearing knowledge graph...")
        self.graph = nx.DiGraph()
        self._save_graph()
        logger.info("✅ Knowledge graph cleared")


knowledge_graph_service = KnowledgeGraphService()

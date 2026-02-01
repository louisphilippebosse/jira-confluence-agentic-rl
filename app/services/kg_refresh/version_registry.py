"""
KG Version Registry - Tracks nano-graphrag versions with metadata.

Simple SQLite-based versioning for graph experiments.
Tracks:
- Version name/description
- Creation date
- Graph stats (nodes, edges, communities)
- Training parameters
- Performance metrics
"""
import os
import json
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class KGVersion:
    """Represents a Knowledge Graph version with comprehensive metadata."""
    id: Optional[int] = None
    name: str = ""
    description: str = ""
    created_at: str = ""
    path: str = ""
    is_active: bool = False
    
    # Graph stats
    node_count: int = 0
    edge_count: int = 0
    community_count: int = 0
    
    # Vector/semantic search stats
    embedding_count: int = 0
    chunk_count: int = 0
    
    # Build info
    build_mode: str = "hybrid"  # 'hybrid' or 'deep'
    build_duration_sec: int = 0
    
    # Data sources
    jira_issues_count: int = 0
    confluence_pages_count: int = 0
    
    # Data lineage (for reproducibility)
    jql_filter: str = ""  # JQL used to fetch issues
    cql_filter: str = ""  # CQL used to fetch pages
    source_date_start: str = ""  # Earliest source data date
    source_date_end: str = ""    # Latest source data date
    
    # Quality metrics
    orphan_node_count: int = 0  # Nodes with no edges
    connected_components: int = 0  # Number of disconnected subgraphs
    avg_degree: float = 0.0
    
    # Performance metrics
    avg_query_time_ms: Optional[float] = None
    p95_query_time_ms: Optional[float] = None
    query_count: int = 0  # Number of queries against this version
    
    # Storage
    size_mb: float = 0.0
    
    # Diff from previous version
    nodes_added: int = 0
    nodes_removed: int = 0
    edges_changed: int = 0
    
    # Training params (for experiments)
    params: Dict[str, Any] = field(default_factory=dict)
    
    # Tags for organization
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if isinstance(d.get('params'), str):
            d['params'] = json.loads(d['params'])
        if isinstance(d.get('tags'), str):
            d['tags'] = json.loads(d['tags'])
        return d
    
    @property
    def quality_score(self) -> float:
        """Calculate overall quality score (0-100)."""
        if self.node_count == 0:
            return 0.0
        
        # Penalize orphan nodes
        orphan_ratio = self.orphan_node_count / max(self.node_count, 1)
        orphan_score = max(0, 100 - (orphan_ratio * 200))  # -2 points per % orphan
        
        # Reward higher connectivity
        connectivity_score = min(100, self.avg_degree * 20)  # 5 avg degree = 100
        
        # Penalize fragmentation
        if self.connected_components > 1:
            frag_score = max(0, 100 - (self.connected_components - 1) * 10)
        else:
            frag_score = 100
        
        return (orphan_score + connectivity_score + frag_score) / 3


class KGVersionRegistry:
    """
    Registry for tracking nano-graphrag versions.
    
    Uses SQLite for persistence, allowing:
    - Create versions from backups
    - Switch active version
    - Compare version stats
    - Track training experiments
    """
    
    def __init__(
        self,
        db_path: str = "./data/kg_versions.db",
        versions_dir: str = "./data/kg_versions"
    ):
        self.db_path = Path(db_path)
        self.versions_dir = Path(versions_dir)
        
        # Ensure directories exist
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        
        self._init_db()
        logger.info(f"KGVersionRegistry initialized: {self.db_path}")
    
    def _init_db(self):
        """Initialize SQLite database with comprehensive schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kg_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    path TEXT NOT NULL,
                    is_active INTEGER DEFAULT 0,
                    
                    -- Graph stats
                    node_count INTEGER DEFAULT 0,
                    edge_count INTEGER DEFAULT 0,
                    community_count INTEGER DEFAULT 0,
                    
                    -- Vector stats
                    embedding_count INTEGER DEFAULT 0,
                    chunk_count INTEGER DEFAULT 0,
                    
                    -- Build info
                    build_mode TEXT DEFAULT 'hybrid',
                    build_duration_sec INTEGER DEFAULT 0,
                    
                    -- Data sources
                    jira_issues_count INTEGER DEFAULT 0,
                    confluence_pages_count INTEGER DEFAULT 0,
                    
                    -- Data lineage
                    jql_filter TEXT DEFAULT '',
                    cql_filter TEXT DEFAULT '',
                    source_date_start TEXT DEFAULT '',
                    source_date_end TEXT DEFAULT '',
                    
                    -- Quality metrics
                    orphan_node_count INTEGER DEFAULT 0,
                    connected_components INTEGER DEFAULT 0,
                    avg_degree REAL DEFAULT 0.0,
                    
                    -- Performance
                    avg_query_time_ms REAL,
                    p95_query_time_ms REAL,
                    query_count INTEGER DEFAULT 0,
                    
                    -- Storage
                    size_mb REAL DEFAULT 0.0,
                    
                    -- Diff
                    nodes_added INTEGER DEFAULT 0,
                    nodes_removed INTEGER DEFAULT 0,
                    edges_changed INTEGER DEFAULT 0,
                    
                    -- Params and tags
                    params TEXT DEFAULT '{}',
                    tags TEXT DEFAULT '[]'
                )
            """)
            
            # Migrate existing databases - add new columns if missing
            new_columns = [
                ("embedding_count", "INTEGER DEFAULT 0"),
                ("chunk_count", "INTEGER DEFAULT 0"),
                ("build_mode", "TEXT DEFAULT 'hybrid'"),
                ("build_duration_sec", "INTEGER DEFAULT 0"),
                ("jql_filter", "TEXT DEFAULT ''"),
                ("cql_filter", "TEXT DEFAULT ''"),
                ("source_date_start", "TEXT DEFAULT ''"),
                ("source_date_end", "TEXT DEFAULT ''"),
                ("orphan_node_count", "INTEGER DEFAULT 0"),
                ("connected_components", "INTEGER DEFAULT 0"),
                ("avg_degree", "REAL DEFAULT 0.0"),
                ("p95_query_time_ms", "REAL"),
                ("query_count", "INTEGER DEFAULT 0"),
                ("size_mb", "REAL DEFAULT 0.0"),
                ("nodes_added", "INTEGER DEFAULT 0"),
                ("nodes_removed", "INTEGER DEFAULT 0"),
                ("edges_changed", "INTEGER DEFAULT 0"),
                ("tags", "TEXT DEFAULT '[]'"),
            ]
            
            for col_name, col_type in new_columns:
                try:
                    conn.execute(f"ALTER TABLE kg_versions ADD COLUMN {col_name} {col_type}")
                except sqlite3.OperationalError:
                    pass  # Column already exists
            
            conn.commit()
    
    def _row_to_version(self, row: tuple) -> KGVersion:
        """Convert database row to KGVersion with all fields."""
        # Use dict-based approach for flexibility with schema changes
        # Column order in new schema (27 columns total)
        try:
            return KGVersion(
                id=row[0],
                name=row[1],
                description=row[2] or "",
                created_at=row[3],
                path=row[4],
                is_active=bool(row[5]),
                node_count=row[6] or 0,
                edge_count=row[7] or 0,
                community_count=row[8] or 0,
                embedding_count=row[9] if len(row) > 9 else 0,
                chunk_count=row[10] if len(row) > 10 else 0,
                build_mode=row[11] if len(row) > 11 else "hybrid",
                build_duration_sec=row[12] if len(row) > 12 else 0,
                jira_issues_count=row[13] if len(row) > 13 else 0,
                confluence_pages_count=row[14] if len(row) > 14 else 0,
                jql_filter=row[15] if len(row) > 15 else "",
                cql_filter=row[16] if len(row) > 16 else "",
                source_date_start=row[17] if len(row) > 17 else "",
                source_date_end=row[18] if len(row) > 18 else "",
                orphan_node_count=row[19] if len(row) > 19 else 0,
                connected_components=row[20] if len(row) > 20 else 0,
                avg_degree=row[21] if len(row) > 21 else 0.0,
                avg_query_time_ms=row[22] if len(row) > 22 else None,
                p95_query_time_ms=row[23] if len(row) > 23 else None,
                query_count=row[24] if len(row) > 24 else 0,
                size_mb=row[25] if len(row) > 25 else 0.0,
                nodes_added=row[26] if len(row) > 26 else 0,
                nodes_removed=row[27] if len(row) > 27 else 0,
                edges_changed=row[28] if len(row) > 28 else 0,
                params=json.loads(row[29]) if len(row) > 29 and row[29] else {},
                tags=json.loads(row[30]) if len(row) > 30 and row[30] else [],
            )
        except (IndexError, TypeError) as e:
            # Fallback for old schema - just use basic fields
            logger.warning(f"Row parsing fallback: {e}")
            return KGVersion(
                id=row[0],
                name=row[1],
                description=row[2] or "",
                created_at=row[3],
                path=row[4],
                is_active=bool(row[5]),
                node_count=row[6] if len(row) > 6 else 0,
                edge_count=row[7] if len(row) > 7 else 0,
            )
    
    # =========================================================================
    # CRUD Operations
    # =========================================================================
    
    def create_version(
        self,
        name: str,
        source_path: str,
        description: str = "",
        params: Optional[Dict] = None,
        jira_count: int = 0,
        confluence_count: int = 0,
        make_active: bool = False,
        build_mode: str = "hybrid",
        build_duration_sec: int = 0,
        jql_filter: str = "",
        cql_filter: str = "",
        tags: Optional[List[str]] = None
    ) -> KGVersion:
        """
        Create a new version from a source directory with comprehensive metadata.
        
        Args:
            name: Human-readable version name (e.g., "v1-baseline", "v2-more-entities")
            source_path: Path to the graph data to version
            description: Optional description of this version
            params: Training parameters used
            jira_count: Number of Jira issues ingested
            confluence_count: Number of Confluence pages ingested
            make_active: Set this as the active version
            build_mode: 'hybrid' (fast) or 'deep' (LLM entity extraction)
            build_duration_sec: How long the build took
            jql_filter: JQL query used to fetch issues
            cql_filter: CQL query used to fetch pages
            tags: Optional tags for organization
        
        Returns:
            Created KGVersion
        """
        import shutil
        
        source = Path(source_path)
        if not source.exists():
            raise ValueError(f"Source path does not exist: {source_path}")
        
        # Create version directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        version_dir = self.versions_dir / f"{name}_{timestamp}"
        shutil.copytree(source, version_dir)
        
        # Also copy the NetworkX graph file if it exists
        nx_graph_path = Path("./data/knowledge_graph.gpickle")
        if nx_graph_path.exists():
            shutil.copy(nx_graph_path, version_dir / "knowledge_graph.gpickle")
            logger.info(f"📦 Copied NetworkX graph to version: {nx_graph_path}")
        else:
            logger.warning(f"⚠️ NetworkX graph not found at {nx_graph_path}, version will not include it")
        
        # Get comprehensive graph stats
        stats = self._get_graph_stats(version_dir)
        
        # Calculate diff from previous active version
        nodes_added, nodes_removed, edges_changed = 0, 0, 0
        prev_version = self.get_active_version()
        if prev_version:
            nodes_added = max(0, stats.get('nodes', 0) - prev_version.node_count)
            nodes_removed = max(0, prev_version.node_count - stats.get('nodes', 0))
            edges_changed = abs(stats.get('edges', 0) - prev_version.edge_count)
        
        # Insert into database with all fields
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO kg_versions 
                (name, description, created_at, path, is_active, 
                 node_count, edge_count, community_count, embedding_count, chunk_count,
                 build_mode, build_duration_sec, jira_issues_count, confluence_pages_count,
                 jql_filter, cql_filter, orphan_node_count, connected_components, avg_degree,
                 size_mb, nodes_added, nodes_removed, edges_changed, params, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name,
                description,
                datetime.now().isoformat(),
                str(version_dir),
                1 if make_active else 0,
                stats.get('nodes', 0),
                stats.get('edges', 0),
                stats.get('communities', 0),
                stats.get('embeddings', 0),
                stats.get('chunks', 0),
                build_mode,
                build_duration_sec,
                jira_count,
                confluence_count,
                jql_filter,
                cql_filter,
                stats.get('orphan_nodes', 0),
                stats.get('connected_components', 0),
                stats.get('avg_degree', 0.0),
                stats.get('size_mb', 0.0),
                nodes_added,
                nodes_removed,
                edges_changed,
                json.dumps(params or {}),
                json.dumps(tags or [])
            ))
            version_id = cursor.lastrowid
            conn.commit()
        
        if make_active:
            self.set_active(version_id)
        
        version = self.get_version(version_id)
        logger.info(f"Created KG version: {name} ({stats.get('nodes', 0)} nodes, {stats.get('embeddings', 0)} embeddings, {stats.get('size_mb', 0)} MB)")
        return version
    
    def _get_graph_stats(self, version_path: Path) -> Dict[str, Any]:
        """Get comprehensive stats from a graph version including quality metrics."""
        stats = {
            'nodes': 0, 'edges': 0, 'communities': 0, 
            'embeddings': 0, 'chunks': 0,
            'orphan_nodes': 0, 'connected_components': 0, 'avg_degree': 0.0,
            'size_mb': 0.0
        }
        
        # Calculate total size
        total_size = 0
        for f in version_path.glob('**/*'):
            if f.is_file():
                total_size += f.stat().st_size
        stats['size_mb'] = round(total_size / (1024 * 1024), 2)
        
        graph_file = version_path / "graph_chunk_entity_relation.graphml"
        if graph_file.exists():
            try:
                import networkx as nx
                graph = nx.read_graphml(str(graph_file))
                stats['nodes'] = graph.number_of_nodes()
                stats['edges'] = graph.number_of_edges()
                
                # Quality metrics
                if stats['nodes'] > 0:
                    # Orphan nodes (no edges)
                    stats['orphan_nodes'] = sum(1 for n in graph.nodes() if graph.degree(n) == 0)
                    
                    # Average degree
                    stats['avg_degree'] = round(sum(d for _, d in graph.degree()) / stats['nodes'], 2)
                    
                    # Connected components (treat as undirected for this)
                    undirected = graph.to_undirected()
                    stats['connected_components'] = nx.number_connected_components(undirected)
                    
            except Exception as e:
                logger.warning(f"Could not read graph stats: {e}")
        
        # Also check NetworkX gpickle if present
        gpickle_file = version_path / "knowledge_graph.gpickle"
        if gpickle_file.exists() and stats['nodes'] == 0:
            try:
                import pickle
                with open(gpickle_file, 'rb') as f:
                    graph = pickle.load(f)
                stats['nodes'] = graph.number_of_nodes()
                stats['edges'] = graph.number_of_edges()
                
                if stats['nodes'] > 0:
                    stats['orphan_nodes'] = sum(1 for n in graph.nodes() if graph.degree(n) == 0)
                    stats['avg_degree'] = round(sum(d for _, d in graph.degree()) / stats['nodes'], 2)
                    undirected = graph.to_undirected()
                    stats['connected_components'] = nx.number_connected_components(undirected)
            except Exception as e:
                logger.warning(f"Could not read gpickle stats: {e}")
        
        communities_file = version_path / "kv_store_community_reports.json"
        if communities_file.exists():
            try:
                with open(communities_file, 'r') as f:
                    data = json.load(f)
                stats['communities'] = len(data) if isinstance(data, (list, dict)) else 0
            except Exception:
                pass
        
        # Check vector embeddings
        vdb_file = version_path / "vdb_entities.json"
        if vdb_file.exists():
            try:
                with open(vdb_file, 'r') as f:
                    data = json.load(f)
                stats['embeddings'] = len(data) if isinstance(data, (list, dict)) else 0
            except Exception:
                pass
        
        # Check text chunks
        chunks_file = version_path / "kv_store_text_chunks.json"
        if chunks_file.exists():
            try:
                with open(chunks_file, 'r') as f:
                    data = json.load(f)
                stats['chunks'] = len(data) if isinstance(data, (list, dict)) else 0
            except Exception:
                pass
        
        return stats
    
    def get_version(self, version_id: int) -> Optional[KGVersion]:
        """Get a specific version by ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM kg_versions WHERE id = ?", (version_id,)
            )
            row = cursor.fetchone()
            return self._row_to_version(row) if row else None
    
    def list_versions(self, limit: int = 50) -> List[KGVersion]:
        """List all versions, most recent first."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM kg_versions ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            return [self._row_to_version(row) for row in cursor.fetchall()]
    
    def get_active_version(self) -> Optional[KGVersion]:
        """Get the currently active version."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM kg_versions WHERE is_active = 1"
            )
            row = cursor.fetchone()
            return self._row_to_version(row) if row else None
    
    def set_active(self, version_id: int) -> bool:
        """
        Set a version as active.
        
        This will:
        1. Deactivate current active version
        2. Activate the new version
        3. Update the nano-graphrag service to use this version
        """
        with sqlite3.connect(self.db_path) as conn:
            # Deactivate all
            conn.execute("UPDATE kg_versions SET is_active = 0")
            # Activate the specified version
            conn.execute(
                "UPDATE kg_versions SET is_active = 1 WHERE id = ?",
                (version_id,)
            )
            conn.commit()
        
        # Get the version to find its path
        version = self.get_version(version_id)
        if version:
            self._switch_active_graph(version.path)
            logger.info(f"Activated KG version: {version.name}")
            return True
        return False
    
    def _switch_active_graph(self, version_path: str):
        """Switch the active graph by updating both nano-graphrag and NetworkX services."""
        import shutil
        
        nano_working_dir = Path("./data/nano_graphrag")
        version_path = Path(version_path)
        
        # Backup current nano-graphrag if exists
        if nano_working_dir.exists():
            backup_dir = nano_working_dir.with_suffix('.previous')
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            nano_working_dir.rename(backup_dir)
        
        # Copy version to nano-graphrag working dir
        shutil.copytree(version_path, nano_working_dir)
        
        # Also switch the NetworkX knowledge_graph.gpickle
        # Look for gpickle in the version directory or copy from nano-graphrag
        kg_dest = Path("./data/knowledge_graph.gpickle")
        
        # Check if version has a gpickle file
        version_gpickle = version_path / "knowledge_graph.gpickle"
        if version_gpickle.exists():
            shutil.copy(version_gpickle, kg_dest)
            logger.info("Switched NetworkX graph from version")
        
        # Notify nano-graphrag service to reload
        try:
            from app.services.graphrag.nano_graphrag_service import nano_graphrag_service
            nano_graphrag_service._rag = None
            nano_graphrag_service._initialized = False
            logger.info("Notified nano-graphrag service to reload")
        except Exception as e:
            logger.warning(f"Could not reload nano-graphrag: {e}")
        
        # Reload the NetworkX graph into knowledge_graph_service
        try:
            from app.services.graphrag.knowledge_graph_service import knowledge_graph_service
            knowledge_graph_service.reload_graph()
            logger.info("Reloaded NetworkX knowledge graph")
        except Exception as e:
            logger.warning(f"Could not notify nano-graphrag service: {e}")
        
        # Notify NetworkX knowledge_graph_service to reload
        try:
            from app.services.graphrag.knowledge_graph_service import knowledge_graph_service
            knowledge_graph_service._load_graph()
            logger.info("Notified knowledge_graph_service to reload")
        except Exception as e:
            logger.warning(f"Could not notify knowledge_graph_service: {e}")
    
    def delete_version(self, version_id: int) -> bool:
        """Delete a version (cannot delete active version)."""
        import shutil
        
        version = self.get_version(version_id)
        if not version:
            return False
        
        if version.is_active:
            raise ValueError("Cannot delete the active version")
        
        # Delete files
        if Path(version.path).exists():
            shutil.rmtree(version.path)
        
        # Delete from database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM kg_versions WHERE id = ?", (version_id,))
            conn.commit()
        
        logger.info(f"Deleted KG version: {version.name}")
        return True
    
    def update_metrics(
        self,
        version_id: int,
        avg_query_time_ms: Optional[float] = None,
        p95_query_time_ms: Optional[float] = None,
        increment_query_count: bool = False
    ):
        """Update performance metrics for a version."""
        with sqlite3.connect(self.db_path) as conn:
            if avg_query_time_ms is not None:
                conn.execute(
                    "UPDATE kg_versions SET avg_query_time_ms = ? WHERE id = ?",
                    (avg_query_time_ms, version_id)
                )
            if p95_query_time_ms is not None:
                conn.execute(
                    "UPDATE kg_versions SET p95_query_time_ms = ? WHERE id = ?",
                    (p95_query_time_ms, version_id)
                )
            if increment_query_count:
                conn.execute(
                    "UPDATE kg_versions SET query_count = query_count + 1 WHERE id = ?",
                    (version_id,)
                )
            conn.commit()
    
    def record_query_time(self, version_id: int, query_time_ms: float):
        """
        Record a query time and update rolling averages.
        Call this from your query endpoints to track performance.
        """
        version = self.get_version(version_id)
        if not version:
            return
        
        # Update rolling average
        if version.avg_query_time_ms is None:
            new_avg = query_time_ms
        else:
            # Exponential moving average (more weight to recent)
            alpha = 0.1  # Smoothing factor
            new_avg = alpha * query_time_ms + (1 - alpha) * version.avg_query_time_ms
        
        self.update_metrics(
            version_id,
            avg_query_time_ms=new_avg,
            increment_query_count=True
        )
    
    def compare_versions(self, version_id_a: int, version_id_b: int) -> Dict[str, Any]:
        """
        Compare two versions and return differences.
        Useful for A/B testing and understanding changes.
        """
        v_a = self.get_version(version_id_a)
        v_b = self.get_version(version_id_b)
        
        if not v_a or not v_b:
            return {"error": "Version not found"}
        
        return {
            "version_a": v_a.name,
            "version_b": v_b.name,
            "node_diff": v_b.node_count - v_a.node_count,
            "edge_diff": v_b.edge_count - v_a.edge_count,
            "embedding_diff": v_b.embedding_count - v_a.embedding_count,
            "quality_score_diff": v_b.quality_score - v_a.quality_score,
            "size_diff_mb": round(v_b.size_mb - v_a.size_mb, 2),
            "query_time_diff_ms": (
                (v_b.avg_query_time_ms or 0) - (v_a.avg_query_time_ms or 0)
                if v_b.avg_query_time_ms and v_a.avg_query_time_ms else None
            ),
            "better_version": (
                v_b.name if v_b.quality_score > v_a.quality_score else v_a.name
            )
        }
    
    def get_best_version(self) -> Optional[KGVersion]:
        """Get the version with the highest quality score."""
        versions = self.list_versions()
        if not versions:
            return None
        return max(versions, key=lambda v: v.quality_score)
    
    def add_tags(self, version_id: int, tags: List[str]):
        """Add tags to a version for organization."""
        version = self.get_version(version_id)
        if not version:
            return
        
        existing_tags = version.tags or []
        new_tags = list(set(existing_tags + tags))
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE kg_versions SET tags = ? WHERE id = ?",
                (json.dumps(new_tags), version_id)
            )
            conn.commit()
    
    def find_by_tag(self, tag: str) -> List[KGVersion]:
        """Find versions by tag."""
        versions = self.list_versions(limit=100)
        return [v for v in versions if tag in (v.tags or [])]
    
    # =========================================================================
    # Import from existing backups
    # =========================================================================
    
    def import_from_backup(
        self,
        backup_path: str,
        name: str,
        description: str = ""
    ) -> KGVersion:
        """
        Import an existing backup as a version.
        
        Useful for versioning existing backups from the refresh manager.
        """
        return self.create_version(
            name=name,
            source_path=backup_path,
            description=description or f"Imported from {backup_path}"
        )
    
    def import_all_backups(self) -> int:
        """Import all existing backups as versions."""
        backup_dir = Path("./data/backups")
        if not backup_dir.exists():
            return 0
        
        imported = 0
        for backup in sorted(backup_dir.iterdir()):
            if backup.is_dir() and backup.name.startswith("nano_graphrag_"):
                try:
                    # Check if already imported
                    existing = [v for v in self.list_versions() if backup.name in v.path]
                    if not existing:
                        self.import_from_backup(
                            backup_path=str(backup),
                            name=backup.name.replace("nano_graphrag_", ""),
                            description="Auto-imported from backup"
                        )
                        imported += 1
                except Exception as e:
                    logger.warning(f"Could not import {backup}: {e}")
        
        return imported


# Global instance
_version_registry: Optional[KGVersionRegistry] = None


def get_version_registry() -> KGVersionRegistry:
    """Get or create the global version registry."""
    global _version_registry
    if _version_registry is None:
        _version_registry = KGVersionRegistry()
    return _version_registry

"""
Knowledge Graph Refresh Manager - Safe, non-blocking KG refresh.

Responsibilities:
- Backup current model before refresh
- Build new model in temporary directory
- Hot-swap: use old model while new trains
- Atomic switchover when complete
- Rollback on failure

Following Single Responsibility Principle.
"""
import os
import shutil
import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from enum import Enum
from threading import Lock, Thread
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class RefreshStatus(Enum):
    """Status of the KG refresh operation."""
    IDLE = "idle"
    BACKING_UP = "backing_up"
    FETCHING_DATA = "fetching_data"
    BUILDING = "building"
    VALIDATING = "validating"
    SWITCHING = "switching"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class RefreshProgress:
    """Progress information for KG refresh."""
    status: RefreshStatus = RefreshStatus.IDLE
    progress: int = 0  # 0-100
    stage: str = "Idle"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    backup_path: Optional[str] = None
    stats: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "progress": self.progress,
            "stage": self.stage,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "backup_path": self.backup_path,
            "stats": self.stats
        }


class KGRefreshManager:
    """
    Manages safe Knowledge Graph refresh operations.
    
    Key features:
    - Non-blocking: Old model serves queries while new one builds
    - Safe: Backups before any modification
    - Atomic: Switchover only when new model is validated
    - Recoverable: Rollback on failure
    """
    
    def __init__(
        self,
        working_dir: str = "./data/nano_graphrag",
        backup_dir: str = "./data/backups",
        temp_build_dir: str = "./data/nano_graphrag_temp",
        status_file: str = "./data/kg_refresh_status.json"
    ):
        self.working_dir = Path(working_dir)
        self.backup_dir = Path(backup_dir)
        self.temp_build_dir = Path(temp_build_dir)
        self.status_file = Path(status_file)
        
        self._progress = RefreshProgress()
        self._lock = Lock()
        self._refresh_thread: Optional[Thread] = None
        self._cancel_requested = False
        
        # Callbacks for hot-swap notification
        self._on_model_ready: Optional[Callable] = None
        
        # Ensure directories exist
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"KGRefreshManager initialized: {self.working_dir}")
    
    @property
    def is_refreshing(self) -> bool:
        """Check if a refresh is currently in progress."""
        return self._progress.status not in [
            RefreshStatus.IDLE, 
            RefreshStatus.COMPLETED, 
            RefreshStatus.FAILED,
            RefreshStatus.ROLLED_BACK
        ]
    
    @property
    def progress(self) -> RefreshProgress:
        """Get current refresh progress."""
        return self._progress
    
    def cancel_refresh(self) -> bool:
        """Request cancellation of ongoing refresh."""
        if not self.is_refreshing:
            logger.warning("No refresh in progress to cancel")
            return False
        
        with self._lock:
            self._cancel_requested = True
        
        # Immediately update status to cancelled so it doesn't show as "building" on page refresh
        self._update_progress(
            RefreshStatus.FAILED, self._progress.progress,
            "Cancelling...", error="Refresh cancelled by user"
        )
        
        logger.info("🛑 Cancellation requested for KG refresh")
        return True
    
    def _check_cancellation(self):
        """Check if cancellation was requested and raise exception."""
        if self._cancel_requested:
            raise Exception("Refresh cancelled by user")
    
    def _update_progress(
        self,
        status: RefreshStatus,
        progress: int,
        stage: str,
        error: Optional[str] = None,
        **kwargs
    ):
        """Update and persist progress."""
        with self._lock:
            self._progress.status = status
            self._progress.progress = progress
            self._progress.stage = stage
            self._progress.error = error
            
            for key, value in kwargs.items():
                setattr(self._progress, key, value)
            
            # Persist to file
            self._save_status()
            
            logger.info(f"🔄 KG Refresh: {stage} ({progress}%)")
    
    def _save_status(self):
        """Save status to file for external monitoring."""
        self.status_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.status_file, 'w') as f:
            json.dump(self._progress.to_dict(), f, indent=2)
    
    def load_status(self) -> RefreshProgress:
        """Load status from file."""
        if self.status_file.exists():
            try:
                with open(self.status_file, 'r') as f:
                    data = json.load(f)
                self._progress.status = RefreshStatus(data.get('status', 'idle'))
                self._progress.progress = data.get('progress', 0)
                self._progress.stage = data.get('stage', 'Unknown')
                self._progress.error = data.get('error')
                self._progress.backup_path = data.get('backup_path')
            except Exception as e:
                logger.warning(f"Could not load status: {e}")
        return self._progress
    
    # =========================================================================
    # Backup Operations
    # =========================================================================
    
    def create_backup(self, reason: str = "refresh") -> Optional[str]:
        """
        Create a timestamped backup of the current KG data.
        
        Returns:
            Backup directory path, or None if no data to backup
        """
        if not self.working_dir.exists():
            logger.info("No existing KG to backup")
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"nano_graphrag_{reason}_{timestamp}"
        backup_path = self.backup_dir / backup_name
        
        try:
            shutil.copytree(self.working_dir, backup_path)
            logger.info(f"💾 Backup created: {backup_path}")
            return str(backup_path)
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            raise
    
    def list_backups(self) -> list:
        """List all available backups."""
        if not self.backup_dir.exists():
            return []
        
        backups = []
        for item in self.backup_dir.iterdir():
            if item.is_dir() and item.name.startswith("nano_graphrag_"):
                stat = item.stat()
                backups.append({
                    "name": item.name,
                    "path": str(item),
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "size_mb": sum(f.stat().st_size for f in item.rglob('*') if f.is_file()) / (1024 * 1024)
                })
        
        return sorted(backups, key=lambda x: x['created'], reverse=True)
    
    def restore_backup(self, backup_path: str) -> bool:
        """
        Restore KG from a backup.
        
        Args:
            backup_path: Path to backup directory
            
        Returns:
            True if successful
        """
        backup_path = Path(backup_path)
        
        if not backup_path.exists():
            raise ValueError(f"Backup not found: {backup_path}")
        
        # Create safety backup of current state
        if self.working_dir.exists():
            self.create_backup(reason="before_restore")
        
        # Remove current and restore
        if self.working_dir.exists():
            shutil.rmtree(self.working_dir)
        
        shutil.copytree(backup_path, self.working_dir)
        logger.info(f"✅ Restored from backup: {backup_path}")
        return True
    
    def cleanup_old_backups(self, keep_count: int = 5):
        """Remove old backups, keeping only the most recent ones."""
        backups = self.list_backups()
        
        if len(backups) <= keep_count:
            return
        
        for backup in backups[keep_count:]:
            try:
                shutil.rmtree(backup['path'])
                logger.info(f"🗑️ Removed old backup: {backup['name']}")
            except Exception as e:
                logger.warning(f"Could not remove backup {backup['name']}: {e}")
    
    # =========================================================================
    # Refresh Operations
    # =========================================================================
    
    def start_refresh(
        self,
        clear_existing: bool = False,
        quick_mode: bool = False,
        on_complete: Optional[Callable] = None
    ) -> bool:
        """
        Start a non-blocking KG refresh.
        
        The refresh runs in a background thread, allowing the current model
        to continue serving queries until the new one is ready.
        
        Args:
            clear_existing: If True, don't migrate existing data
            quick_mode: If True, skip LLM-based entity extraction (much faster)
            on_complete: Callback when refresh completes
            
        Returns:
            True if refresh started, False if already in progress
        """
        if self.is_refreshing:
            logger.warning("Refresh already in progress")
            return False
        
        # Reset cancel flag
        with self._lock:
            self._cancel_requested = False
        
        self._on_model_ready = on_complete
        self._quick_mode = quick_mode
        
        # Start in background thread
        self._refresh_thread = Thread(
            target=self._run_refresh,
            args=(clear_existing, quick_mode),
            daemon=True
        )
        self._refresh_thread.start()
        
        return True
    
    def _run_refresh(self, clear_existing: bool, quick_mode: bool = False):
        """
        Execute the refresh process.
        
        Steps:
        1. Backup current model
        2. Build new model in temp directory
        3. Validate new model
        4. Atomic switchover
        5. Cleanup
        
        Args:
            clear_existing: Clear existing data before refresh
            quick_mode: Skip LLM-based entity extraction (much faster)
        """
        mode_str = "QUICK" if quick_mode else "FULL"
        try:
            self._update_progress(
                RefreshStatus.BACKING_UP, 5, f"Creating backup... ({mode_str} mode)",
                started_at=datetime.now()
            )
            
            # Check cancellation
            self._check_cancellation()
            
            # Step 1: Backup
            backup_path = self.create_backup(reason="before_refresh")
            self._progress.backup_path = backup_path
            
            self._update_progress(
                RefreshStatus.FETCHING_DATA, 10, "Fetching Jira/Confluence data..."
            )
            
            # Check cancellation
            self._check_cancellation()
            
            # Step 2: Fetch data
            from app.maintenance.kg_manager import fetch_jira_data, fetch_confluence_data
            jira_issues = fetch_jira_data()
            confluence_pages = fetch_confluence_data()
            
            if not jira_issues and not confluence_pages:
                self._update_progress(
                    RefreshStatus.FAILED, 10, "No data to populate",
                    error="No Jira issues or Confluence pages found"
                )
                return
            
            # Check cancellation
            self._check_cancellation()
            
            self._update_progress(
                RefreshStatus.BUILDING, 20, 
                f"Building KG ({len(jira_issues)} issues, {len(confluence_pages)} pages) - {mode_str} mode..."
            )
            
            # Step 3: Build new model
            if quick_mode:
                # Quick mode: Use only NetworkX graph, skip nano-graphrag LLM
                self._build_quick_model(jira_issues, confluence_pages)
            else:
                # Full mode: Build using nano-graphrag with LLM entity extraction
                self._build_new_model(jira_issues, confluence_pages, clear_existing)
            
            # Check cancellation
            self._check_cancellation()
            
            self._update_progress(
                RefreshStatus.VALIDATING, 85, "Validating new model..."
            )
            
            # Step 4: Validate
            if quick_mode:
                # Quick mode validates the NetworkX graph directly
                if not self._validate_quick_model():
                    raise RuntimeError("Quick model validation failed")
            else:
                if not self._validate_new_model():
                    raise RuntimeError("New model validation failed")
            
            # Check cancellation
            self._check_cancellation()
            
            self._update_progress(
                RefreshStatus.SWITCHING, 95, "Switching to new model..."
            )
            
            # Step 5: Atomic switchover (only for full mode with nano-graphrag)
            if not quick_mode:
                self._atomic_switchover()
            
            # Done!
            self._update_progress(
                RefreshStatus.COMPLETED, 100, f"Refresh completed! ({mode_str} mode)",
                completed_at=datetime.now(),
                stats={
                    "jira_issues": len(jira_issues),
                    "confluence_pages": len(confluence_pages),
                    "backup_path": backup_path
                }
            )
            
            # Cleanup old backups
            self.cleanup_old_backups(keep_count=5)
            
            # Notify callback
            if self._on_model_ready:
                self._on_model_ready()
            
        except Exception as e:
            logger.error(f"Refresh failed: {e}")
            import traceback
            traceback.print_exc()
            
            # Check if it was cancelled
            if self._cancel_requested:
                self._update_progress(
                    RefreshStatus.FAILED, self._progress.progress,
                    "Cancelled by user", error="Refresh cancelled"
                )
                logger.info("🛑 Refresh cancelled by user")
            else:
                self._update_progress(
                    RefreshStatus.FAILED, self._progress.progress,
                    f"Failed: {str(e)}", error=str(e)
                )
            
            # Attempt rollback
            if self._progress.backup_path:
                try:
                    self._rollback()
                except Exception as rollback_error:
                    logger.error(f"Rollback also failed: {rollback_error}")
    
    def _build_new_model(
        self,
        jira_issues: list,
        confluence_pages: list,
        clear_existing: bool
    ):
        """Build new model in temporary directory."""
        from app.services.graphrag.nano_graphrag_service import NanoGraphRAGService
        
        # Clean temp dir
        if self.temp_build_dir.exists():
            shutil.rmtree(self.temp_build_dir)
        self.temp_build_dir.mkdir(parents=True)
        
        # Create new service instance pointing to temp dir
        temp_service = NanoGraphRAGService(working_dir=str(self.temp_build_dir))
        
        # Copy existing graph data if not clearing
        if not clear_existing and self.working_dir.exists():
            graph_file = self.working_dir / "graph_chunk_entity_relation.graphml"
            if graph_file.exists():
                shutil.copy(graph_file, self.temp_build_dir / "graph_chunk_entity_relation.graphml")
                logger.info("Migrated existing graph to temp build")
        
        # Populate with progress updates
        total_items = len(jira_issues) + len(confluence_pages)
        processed = 0
        
        def update_build_progress():
            nonlocal processed
            processed += 1
            pct = 20 + int((processed / max(total_items, 1)) * 60)  # 20-80%
            self._update_progress(
                RefreshStatus.BUILDING, pct,
                f"Processing {processed}/{total_items} items..."
            )
        
        # Batch populate
        temp_service.populate_from_jira_confluence(
            jira_issues=jira_issues,
            confluence_pages=confluence_pages
        )
        
        self._update_progress(
            RefreshStatus.BUILDING, 80, "Generating community reports..."
        )
    
    def _build_quick_model(
        self,
        jira_issues: list,
        confluence_pages: list
    ):
        """
        Build knowledge graph using fast NetworkX service (no LLM).
        
        HYBRID APPROACH:
        1. Build graph structure from explicit metadata (fast)
        2. Index content with vector embeddings for semantic search (fast)
        
        This gives you:
        - Fast rebuild (~5-10 minutes instead of 24 hours)
        - Semantic search via embeddings
        - Explicit relationships from Jira/Confluence
        
        What you DON'T get (compared to full mode):
        - Implicit relationships extracted by LLM from text content
        """
        from app.services.graphrag.knowledge_graph_service import knowledge_graph_service
        
        logger.info(f"🚀 Quick mode: Building KG with {len(jira_issues)} issues, {len(confluence_pages)} pages")
        
        # Clear and rebuild the graph
        knowledge_graph_service.clear_graph()
        
        total_items = len(jira_issues) + len(confluence_pages)
        processed = 0
        entities_for_indexing = []
        
        # Process Jira issues
        for issue in jira_issues:
            try:
                knowledge_graph_service.add_jira_issue(issue)
                
                # Prepare for vector indexing
                entities_for_indexing.append({
                    "id": issue.get("key", ""),
                    "type": issue.get("issue_type", "jira_issue"),
                    "text": f"{issue.get('summary', '')} {issue.get('description', '')}"
                })
                
                processed += 1
                if processed % 50 == 0:
                    pct = 20 + int((processed / max(total_items, 1)) * 40)
                    self._update_progress(
                        RefreshStatus.BUILDING, pct,
                        f"Building graph: {processed}/{total_items} items..."
                    )
            except Exception as e:
                logger.warning(f"Failed to add Jira issue {issue.get('key', 'unknown')}: {e}")
        
        # Process Confluence pages
        for page in confluence_pages:
            try:
                knowledge_graph_service.add_confluence_page(page)
                
                # Prepare for vector indexing
                entities_for_indexing.append({
                    "id": page.get("id", ""),
                    "type": "confluence_page",
                    "text": f"{page.get('title', '')} {page.get('body', '')}"
                })
                
                processed += 1
                if processed % 50 == 0:
                    pct = 20 + int((processed / max(total_items, 1)) * 40)
                    self._update_progress(
                        RefreshStatus.BUILDING, pct,
                        f"Building graph: {processed}/{total_items} items..."
                    )
            except Exception as e:
                logger.warning(f"Failed to add Confluence page {page.get('title', 'unknown')}: {e}")
        
        # Save the graph
        knowledge_graph_service.save_graph()
        
        self._update_progress(
            RefreshStatus.BUILDING, 65, "Graph built! Now indexing for semantic search..."
        )
        
        # HYBRID: Also index with embeddings for semantic search
        try:
            from app.services.graphrag.nano_graphrag_service import nano_graphrag_service
            
            def update_index_progress(current, total):
                pct = 65 + int((current / max(total, 1)) * 15)  # 65-80%
                self._update_progress(
                    RefreshStatus.BUILDING, pct,
                    f"Indexing embeddings: {current}/{total}..."
                )
            
            nano_graphrag_service.index_entities_fast(
                entities_for_indexing,
                progress_callback=update_index_progress
            )
            
            logger.info("✅ Hybrid mode: Graph + embeddings complete!")
        except Exception as e:
            logger.warning(f"Embedding indexing skipped (not critical): {e}")
        
        self._update_progress(
            RefreshStatus.BUILDING, 80, "Quick build complete, validating..."
        )
        
        # Copy gpickle to nano_graphrag dir so versions capture it
        try:
            gpickle_src = Path("./data/knowledge_graph.gpickle")
            gpickle_dest = Path("./data/nano_graphrag/knowledge_graph.gpickle")
            if gpickle_src.exists():
                import shutil
                shutil.copy(gpickle_src, gpickle_dest)
                logger.info("Copied NetworkX graph to nano_graphrag dir for versioning")
        except Exception as e:
            logger.warning(f"Could not copy gpickle for versioning: {e}")
        
        logger.info(f"✅ Quick mode: Built graph with {knowledge_graph_service.get_stats()}")
    
    def _validate_quick_model(self) -> bool:
        """Validate the quick-built NetworkX graph."""
        from app.services.graphrag.knowledge_graph_service import knowledge_graph_service
        
        try:
            stats = knowledge_graph_service.get_stats()
            if stats.get('nodes', 0) == 0:
                logger.error("Quick model validation failed: no nodes")
                return False
            logger.info(f"Quick model validated: {stats}")
            return True
        except Exception as e:
            logger.error(f"Quick model validation failed: {e}")
            return False
    
    def _validate_new_model(self) -> bool:
        """Validate the new model before switchover."""
        required_files = [
            "graph_chunk_entity_relation.graphml",
            "vdb_entities.json"
        ]
        
        for filename in required_files:
            if not (self.temp_build_dir / filename).exists():
                logger.error(f"Validation failed: missing {filename}")
                return False
        
        # Check graph has nodes
        try:
            import networkx as nx
            graph = nx.read_graphml(str(self.temp_build_dir / "graph_chunk_entity_relation.graphml"))
            if graph.number_of_nodes() == 0:
                logger.error("Validation failed: graph has no nodes")
                return False
            logger.info(f"New model has {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return False
        
        return True
    
    def _atomic_switchover(self):
        """Atomically switch from old model to new model."""
        # Rename current to .old
        old_backup = self.working_dir.with_suffix('.old')
        if old_backup.exists():
            shutil.rmtree(old_backup)
        
        if self.working_dir.exists():
            self.working_dir.rename(old_backup)
        
        # Move temp to current
        self.temp_build_dir.rename(self.working_dir)
        
        # Remove .old
        if old_backup.exists():
            shutil.rmtree(old_backup)
        
        logger.info("✅ Atomic switchover complete")
    
    def _rollback(self):
        """Rollback to backup on failure."""
        if not self._progress.backup_path:
            logger.warning("No backup to rollback to")
            return
        
        logger.info(f"🔙 Rolling back to: {self._progress.backup_path}")
        self.restore_backup(self._progress.backup_path)
        
        self._update_progress(
            RefreshStatus.ROLLED_BACK, 0,
            "Rolled back to previous version"
        )
    
    # =========================================================================
    # Hot Reload Support
    # =========================================================================
    
    def notify_service_reload(self):
        """
        Notify the nano-graphrag service to reload its instance.
        
        This allows the service to pick up the new model without restart.
        """
        try:
            from app.services.graphrag.nano_graphrag_service import nano_graphrag_service
            
            # Reset the cached RAG instance
            nano_graphrag_service._rag = None
            nano_graphrag_service._initialized = False
            
            logger.info("🔄 Notified nano-graphrag service to reload")
        except Exception as e:
            logger.warning(f"Could not notify service: {e}")


# Global instance
_refresh_manager: Optional[KGRefreshManager] = None


def get_refresh_manager() -> KGRefreshManager:
    """Get or create the global refresh manager."""
    global _refresh_manager
    if _refresh_manager is None:
        _refresh_manager = KGRefreshManager()
    return _refresh_manager

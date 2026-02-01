"""
Knowledge Graph Refresh module.

Provides safe, non-blocking KG refresh operations:
- Backup before refresh
- Hot-swap: old model serves while new builds
- Atomic switchover when ready
- Rollback on failure
- Version management with metadata tracking
"""
from .refresh_manager import (
    KGRefreshManager,
    RefreshStatus,
    RefreshProgress,
    get_refresh_manager
)
from .version_registry import (
    KGVersion,
    KGVersionRegistry,
    get_version_registry
)

__all__ = [
    # Refresh Manager
    "KGRefreshManager",
    "RefreshStatus",
    "RefreshProgress",
    "get_refresh_manager",
    
    # Version Registry
    "KGVersion",
    "KGVersionRegistry",
    "get_version_registry"
]

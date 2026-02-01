import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { kgAdminService } from '../services/kgAdminService';
import type { KGVersion, RefreshStatus } from '../services/kgAdminService';
import { GraphVisualization } from '../components/GraphVisualization';
import './KnowledgeGraph.css';

interface GraphStats {
  total_nodes: number;
  total_edges: number;
  entity_types: Record<string, number>;
  avg_degree: number;
}

interface CentralEntity {
  id: string;
  score: number;
}

interface SelectedNodeInfo {
  id: string;
  type: string;
  title?: string;
}

export function KnowledgeGraph() {
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [centralEntities, setCentralEntities] = useState<CentralEntity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [liveSearchQuery, setLiveSearchQuery] = useState('');

  // Filter state for graph interactivity
  const [filterType, setFilterType] = useState<string | null>(null);
  const [highlightNodeId, setHighlightNodeId] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<SelectedNodeInfo | null>(null);

  // Version management state
  const [versions, setVersions] = useState<KGVersion[]>([]);
  const [, setActiveVersionId] = useState<number | null>(null);
  const [, setLoadingVersions] = useState(false);

  // Refresh state
  const [refreshStatus, setRefreshStatus] = useState<RefreshStatus | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  
  // Dialog state
  const [showRefreshDialog, setShowRefreshDialog] = useState(false);
  const [confirmText, setConfirmText] = useState('');
  const [quickRebuildMode, setQuickRebuildMode] = useState(true); // Default to quick mode
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [newVersionName, setNewVersionName] = useState('');
  const [newVersionDesc, setNewVersionDesc] = useState('');

  // View mode
  const [activeTab, setActiveTab] = useState<'graph' | 'versions'>('graph');

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setLiveSearchQuery(searchQuery);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Handle node selection from graph
  const handleNodeSelect = useCallback((node: SelectedNodeInfo | null) => {
    setSelectedNode(node);
    if (node) {
      setHighlightNodeId(node.id);
    }
  }, []);

  useEffect(() => {
    loadGraphData();
    loadVersions();
    checkRefreshStatus();
  }, []);

  useEffect(() => {
    if (!isRefreshing) return;
    const interval = setInterval(async () => {
      try {
        const status = await kgAdminService.getStatus();
        setRefreshStatus(status);
        if (status.status === 'completed' || status.status === 'failed' || status.status === 'cancelled' || status.status === 'idle') {
          setIsRefreshing(false);
          loadGraphData();
          loadVersions();
        }
      } catch {
        setIsRefreshing(false);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [isRefreshing]);

  async function loadGraphData() {
    try {
      const [statsRes, centralRes] = await Promise.all([
        axios.get('/api/kg/stats'),
        axios.get('/api/kg/central?limit=10'),
      ]);
      setStats(statsRes.data);
      setCentralEntities(centralRes.data.central_entities || []);
      setError(null);
    } catch (err) {
      console.error('Error loading graph data:', err);
      setError('Failed to load knowledge graph data');
    } finally {
      setLoading(false);
    }
  }

  async function loadVersions() {
    setLoadingVersions(true);
    try {
      const data = await kgAdminService.listVersions();
      setVersions(data?.versions || []);
      setActiveVersionId(data?.active_id ?? null);
    } catch (err) {
      console.error('Error loading versions:', err);
      setVersions([]);
    } finally {
      setLoadingVersions(false);
    }
  }

  async function checkRefreshStatus() {
    try {
      const status = await kgAdminService.getStatus();
      setRefreshStatus(status);
      if (status.status === 'building' || status.status === 'fetching_data') {
        setIsRefreshing(true);
      }
    } catch { /* ignore */ }
  }

  async function handleRefreshConfirmed() {
    setShowRefreshDialog(false);
    setConfirmText('');
    setIsRefreshing(true);
    try {
      await kgAdminService.refreshKG(false, quickRebuildMode);
    } catch (err) {
      console.error('Refresh failed:', err);
      setIsRefreshing(false);
    }
  }

  async function handleSaveVersion() {
    if (!newVersionName.trim()) return;
    try {
      await kgAdminService.createVersion(newVersionName, newVersionDesc);
      setShowSaveDialog(false);
      setNewVersionName('');
      setNewVersionDesc('');
      loadVersions();
    } catch (err) {
      console.error('Save version failed:', err);
      alert('Failed to save version');
    }
  }

  async function handleActivateVersion(versionId: number) {
    try {
      await kgAdminService.activateVersion(versionId);
      setActiveVersionId(versionId);
      // Force reload to show updated graph data
      await loadGraphData();
      await loadVersions();
    } catch (err) {
      console.error('Activate version failed:', err);
      alert('Failed to activate version');
    }
  }

  async function handleDeleteVersion(versionId: number) {
    if (!confirm('Are you sure you want to delete this version?')) return;
    try {
      await kgAdminService.deleteVersion(versionId);
      loadVersions();
    } catch (err: any) {
      alert(err.response?.data?.error || 'Failed to delete version');
    }
  }

  async function handleCancelRefresh() {
    if (!confirm('Are you sure you want to cancel the rebuild?')) return;
    try {
      await kgAdminService.cancelRefresh();
      // Immediately clear refresh state
      setIsRefreshing(false);
      setRefreshStatus(null);
      // Reload data to show current state
      await loadGraphData();
      await loadVersions();
    } catch (err) {
      console.error('Cancel failed:', err);
      alert('Failed to cancel rebuild');
    }
  }

  if (loading) {
    return (
      <div className="kg-dashboard">
        <div className="kg-loading">Loading Knowledge Graph...</div>
      </div>
    );
  }

  return (
    <div className="kg-dashboard">
      {/* Header Bar */}
      <div className="kg-topbar">
        <div className="kg-title">
          <h1>🕸️ Knowledge Graph</h1>
          <span className="kg-subtitle">
            {stats ? `${stats.total_nodes} nodes • ${stats.total_edges} edges` : 'Loading...'}
          </span>
        </div>
        <div className="kg-actions">
          <button className="btn-secondary" onClick={() => setShowSaveDialog(true)}>
            💾 Save Version
          </button>
          <button 
            className="btn-danger" 
            onClick={() => setShowRefreshDialog(true)}
            disabled={isRefreshing}
          >
            {isRefreshing ? '🔄 Rebuilding...' : '🔄 Rebuild'}
          </button>
        </div>
      </div>

      {/* Refresh Progress */}
      {isRefreshing && refreshStatus && (
        <div className="kg-progress-bar">
          <div className="progress-fill" style={{ width: `${refreshStatus.progress}%` }} />
          <span className="progress-text">{refreshStatus.stage} ({refreshStatus.progress}%)</span>
          <button className="btn-cancel" onClick={handleCancelRefresh} title="Cancel rebuild">
            ✕ Cancel
          </button>
        </div>
      )}

      {error && <div className="kg-error">{error}</div>}

      {/* Main Content */}
      <div className="kg-content">
        {/* Left Sidebar - Stats & Info */}
        <div className="kg-sidebar">
          {/* Quick Stats */}
          <div className="sidebar-section">
            <h3>📊 Statistics</h3>
            <div className="stat-grid-small">
              <div className="stat-item">
                <span className="stat-number">{stats?.total_nodes ?? 0}</span>
                <span className="stat-label">Nodes</span>
              </div>
              <div className="stat-item">
                <span className="stat-number">{stats?.total_edges ?? 0}</span>
                <span className="stat-label">Edges</span>
              </div>
              <div className="stat-item">
                <span className="stat-number">{(stats?.avg_degree ?? 0).toFixed(1)}</span>
                <span className="stat-label">Avg Degree</span>
              </div>
              <div className="stat-item">
                <span className="stat-number">{Object.keys(stats?.entity_types || {}).length}</span>
                <span className="stat-label">Types</span>
              </div>
            </div>
          </div>

          {/* Entity Types - Clickable to filter */}
          <div className="sidebar-section">
            <h3>📁 Entity Types {filterType && <button className="clear-filter" onClick={() => setFilterType(null)}>✕ Clear</button>}</h3>
            <div className="entity-type-list">
              {stats && Object.entries(stats.entity_types)
                .sort((a, b) => b[1] - a[1])
                .map(([type, count]) => (
                  <div 
                    key={type} 
                    className={`entity-type-row clickable ${filterType === type ? 'active' : ''}`}
                    onClick={() => setFilterType(filterType === type ? null : type)}
                    title={`Click to ${filterType === type ? 'clear' : 'filter by'} ${type}`}
                  >
                    <span className={`type-badge type-${type}`}>{type.replace('_', ' ')}</span>
                    <span className="type-count">{count}</span>
                  </div>
                ))}
            </div>
          </div>

          {/* Most Connected - Clickable to highlight */}
          <div className="sidebar-section">
            <h3>🔗 Most Connected</h3>
            <div className="connected-list">
              {centralEntities.length > 0 ? (
                centralEntities.slice(0, 8).map((entity, idx) => (
                  <div 
                    key={entity.id || idx} 
                    className={`connected-item clickable ${highlightNodeId === entity.id ? 'active' : ''}`}
                    onClick={() => setHighlightNodeId(highlightNodeId === entity.id ? null : entity.id)}
                    title="Click to highlight in graph"
                  >
                    <span className="connected-rank">#{idx + 1}</span>
                    <span className="connected-id">{entity.id}</span>
                    <span className="connected-score">{(entity.score ?? 0).toFixed(3)}</span>
                  </div>
                ))
              ) : (
                <p className="no-data">No centrality data available</p>
              )}
            </div>
          </div>

          {/* Selected Node Info */}
          {selectedNode && (
            <div className="sidebar-section selected-node-section">
              <h3>📌 Selected Node</h3>
              <div className="selected-node-info">
                <div className="node-id">{selectedNode.id}</div>
                <div className="node-type">
                  <span className={`type-badge type-${selectedNode.type}`}>{selectedNode.type}</span>
                </div>
                {selectedNode.title && <div className="node-title">{selectedNode.title}</div>}
                <button 
                  className="btn-small" 
                  onClick={() => { setSelectedNode(null); setHighlightNodeId(null); }}
                >
                  Clear Selection
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Main Area - Graph or Versions */}
        <div className="kg-main">
          {/* Search bar above tabs */}
          <div className="kg-search-bar">
            <div className="search-input-wrapper">
              <span className="search-icon">🔍</span>
              <input
                type="text"
                placeholder="Search nodes by ID or title..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="search-input-large"
              />
              {searchQuery && (
                <button className="search-clear" onClick={() => setSearchQuery('')}>✕</button>
              )}
            </div>
            {(filterType || liveSearchQuery) && (
              <div className="active-filters">
                {filterType && (
                  <span className="filter-tag">
                    Type: {filterType}
                    <button onClick={() => setFilterType(null)}>✕</button>
                  </span>
                )}
                {liveSearchQuery && (
                  <span className="filter-tag">
                    Search: "{liveSearchQuery}"
                    <button onClick={() => setSearchQuery('')}>✕</button>
                  </span>
                )}
              </div>
            )}
          </div>

          <div className="kg-tabs">
            <button 
              className={activeTab === 'graph' ? 'active' : ''} 
              onClick={() => setActiveTab('graph')}
            >
              📈 Graph View
            </button>
            <button 
              className={activeTab === 'versions' ? 'active' : ''} 
              onClick={() => setActiveTab('versions')}
            >
              📦 Versions ({versions.length})
            </button>
          </div>

          {activeTab === 'graph' && (
            <div className="graph-container">
              <GraphVisualization 
                maxNodes={200}
                highlightNodeId={highlightNodeId}
                filterType={filterType}
                searchQuery={liveSearchQuery}
                onNodeSelect={handleNodeSelect}
                onTypeFilter={setFilterType}
              />
            </div>
          )}

          {activeTab === 'versions' && (
            <div className="versions-container">
              {versions.length === 0 ? (
                <div className="no-versions">
                  <p>No saved versions yet.</p>
                  <p>Click "Save Version" to create a snapshot of the current graph.</p>
                </div>
              ) : (
                <table className="versions-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Mode</th>
                      <th>Graph</th>
                      <th>Quality</th>
                      <th>Size</th>
                      <th>Created</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {versions.map((v) => {
                      // Calculate quality score (mirror backend logic)
                      const orphanRatio = v.node_count > 0 ? (v.orphan_node_count ?? 0) / v.node_count : 0;
                      const orphanScore = Math.max(0, 100 - orphanRatio * 200);
                      const connectivityScore = Math.min(100, (v.avg_degree ?? 0) * 20);
                      const fragScore = (v.connected_components ?? 1) > 1 
                        ? Math.max(0, 100 - ((v.connected_components ?? 1) - 1) * 10) 
                        : 100;
                      const qualityScore = Math.round((orphanScore + connectivityScore + fragScore) / 3);
                      
                      return (
                        <tr key={v.id} className={v.is_active ? 'active-version' : ''}>
                          <td>
                            {v.is_active && <div className="active-badge" style={{ marginBottom: '4px' }}>✓ Active</div>}
                            <strong>{v.name || 'Unnamed'}</strong>
                            {v.description && <div className="version-desc">{v.description}</div>}
                            {v.tags && v.tags.length > 0 && (
                              <div className="version-tags">
                                {v.tags.map(tag => (
                                  <span key={tag} className="version-tag">{tag}</span>
                                ))}
                              </div>
                            )}
                          </td>
                          <td>
                            <span className={`build-mode-badge ${v.build_mode || 'hybrid'}`}>
                              {v.build_mode === 'deep' ? '🧠' : '⚡'}
                            </span>
                            {v.build_duration_sec > 0 && (
                              <div className="build-time">
                                {v.build_duration_sec < 60 
                                  ? `${v.build_duration_sec}s`
                                  : `${Math.round(v.build_duration_sec / 60)}m`}
                              </div>
                            )}
                          </td>
                          <td>
                            <div className="version-stat">
                              <span>{(v.node_count ?? 0).toLocaleString()} nodes</span>
                              <small>
                                {(v.edge_count ?? 0).toLocaleString()} edges
                                {v.embedding_count > 0 && ` • ${v.embedding_count} vectors`}
                              </small>
                            </div>
                          </td>
                          <td>
                            <div className="quality-score" title={`Orphans: ${v.orphan_node_count ?? 0}, Components: ${v.connected_components ?? 1}, Avg Degree: ${(v.avg_degree ?? 0).toFixed(1)}`}>
                              <div className={`score-bar ${qualityScore >= 70 ? 'good' : qualityScore >= 40 ? 'ok' : 'poor'}`} 
                                   style={{ width: `${qualityScore}%` }} />
                              <span>{qualityScore}%</span>
                            </div>
                          </td>
                          <td>
                            <div className="version-stat">
                              <span>{(v.size_mb ?? 0).toFixed(1)} MB</span>
                              <small>
                                {v.jira_issues_count ?? 0}+{v.confluence_pages_count ?? 0} docs
                              </small>
                            </div>
                          </td>
                          <td>{v.created_at ? new Date(v.created_at).toLocaleDateString() : '-'}</td>
                          <td>
                            {!v.is_active ? (
                              <>
                                <button className="btn-small btn-use" onClick={() => handleActivateVersion(v.id)}>
                                  Use
                                </button>
                                <button className="btn-small btn-delete" onClick={() => handleDeleteVersion(v.id)}>
                                  🗑️
                                </button>
                              </>
                            ) : (
                              <span className="current-badge">Current</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Refresh Confirmation Dialog */}
      {showRefreshDialog && (
        <div className="dialog-overlay">
          <div className="dialog">
            <h2>⚠️ Rebuild Knowledge Graph</h2>
            <p>This will rebuild the entire graph from Jira and Confluence.</p>
            
            {/* Quick Mode Toggle */}
            <div className="rebuild-mode-toggle">
              <label className="mode-option">
                <input
                  type="radio"
                  name="rebuildMode"
                  checked={quickRebuildMode}
                  onChange={() => setQuickRebuildMode(true)}
                />
                <div className="mode-content">
                  <strong>⚡ Hybrid Rebuild</strong>
                  <span>~5-10 minutes • Graph from metadata + semantic search via embeddings</span>
                </div>
              </label>
              <label className="mode-option">
                <input
                  type="radio"
                  name="rebuildMode"
                  checked={!quickRebuildMode}
                  onChange={() => setQuickRebuildMode(false)}
                />
                <div className="mode-content">
                  <strong>🧠 Deep Rebuild (AI)</strong>
                  <span>~2-24 hours • LLM extracts implicit relationships from text</span>
                </div>
              </label>
            </div>

            <p className="confirm-text-label">Type <strong>REBUILD</strong> to confirm:</p>
            <input
              type="text"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              placeholder="Type REBUILD"
            />
            <div className="dialog-actions">
              <button className="btn-secondary" onClick={() => setShowRefreshDialog(false)}>
                Cancel
              </button>
              <button 
                className={quickRebuildMode ? "btn-primary" : "btn-danger"}
                onClick={handleRefreshConfirmed}
                disabled={confirmText !== 'REBUILD'}
              >
                {quickRebuildMode ? '⚡ Hybrid Rebuild' : '🧠 Deep Rebuild'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Save Version Dialog */}
      {showSaveDialog && (
        <div className="dialog-overlay">
          <div className="dialog">
            <h2>💾 Save Graph Version</h2>
            <p>Create a named snapshot of the current knowledge graph.</p>
            <input
              type="text"
              value={newVersionName}
              onChange={(e) => setNewVersionName(e.target.value)}
              placeholder="Version name (e.g., 'Sprint 42 Release')"
            />
            <textarea
              value={newVersionDesc}
              onChange={(e) => setNewVersionDesc(e.target.value)}
              placeholder="Description (optional)"
            />
            <div className="dialog-actions">
              <button className="btn-secondary" onClick={() => setShowSaveDialog(false)}>
                Cancel
              </button>
              <button 
                className="btn-primary" 
                onClick={handleSaveVersion}
                disabled={!newVersionName.trim()}
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

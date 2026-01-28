import { useState, useEffect } from 'react';
import axios from 'axios';
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

export function KnowledgeGraph() {
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [centralEntities, setCentralEntities] = useState<CentralEntity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);

  useEffect(() => {
    loadGraphData();
  }, []);

  async function loadGraphData() {
    try {
      const [statsRes, centralRes] = await Promise.all([
        axios.get('/api/kg/stats'),
        axios.get('/api/kg/central?limit=15'),
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

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    try {
      const response = await axios.get(`/api/kg/entity/${searchQuery}`);
      setSearchResults([response.data]);
    } catch (err: any) {
      if (err.response?.status === 404) {
        alert(`Entity "${searchQuery}" not found in knowledge graph`);
      } else {
        console.error('Search error:', err);
        alert('Search failed');
      }
    }
  }

  if (loading) {
    return (
      <div className="kg-page">
        <div className="kg-header">
          <h1>🕸️ Knowledge Graph</h1>
          <p>Loading graph data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="kg-page">
      <div className="kg-header">
        <h1>🕸️ Knowledge Graph</h1>
        <p>Explore relationships between Jira issues, projects, and Confluence pages</p>
      </div>

      {error && (
        <div className="error-message">
          {error}
        </div>
      )}

      {stats && (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-value">{stats.total_nodes.toLocaleString()}</div>
            <div className="stat-label">Entities</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.total_edges.toLocaleString()}</div>
            <div className="stat-label">Relationships</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{Object.keys(stats.entity_types).length}</div>
            <div className="stat-label">Entity Types</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.avg_degree.toFixed(1)}</div>
            <div className="stat-label">Avg Connections</div>
          </div>
        </div>
      )}

      <div className="search-section">
        <form onSubmit={handleSearch} className="search-form">
          <input
            type="text"
            placeholder="Search by entity ID (e.g., ACTHUB-9, LIFEOPS-1)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="search-input"
          />
          <button type="submit" className="search-btn">
            🔍 Search
          </button>
        </form>
      </div>

      {searchResults.length > 0 && (
        <div className="search-results">
          <h3>Search Results</h3>
          {searchResults.map((entity, idx) => (
            <div key={idx} className="entity-card">
              <div className="entity-header">
                <span className="entity-id">{entity.id}</span>
                <span className="entity-type">{entity.entity_type}</span>
              </div>
              <pre className="entity-data">{JSON.stringify(entity, null, 2)}</pre>
            </div>
          ))}
        </div>
      )}

      {stats && Object.keys(stats.entity_types).length > 0 && (
        <div className="entity-types-section">
          <h3>Entity Types</h3>
          <div className="entity-types-grid">
            {Object.entries(stats.entity_types).map(([type, count]) => (
              <div key={type} className="entity-type-card">
                <div className="type-count">{count}</div>
                <div className="type-name">{type}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {centralEntities.length > 0 && (
        <div className="central-entities-section">
          <h3>Most Connected Entities</h3>
          <div className="entities-list">
            {centralEntities.map((entity, idx) => (
              <div key={entity.id} className="central-entity">
                <span className="rank">#{idx + 1}</span>
                <span className="entity-id">{entity.id}</span>
                <span className="score">{entity.score.toFixed(3)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="help-section">
        <h3>💡 Tips</h3>
        <ul>
          <li>The Knowledge Graph auto-updates as you query Jira and Confluence</li>
          <li>Search for specific issue keys (e.g., ACTHUB-9) to see their connections</li>
          <li>Run <code>python repopulate_kg.py</code> to rebuild the graph from scratch</li>
        </ul>
      </div>
    </div>
  );
}

import axios from 'axios';

export interface KGVersion {
  id: number;
  name: string;
  description: string;
  created_at: string;
  path: string;
  is_active: boolean;
  
  // Graph stats
  node_count: number;
  edge_count: number;
  community_count: number;
  
  // Vector stats
  embedding_count: number;
  chunk_count: number;
  
  // Build info
  build_mode: 'hybrid' | 'deep';
  build_duration_sec: number;
  
  // Data sources
  jira_issues_count: number;
  confluence_pages_count: number;
  
  // Data lineage
  jql_filter: string;
  cql_filter: string;
  
  // Quality metrics
  orphan_node_count: number;
  connected_components: number;
  avg_degree: number;
  
  // Performance
  avg_query_time_ms: number | null;
  p95_query_time_ms: number | null;
  query_count: number;
  
  // Storage
  size_mb: number;
  
  // Diff from previous
  nodes_added: number;
  nodes_removed: number;
  edges_changed: number;
  
  // Tags
  tags: string[];
}

export interface RefreshStatus {
  status: string;
  progress: number;
  stage: string;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
  backup_path: string | null;
}

export interface Backup {
  name: string;
  path: string;
  created: string;
  size_mb: number;
}

export const kgAdminService = {
  // Refresh operations
  async refreshKG(clearExisting: boolean = false, quickMode: boolean = false): Promise<{ status: string; message: string }> {
    const response = await axios.post('/api/kg/maintenance/refresh', null, {
      params: { clear_existing: clearExisting, quick_mode: quickMode }
    });
    return response.data;
  },

  async getStatus(): Promise<RefreshStatus> {
    const response = await axios.get('/api/kg/maintenance/status');
    return response.data;
  },

  async cancelRefresh(): Promise<{ status: string; message: string }> {
    const response = await axios.post('/api/kg/maintenance/cancel');
    return response.data;
  },

  // Version operations
  async listVersions(): Promise<{ versions: KGVersion[]; count: number; active_id: number | null }> {
    const response = await axios.get('/api/kg/maintenance/versions');
    return response.data;
  },

  async createVersion(name: string, description: string = '', makeActive: boolean = false): Promise<{ status: string; version: KGVersion }> {
    const response = await axios.post('/api/kg/maintenance/versions', null, {
      params: { name, description, make_active: makeActive }
    });
    return response.data;
  },

  async activateVersion(versionId: number): Promise<{ status: string; version: KGVersion }> {
    const response = await axios.post(`/api/kg/maintenance/versions/${versionId}/activate`);
    return response.data;
  },

  async deleteVersion(versionId: number): Promise<{ status: string }> {
    const response = await axios.delete(`/api/kg/maintenance/versions/${versionId}`);
    return response.data;
  },

  async importBackups(): Promise<{ status: string; count: number }> {
    const response = await axios.post('/api/kg/maintenance/versions/import-backups');
    return response.data;
  },

  // Backup operations
  async listBackups(): Promise<{ backups: Backup[]; count: number }> {
    const response = await axios.get('/api/kg/maintenance/backups');
    return response.data;
  },

  async createBackup(reason: string = 'manual'): Promise<{ status: string; backup_path: string }> {
    const response = await axios.post('/api/kg/maintenance/backups', null, {
      params: { reason }
    });
    return response.data;
  },

  async restoreBackup(backupPath: string): Promise<{ status: string }> {
    const response = await axios.post('/api/kg/maintenance/backups/restore', null, {
      params: { backup_path: backupPath }
    });
    return response.data;
  },

  async cleanupBackups(keepCount: number = 5): Promise<{ status: string; removed: number }> {
    const response = await axios.delete('/api/kg/maintenance/backups/cleanup', {
      params: { keep_count: keepCount }
    });
    return response.data;
  }
};

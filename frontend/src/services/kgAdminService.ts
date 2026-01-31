import axios from 'axios';

export const kgAdminService = {
  async refreshKG(): Promise<{ status: string }> {
    const response = await axios.post('/api/kg-refresh/trigger');
    return response.data;
  },
  async getStatus(): Promise<{ progress: number; stage: string }> {
    const response = await axios.get('/api/kg-refresh/status');
    return response.data;
  },
};

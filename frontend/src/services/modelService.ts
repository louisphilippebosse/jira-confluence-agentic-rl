import axios from 'axios';

export const modelService = {
  async getModelStatus(): Promise<{ ready: boolean; status: string }> {
    const response = await axios.get('/api/model-status');
    return response.data;
  },
};

import axios from 'axios';

export const modelProgressService = {
  async getProgress(): Promise<{ progress: number; downloaded: number; total: number }> {
    const response = await axios.get('/api/model-progress');
    return response.data;
  },
};

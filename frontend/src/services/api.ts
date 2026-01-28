import axios from 'axios';
import type { ChatRequest, ChatResponse, Session, ChatMessage } from '../types';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const chatService = {
  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    const response = await api.post('/chat', request);
    return response.data;
  },

  async getSessions(): Promise<Session[]> {
    const response = await api.get('/sessions');
    return response.data;
  },

  async getSession(sessionId: string): Promise<{ messages: ChatMessage[] }> {
    const response = await api.get(`/sessions/${sessionId}`);
    return response.data;
  },

  async deleteSession(sessionId: string): Promise<void> {
    await api.delete(`/sessions/${sessionId}`);
  },

  async updateSessionTitle(sessionId: string, title: string): Promise<void> {
    await api.patch(`/sessions/${sessionId}`, { title });
  },

  async submitFeedback(feedback: {
    session_id: string;
    message_id: number;
    feedback_value: number;
    comment?: string;
  }): Promise<void> {
    await api.post('/feedback', feedback);
  },
};

export default api;

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
  message_id?: number;
}

export interface Session {
  session_id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface ChatRequest {
  message: string;
  session_id?: string;
  context_modes?: ('jira' | 'confluence' | 'web')[];
}

export interface ChatResponse {
  message: string;
  session_id: string;
  timestamp: string;
  message_id: number;
}

export type ContextMode = 'auto' | ('jira' | 'confluence' | 'web')[];

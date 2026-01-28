import React, { createContext, useContext, useState, ReactNode } from 'react';
import type { ChatMessage, Session, ContextMode } from '../types';

interface AppContextType {
  currentSessionId: string | null;
  setCurrentSessionId: (id: string | null) => void;
  sessions: Session[];
  setSessions: (sessions: Session[]) => void;
  messages: ChatMessage[];
  setMessages: (messages: ChatMessage[]) => void;
  contextMode: ContextMode;
  setContextMode: (mode: ContextMode) => void;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export function AppProvider({ children }: { children: ReactNode }) {
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [contextMode, setContextMode] = useState<ContextMode>('auto');
  const [isLoading, setIsLoading] = useState(false);

  return (
    <AppContext.Provider
      value={{
        currentSessionId,
        setCurrentSessionId,
        sessions,
        setSessions,
        messages,
        setMessages,
        contextMode,
        setContextMode,
        isLoading,
        setIsLoading,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within AppProvider');
  }
  return context;
}

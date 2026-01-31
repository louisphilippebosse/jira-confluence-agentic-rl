import { createContext, useContext, useState } from 'react';
import type { ChatMessage, Session, ContextMode } from '../types';
import type { ReactNode } from 'react';

import type { Dispatch, SetStateAction } from 'react';

interface AppContextType {
  currentSessionId: string | null;
  setCurrentSessionId: Dispatch<SetStateAction<string | null>>;
  sessions: Session[];
  setSessions: Dispatch<SetStateAction<Session[]>>;
  messages: ChatMessage[];
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>;
  contextMode: ContextMode;
  setContextMode: Dispatch<SetStateAction<ContextMode>>;
  isLoading: boolean;
  setIsLoading: Dispatch<SetStateAction<boolean>>;
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
        setMessages, // This is the useState setter, supports updater fn
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

import { useEffect, useState } from 'react';
import { useApp } from '../contexts/AppContext';
import { chatService } from '../services/api';
import './SessionList.css';

export function SessionList() {
  const { sessions, setSessions, currentSessionId, setCurrentSessionId, setMessages } = useApp();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');

  useEffect(() => {
    loadSessions();
  }, []);

  async function loadSessions() {
    try {
      const data = await chatService.getSessions();
      setSessions(data);
    } catch (error) {
      console.error('Error loading sessions:', error);
    }
  }

  async function selectSession(sessionId: string) {
    try {
      const data = await chatService.getSession(sessionId);
      setCurrentSessionId(sessionId);
      setMessages(data.messages);
    } catch (error) {
      console.error('Error loading session:', error);
    }
  }

  function startNewChat() {
    setCurrentSessionId(null);
    setMessages([]);
  }

  async function deleteSession(sessionId: string, e: React.MouseEvent) {
    e.stopPropagation();
    if (!confirm('Delete this conversation?')) return;
    
    try {
      await chatService.deleteSession(sessionId);
      setSessions(sessions.filter(s => s.session_id !== sessionId));
      if (currentSessionId === sessionId) {
        setCurrentSessionId(null);
        setMessages([]);
      }
    } catch (error) {
      console.error('Error deleting session:', error);
    }
  }

  function startEdit(session: any, e: React.MouseEvent) {
    e.stopPropagation();
    setEditingId(session.session_id);
    setEditTitle(session.title);
  }

  async function saveEdit(sessionId: string) {
    if (!editTitle.trim()) return;
    
    try {
      await chatService.updateSessionTitle(sessionId, editTitle);
      setSessions(sessions.map(s => 
        s.session_id === sessionId ? { ...s, title: editTitle } : s
      ));
      setEditingId(null);
    } catch (error) {
      console.error('Error updating title:', error);
    }
  }

  function cancelEdit() {
    setEditingId(null);
    setEditTitle('');
  }

  return (
    <div className="session-list">
      <h3>Conversations</h3>
      <button className="new-chat-btn" onClick={startNewChat}>
        + New Chat
      </button>
      <div className="sessions">
        {sessions.map((session) => (
          <div
            key={session.session_id}
            className={`session-item ${currentSessionId === session.session_id ? 'active' : ''}`}
            onClick={() => !editingId && selectSession(session.session_id)}
          >
            {editingId === session.session_id ? (
              <input
                type="text"
                className="session-title-edit"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') saveEdit(session.session_id);
                  if (e.key === 'Escape') cancelEdit();
                }}
                onBlur={() => saveEdit(session.session_id)}
                autoFocus
                onClick={(e) => e.stopPropagation()}
              />
            ) : (
              <>
                <div className="session-title" title={session.title}>
                  {session.title}
                </div>
                <div className="session-meta">
                  {session.message_count} messages
                </div>
                <div className="session-actions">
                  <button
                    className="action-btn edit-btn"
                    onClick={(e) => startEdit(session, e)}
                    title="Rename"
                  >
                    ✏️
                  </button>
                  <button
                    className="action-btn delete-btn"
                    onClick={(e) => deleteSession(session.session_id, e)}
                    title="Delete"
                  >
                    🗑️
                  </button>
                </div>
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

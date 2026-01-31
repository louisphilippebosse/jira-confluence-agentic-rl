
import { useState, useRef, useEffect } from 'react';
import { kgAdminService } from '../services/kgAdminService';
import { modelService } from '../services/modelService';
import { modelProgressService } from '../services/modelProgressService';
import { chatService } from '../services/api';
import { marked } from 'marked';
import { useApp } from '../contexts/AppContext';
import { ContextDropdown } from './ContextDropdown';
import type { ChatMessage } from '../types';
import './Chat.css';

export function Chat() {
  // KG refresh state (must be inside component)
  const [kgRefreshing, setKgRefreshing] = useState(false);
  const [kgProgress, setKgProgress] = useState<number>(0);
  const [kgStage, setKgStage] = useState<string>('');

  // Poll KG refresh progress if running
  useEffect(() => {
    let interval: any;
    if (kgRefreshing) {
      const poll = async () => {
        try {
          const status = await kgAdminService.getStatus();
          setKgProgress(status.progress);
          setKgStage(status.stage);
          if (status.progress >= 100 || status.stage.startsWith('Error')) {
            setKgRefreshing(false);
          }
        } catch {
          setKgStage('Error fetching status');
          setKgRefreshing(false);
        }
      };
      poll();
      interval = setInterval(poll, 2000);
    }
    return () => clearInterval(interval);
  }, [kgRefreshing]);

  const handleKgRefresh = async () => {
    setKgRefreshing(true);
    setKgProgress(0);
    setKgStage('Starting...');
    await kgAdminService.refreshKG();
  };

  const { currentSessionId, setCurrentSessionId, messages, setMessages, contextMode, isLoading, setIsLoading } = useApp();
  const [modelLoading, setModelLoading] = useState(false);
  const [modelStatus, setModelStatus] = useState<string>('');
  const [modelProgress, setModelProgress] = useState<number | null>(null);
  const [modelDownloaded, setModelDownloaded] = useState<number | null>(null);
  const [modelTotal, setModelTotal] = useState<number | null>(null);

  // Poll model readiness on mount
  useEffect(() => {
    let interval: any;
    let cancelled = false;
    async function checkModel() {
      try {
        const res = await modelService.getModelStatus();
        if (!cancelled) {
          setModelLoading(!res.ready);
          setModelStatus(res.status);
          if (!res.ready) {
            // Try to get progress if not ready
            try {
              const prog = await modelProgressService.getProgress();
              setModelProgress(prog.progress);
              setModelDownloaded(prog.downloaded);
              setModelTotal(prog.total);
            } catch {
              setModelProgress(null);
            }
          } else {
            setModelProgress(null);
            setModelDownloaded(null);
            setModelTotal(null);
          }
        }
      } catch (e) {
        if (!cancelled) {
          setModelLoading(true);
          setModelStatus('Checking model status...');
          setModelProgress(null);
          setModelDownloaded(null);
          setModelTotal(null);
        }
      }
    }
    checkModel();
    // Poll every 10 seconds only if model is not ready
    interval = setInterval(() => {
      if (!modelLoading) {
        clearInterval(interval);
        return;
      }
      checkModel();
    }, 10000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [modelLoading]);

  const [input, setInput] = useState<string>('');
  const [feedbackState, setFeedbackState] = useState<Record<number, number>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
    }
  }, [input]);


  async function sendMessage() {
    if (!input.trim() || isLoading || modelLoading) return;

    const userMessage: ChatMessage = {
      role: 'user',
      content: input,
    };

    setMessages((prev: ChatMessage[]) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    setModelLoading(false);

    try {
      // Send message to chat API
      const response = await chatService.sendMessage({
        message: input,
        session_id: currentSessionId || undefined,
        context_modes: contextMode === 'auto' ? undefined : contextMode,
      });

      setCurrentSessionId(response.session_id);

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response.message,
        message_id: response.message_id,
        timestamp: response.timestamp,
      };

      setMessages((prev: ChatMessage[]) => [...prev, assistantMessage]);
    } catch (error: any) {
      console.error('Error sending message:', error);
      // Detect model-not-ready error from backend
      let isModelNotReady = false;
      if (error?.response?.data?.detail) {
        const detail = error.response.data.detail;
        if (
          typeof detail === 'string' &&
          (detail.toLowerCase().includes('model not ready') || detail.toLowerCase().includes('model is still loading'))
        ) {
          isModelNotReady = true;
        }
      }
      if (isModelNotReady) {
        setModelLoading(true);
        setModelStatus('Model is still loading');
      } else {
        const errorMessage: ChatMessage = {
          role: 'assistant',
          content: 'Sorry, I encountered an error processing your request. Please try again.',
        };
        setMessages((prev: ChatMessage[]) => [...prev, errorMessage]);
      }
    } finally {
      setIsLoading(false);
    }
  }


  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }


  async function handleFeedback(messageId: number | undefined, value: number) {
    if (!messageId || !currentSessionId) return;

    try {
      await chatService.submitFeedback({
        session_id: currentSessionId,
        message_id: messageId,
        feedback_value: value,
      });
      setFeedbackState((prev: Record<number, number>) => ({ ...prev, [messageId]: value }));
    } catch (error) {
      console.error('Error submitting feedback:', error);
    }
  }


  return (
    <div className="chat-container">

      <div className="chat-messages">
        <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 12, marginBottom: 8 }}>
          <button onClick={handleKgRefresh} disabled={kgRefreshing} style={{ padding: '6px 16px', borderRadius: 6, background: kgRefreshing ? '#ccc' : '#4b9cff', color: '#fff', border: 'none', cursor: kgRefreshing ? 'not-allowed' : 'pointer', fontWeight: 500, position: 'relative' }}>
            {kgRefreshing ? 'Refreshing Knowledge Graph...' : 'Refresh Knowledge Graph'}
          </button>
          {kgRefreshing && (
            <div style={{ display: 'inline-block', marginLeft: 8, minWidth: 120 }}>
              <div style={{ background: '#eee', borderRadius: 8, height: 8, width: 120, position: 'relative', overflow: 'hidden', verticalAlign: 'middle' }}>
                <div style={{ background: '#4b9cff', height: '100%', width: `${kgProgress}%`, borderRadius: 8, transition: 'width 0.5s' }} />
              </div>
              <div style={{ fontSize: 11, marginTop: 2, color: '#555' }}>{kgStage} ({kgProgress}%)</div>
            </div>
          )}
        </div>

        {/* OLLAMA MODEL PROGRESS BAR (independent) */}
        {modelLoading && (
          <div className="model-loading-message" style={{ marginBottom: 24 }}>
            <h2>Model loading, please wait…</h2>
            <p style={{ color: modelStatus && modelStatus.toLowerCase().includes('not found') ? '#d32f2f' : undefined }}>
              {modelStatus || 'The AI model is still loading or warming up. This can take a minute after startup or restart.'}
            </p>
            <div style={{ margin: '16px 0' }}>
              <div className="progress-bar-outer" style={{ background: '#eee', borderRadius: 8, height: 12, width: 200, margin: '0 auto', position: 'relative', overflow: 'hidden' }}>
                <div className="progress-bar-inner" style={{ background: '#4b9cff', height: '100%', width: `${modelProgress !== null ? modelProgress : 100}%`, borderRadius: 8, transition: 'width 0.5s', animation: modelProgress === null ? 'progressBarIndeterminate 1.5s linear infinite' : undefined }} />
              </div>
              <style>{`
                @keyframes progressBarIndeterminate {
                  0% { opacity: 0.3; width: 10%; left: 0; }
                  50% { opacity: 1; width: 80%; left: 10%; }
                  100% { opacity: 0.3; width: 10%; left: 90%; }
                }
                .progress-bar-inner {
                  position: absolute;
                  left: 0;
                  top: 0;
                }
              `}</style>
              {modelProgress !== null && modelDownloaded !== null && modelTotal !== null && (
                <div style={{ textAlign: 'center', marginTop: 4, fontSize: 12 }}>
                  {formatBytes(modelDownloaded)} / {formatBytes(modelTotal)} ({modelProgress}%)
                </div>
              )}
            </div>
            <p>You can continue to use other features while you wait.</p>
          </div>
        )}

        {(!modelLoading && !kgRefreshing && messages.length === 0) ? (
          <div className="welcome-message">
            <h2>Welcome! 👋</h2>
            <p>I'm your AI assistant for delivery intelligence and decision support.</p>
            <p>I can help you with:</p>
            <ul>
              <li>📊 Analyze project delivery metrics and sprint progress</li>
              <li>🔍 Search Jira issues and Confluence documentation</li>
              <li>📈 Identify risks and provide recommendations</li>
              <li>💡 Answer questions about project status</li>
            </ul>
            <p><strong>Try asking:</strong></p>
            <ul>
              <li>"Show me open issues in project ABC"</li>
              <li>"What's the delivery status of our current sprint?"</li>
              <li>"Search for documentation about API integration"</li>
            </ul>
          </div>
        ) : (
          messages.map((msg: ChatMessage, index: number) => (
            <div key={index} className={`message ${msg.role}`}>
              <div className="message-content" dangerouslySetInnerHTML={{ __html: marked(msg.content) }} />
              {msg.role === 'assistant' && msg.message_id && (
                <div className="feedback-buttons">
                  <button
                    className={`feedback-btn ${feedbackState[msg.message_id] === 1 ? 'active' : ''}`}
                    onClick={() => handleFeedback(msg.message_id!, feedbackState[msg.message_id!] === 1 ? 0 : 1)}
                    title="Good response"
                  >
                    👍
                  </button>
                  <button
                    className={`feedback-btn ${feedbackState[msg.message_id] === -1 ? 'active' : ''}`}
                    onClick={() => handleFeedback(msg.message_id!, feedbackState[msg.message_id!] === -1 ? 0 : -1)}
                    title="Bad response"
                  >
                    👎
                  </button>
                </div>
              )}
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="input-container">
        <div className="input-wrapper">
          <ContextDropdown />
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask me anything about your projects..."
            rows={1}
            disabled={isLoading || modelLoading}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || isLoading || modelLoading}
            className="send-btn"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M2 10L18 2L12 18L10 11L2 10Z" fill="currentColor"/>
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

// Utility to format bytes as human-readable string
function formatBytes(bytes: number | null): string {
  if (bytes === null || isNaN(bytes)) return '';
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let i = -1;
  let value = bytes;
  do {
    value = value / 1024;
    i++;
  } while (value >= 1024 && i < units.length - 1);
  return `${value.toFixed(2)} ${units[i]}`;
}

import { useState, useRef, useEffect } from 'react';
import { marked } from 'marked';
import { useApp } from '../contexts/AppContext';
import { chatService } from '../services/api';
import { ContextDropdown } from './ContextDropdown';
import type { ChatMessage } from '../types';
import './Chat.css';

export function Chat() {
  const { currentSessionId, setCurrentSessionId, messages, setMessages, contextMode, isLoading, setIsLoading } = useApp();
  const [input, setInput] = useState('');
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
    if (!input.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      role: 'user',
      content: input,
    };

    setMessages([...messages, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
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

      setMessages([...messages, assistantMessage]);
    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your request. Please try again.',
      };
      setMessages([...messages, errorMessage]);
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
      setFeedbackState(prev => ({ ...prev, [messageId]: value }));
    } catch (error) {
      console.error('Error submitting feedback:', error);
    }
  }

  return (
    <div className="chat-container">
      <div className="chat-messages">
        {messages.length === 0 ? (
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
          messages.map((msg, index) => (
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
            disabled={isLoading}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || isLoading}
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

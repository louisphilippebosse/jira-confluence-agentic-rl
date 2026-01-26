// Global state
let currentSessionId = null;
let sessions = [];

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
    setupEventListeners();
});

async function initializeApp() {
    await loadSessions();
}

function setupEventListeners() {
    const sendBtn = document.getElementById('send-btn');
    const messageInput = document.getElementById('message-input');
    const newChatBtn = document.getElementById('new-chat-btn');

    // Send message on button click
    sendBtn.addEventListener('click', sendMessage);

    // Send message on Enter (Shift+Enter for new line)
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Auto-resize textarea
    messageInput.addEventListener('input', () => {
        messageInput.style.height = 'auto';
        messageInput.style.height = messageInput.scrollHeight + 'px';
    });

    // New chat button
    newChatBtn.addEventListener('click', startNewChat);
}

function startNewChat() {
    currentSessionId = null;
    clearChatMessages();
    showWelcomeMessage();
    updateSessionList();
}

async function sendMessage() {
    const messageInput = document.getElementById('message-input');
    const message = messageInput.value.trim();
    
    if (!message) return;

    // Clear input and disable button
    messageInput.value = '';
    messageInput.style.height = 'auto';
    setLoading(true);

    // Add user message to UI
    addMessageToUI('user', message);

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                session_id: currentSessionId
            })
        });

        if (!response.ok) {
            throw new Error('Failed to send message');
        }

        const data = await response.json();
        currentSessionId = data.session_id;

        // Add assistant message to UI
        addMessageToUI('assistant', data.message);

        // Reload sessions
        await loadSessions();
    } catch (error) {
        console.error('Error sending message:', error);
        addMessageToUI('assistant', 'Sorry, I encountered an error processing your request. Please try again.');
    } finally {
        setLoading(false);
        messageInput.focus();
    }
}

function addMessageToUI(role, content) {
    const messagesContainer = document.getElementById('chat-messages');
    
    // Remove welcome message if present
    const welcomeMessage = messagesContainer.querySelector('.welcome-message');
    if (welcomeMessage) {
        welcomeMessage.remove();
    }

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = role === 'user' ? 'You' : '🤖';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    // Format content (simple markdown-like formatting)
    contentDiv.innerHTML = formatMessage(content);

    const timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    timeDiv.textContent = new Date().toLocaleTimeString();

    contentDiv.appendChild(timeDiv);
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);

    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function formatMessage(content) {
    // Simple formatting for better readability
    let formatted = content
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')  // Bold
        .replace(/\*(.*?)\*/g, '<em>$1</em>')  // Italic
        .replace(/`([^`]+)`/g, '<code>$1</code>')  // Inline code
        .replace(/\n/g, '<br>');  // Line breaks

    // Format code blocks
    formatted = formatted.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');

    return formatted;
}

async function loadSessions() {
    try {
        const response = await fetch('/api/sessions');
        if (!response.ok) return;

        sessions = await response.json();
        updateSessionList();
    } catch (error) {
        console.error('Error loading sessions:', error);
    }
}

function updateSessionList() {
    const sessionsList = document.getElementById('sessions-list');
    sessionsList.innerHTML = '';

    if (sessions.length === 0) {
        sessionsList.innerHTML = '<p style="color: #5e6c84; font-size: 0.9rem; text-align: center; padding: 1rem;">No conversations yet</p>';
        return;
    }

    sessions.forEach((sessionId, index) => {
        const sessionDiv = document.createElement('div');
        sessionDiv.className = 'session-item';
        if (sessionId === currentSessionId) {
            sessionDiv.classList.add('active');
        }

        const header = document.createElement('div');
        header.className = 'session-item-header';

        const title = document.createElement('div');
        title.className = 'session-title';
        title.textContent = `Chat ${sessions.length - index}`;

        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'delete-session';
        deleteBtn.textContent = '×';
        deleteBtn.onclick = (e) => {
            e.stopPropagation();
            deleteSession(sessionId);
        };

        header.appendChild(title);
        header.appendChild(deleteBtn);
        sessionDiv.appendChild(header);

        sessionDiv.onclick = () => loadConversation(sessionId);
        sessionsList.appendChild(sessionDiv);
    });
}

async function loadConversation(sessionId) {
    try {
        const response = await fetch(`/api/conversation/${sessionId}`);
        if (!response.ok) return;

        const data = await response.json();
        currentSessionId = sessionId;

        clearChatMessages();

        data.messages.forEach(msg => {
            addMessageToUI(msg.role, msg.content);
        });

        updateSessionList();
    } catch (error) {
        console.error('Error loading conversation:', error);
    }
}

async function deleteSession(sessionId) {
    if (!confirm('Delete this conversation?')) return;

    try {
        const response = await fetch(`/api/conversation/${sessionId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            if (currentSessionId === sessionId) {
                startNewChat();
            }
            await loadSessions();
        }
    } catch (error) {
        console.error('Error deleting session:', error);
    }
}

function clearChatMessages() {
    const messagesContainer = document.getElementById('chat-messages');
    messagesContainer.innerHTML = '';
}

function showWelcomeMessage() {
    const messagesContainer = document.getElementById('chat-messages');
    messagesContainer.innerHTML = `
        <div class="welcome-message">
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
    `;
}

function setLoading(loading) {
    const sendBtn = document.getElementById('send-btn');
    const messageInput = document.getElementById('message-input');
    
    sendBtn.disabled = loading;
    messageInput.disabled = loading;

    if (loading) {
        sendBtn.innerHTML = '<div class="loading"></div>';
    } else {
        sendBtn.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M2 10L18 2L12 18L10 11L2 10Z" fill="currentColor"/>
            </svg>
        `;
    }
}

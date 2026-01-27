// Global state
let currentSessionId = null;
let sessions = [];
let approvalPollInterval = null;

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
    setupEventListeners();
    // Approval polling removed - will only check when write operations are requested
});

async function initializeApp() {
    await loadSessions();
    // Check once on load in case there are pending approvals from previous session
    await checkPendingApprovals();
}

function startApprovalPolling() {
    // Start polling only when a write operation is pending
    if (approvalPollInterval) {
        clearInterval(approvalPollInterval);
    }
    approvalPollInterval = setInterval(checkPendingApprovals, 3000);
}

function stopApprovalPolling() {
    // Stop polling when no approvals are pending
    if (approvalPollInterval) {
        clearInterval(approvalPollInterval);
        approvalPollInterval = null;
    }
}

async function checkPendingApprovals() {
    try {
        const response = await fetch('/api/approvals/pending');
        const data = await response.json();
        
        if (data.pending && data.pending.length > 0) {
            showApprovalNotification(data.pending.length);
            updateApprovalPanel(data.pending);
            // Ensure polling is active when approvals exist
            if (!approvalPollInterval) {
                startApprovalPolling();
            }
        } else {
            hideApprovalNotification();
            // Stop polling when no approvals are pending
            stopApprovalPolling();
        }
    } catch (error) {
        console.error('Error checking approvals:', error);
    }
}

function showApprovalNotification(count) {
    let notification = document.getElementById('approval-notification');
    if (!notification) {
        notification = document.createElement('div');
        notification.id = 'approval-notification';
        notification.className = 'approval-notification';
        notification.innerHTML = `
            <span class="approval-badge">${count}</span>
            <span>Pending Approvals</span>
            <button onclick="toggleApprovalPanel()">Review</button>
        `;
        document.body.appendChild(notification);
    } else {
        notification.querySelector('.approval-badge').textContent = count;
    }
}

function hideApprovalNotification() {
    const notification = document.getElementById('approval-notification');
    if (notification) {
        notification.remove();
    }
}

function toggleApprovalPanel() {
    let panel = document.getElementById('approval-panel');
    if (!panel) {
        panel = document.createElement('div');
        panel.id = 'approval-panel';
        panel.className = 'approval-panel';
        document.body.appendChild(panel);
    }
    panel.classList.toggle('open');
}

function updateApprovalPanel(approvals) {
    let panel = document.getElementById('approval-panel');
    if (!panel) return;
    
    panel.innerHTML = `
        <div class="approval-header">
            <h3>⚠️ Pending Approvals</h3>
            <button onclick="toggleApprovalPanel()">✕</button>
        </div>
        <div class="approval-list">
            ${approvals.map(approval => `
                <div class="approval-item" data-id="${approval.id}">
                    <div class="approval-action">${approval.preview.type || approval.action}</div>
                    <div class="approval-details">
                        ${renderApprovalPreview(approval.preview)}
                    </div>
                    <div class="approval-actions">
                        <button class="approve-btn" onclick="approveAction('${approval.id}', true)">
                            ✓ Approve
                        </button>
                        <button class="reject-btn" onclick="approveAction('${approval.id}', false)">
                            ✕ Reject
                        </button>
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

function renderApprovalPreview(preview) {
    if (preview.type === 'Create Issue') {
        return `
            <div><strong>Project:</strong> ${preview.project}</div>
            <div><strong>Summary:</strong> ${preview.summary}</div>
            <div><strong>Type:</strong> ${preview.issue_type}</div>
        `;
    } else if (preview.type === 'Update Issue') {
        return `
            <div><strong>Issue:</strong> ${preview.issue}</div>
            <div><strong>Changes:</strong> ${JSON.stringify(preview.changes)}</div>
        `;
    } else if (preview.type === 'Change Status') {
        return `
            <div><strong>Issue:</strong> ${preview.issue}</div>
            <div><strong>New Status:</strong> ${preview.new_status}</div>
        `;
    }
    return JSON.stringify(preview);
}

async function approveAction(approvalId, approved) {
    try {
        const response = await fetch(`/api/approvals/approve/${approvalId}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                approval_id: approvalId,
                approved: approved,
                reason: approved ? null : 'User rejected'
            })
        });
        
        const result = await response.json();
        
        // Remove from UI
        document.querySelector(`[data-id="${approvalId}"]`)?.remove();
        
        // Show result message
        if (approved && result.status === 'executed') {
            addSystemMessage(`✅ Action approved and executed: ${JSON.stringify(result.result, null, 2)}`);
        } else {
            addSystemMessage(`❌ Action rejected`);
        }
        
        // Refresh approvals
        await checkPendingApprovals();
        
    } catch (error) {
        console.error('Error approving action:', error);
        alert('Failed to process approval');
    }
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

        // Add assistant message to UI with message_id for feedback
        addMessageToUI('assistant', data.message, data.message_id);

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

function addMessageToUI(role, content, messageId = null) {
    const messagesContainer = document.getElementById('chat-messages');
    
    // Remove welcome message if present
    const welcomeMessage = messagesContainer.querySelector('.welcome-message');
    if (welcomeMessage) {
        welcomeMessage.remove();
    }

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    if (messageId) {
        messageDiv.dataset.messageId = messageId;
    }

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
    
    // Add feedback buttons for assistant messages
    if (role === 'assistant' && messageId) {
        const feedbackDiv = document.createElement('div');
        feedbackDiv.className = 'message-feedback';
        feedbackDiv.innerHTML = `
            <button class="feedback-btn thumbs-up" onclick="submitFeedback(${messageId}, 1)" title="Helpful">
                👍
            </button>
            <button class="feedback-btn thumbs-down" onclick="submitFeedback(${messageId}, -1)" title="Not helpful">
                👎
            </button>
        `;
        contentDiv.appendChild(feedbackDiv);
    }
    
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);

    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Submit feedback to the backend
async function submitFeedback(messageId, feedbackValue) {
    try {
        const response = await fetch('/api/feedback/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                session_id: currentSessionId,
                message_id: messageId,
                feedback_value: feedbackValue
            })
        });

        if (!response.ok) {
            throw new Error('Failed to submit feedback');
        }

        // Visual feedback
        const messageDiv = document.querySelector(`[data-message-id="${messageId}"]`);
        if (messageDiv) {
            const feedbackDiv = messageDiv.querySelector('.message-feedback');
            if (feedbackDiv) {
                feedbackDiv.innerHTML = `
                    <span class="feedback-submitted">
                        Thanks for your feedback! ${feedbackValue > 0 ? '👍' : '👎'}
                    </span>
                `;
            }
        }

        console.log('Feedback submitted successfully');
    } catch (error) {
        console.error('Error submitting feedback:', error);
    }
}

function formatMessage(content) {
    // Use marked.js for full markdown rendering (tables, lists, headers, etc.)
    if (typeof marked !== 'undefined') {
        // Configure marked for better rendering
        marked.setOptions({
            breaks: true,  // Support line breaks
            gfm: true,     // GitHub Flavored Markdown (tables, strikethrough, etc.)
            headerIds: false,
            mangle: false
        });
        return marked.parse(content);
    }
    
    // Fallback for basic formatting if marked.js isn't loaded
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
        console.log('Loaded sessions:', sessions);
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

    sessions.forEach((session, index) => {
        const sessionDiv = document.createElement('div');
        sessionDiv.className = 'session-item';
        if (session.session_id === currentSessionId) {
            sessionDiv.classList.add('active');
        }

        const header = document.createElement('div');
        header.className = 'session-item-header';

        const title = document.createElement('div');
        title.className = 'session-title';
        title.textContent = session.title || `Chat ${sessions.length - index}`;

        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'delete-session';
        deleteBtn.textContent = '×';
        deleteBtn.onclick = (e) => {
            e.stopPropagation();
            deleteSession(session.session_id);
        };

        header.appendChild(title);
        header.appendChild(deleteBtn);
        sessionDiv.appendChild(header);

        sessionDiv.onclick = () => loadConversation(session.session_id);
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

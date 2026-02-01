import { useState, useEffect } from 'react';
import axios from 'axios';
import './Approvals.css';

interface ApprovalRequest {
  id: string;
  action: string;
  parameters: Record<string, any>;
  preview: {
    summary?: string;
    description?: string;
    changes?: Record<string, any>;
  };
  created_at: string;
}

export function Approvals() {
  const [pending, setPending] = useState<ApprovalRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadPendingApprovals();
    // Poll every 3 seconds
    const interval = setInterval(loadPendingApprovals, 3000);
    return () => clearInterval(interval);
  }, []);

  async function loadPendingApprovals() {
    try {
      const response = await axios.get('/api/approvals/pending');
      setPending(response.data.pending || []);
      setError(null);
    } catch (err) {
      console.error('Error loading approvals:', err);
      setError('Failed to load pending approvals');
    } finally {
      setLoading(false);
    }
  }

  async function handleApprove(approvalId: string, approved: boolean) {
    try {
      await axios.post(`/api/approvals/approve/${approvalId}`, {
        approval_id: approvalId,
        approved,
        reason: approved ? 'Approved by user' : 'Rejected by user',
      });
      await loadPendingApprovals();
    } catch (err) {
      console.error('Error processing approval:', err);
      alert('Failed to process approval');
    }
  }

  if (loading) {
    return (
      <div className="approvals-page">
        <div className="approvals-header">
          <h1>🔐 Approval Queue</h1>
          <p>Loading pending requests...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="approvals-page">
      <div className="approvals-header">
        <h1>🔐 Approval Queue</h1>
        <p>Review and approve AI agent write operations</p>
      </div>

      {error && (
        <div className="error-message">
          {error}
        </div>
      )}

      {pending.length === 0 ? (
        <div className="empty-state">
          <p>✅ No pending approvals</p>
          <p className="empty-desc">
            When the AI agent wants to create, update, or delete Jira issues, they will appear here for your approval.
          </p>
        </div>
      ) : (
        <div className="approvals-list">
          {pending.map((request) => (
            <div key={request.id} className="approval-card">
              <div className="approval-header">
                <span className="approval-action">{request.action}</span>
                <span className="approval-time">
                  {new Date(request.created_at).toLocaleString()}
                </span>
              </div>

              <div className="approval-preview">
                {request.preview.summary && (
                  <div className="preview-field">
                    <strong>Summary:</strong> {request.preview.summary}
                  </div>
                )}
                {request.preview.description && (
                  <div className="preview-field">
                    <strong>Description:</strong>
                    <pre>{request.preview.description}</pre>
                  </div>
                )}
                {request.preview.changes && (
                  <div className="preview-field">
                    <strong>Changes:</strong>
                    <pre>{JSON.stringify(request.preview.changes, null, 2)}</pre>
                  </div>
                )}
              </div>

              <div className="approval-parameters">
                <details>
                  <summary>View Parameters</summary>
                  <pre>{JSON.stringify(request.parameters, null, 2)}</pre>
                </details>
              </div>

              <div className="approval-actions">
                <button
                  className="btn-reject"
                  onClick={() => handleApprove(request.id, false)}
                >
                  ❌ Reject
                </button>
                <button
                  className="btn-approve"
                  onClick={() => handleApprove(request.id, true)}
                >
                  ✅ Approve
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

import { useState, useEffect, useCallback } from 'react';
import api from '@/lib/api';

export interface Proposal {
  id: string;
  type: string;
  status: string;
  agent_type: string;
  confidence: number;
  proposal_data: any;
  viewed_at?: string;
  decided_at?: string;
  executed_at?: string;
  created_at: string;
  origin_execution_id?: string;
  waiting_for_mobile_auth?: boolean;
  mobile_auth_status?: string;
  chat_history?: {
    role: string;
    content: string;
    timestamp: string;
  }[];
}

export function useInbox(merchantId: string) {
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [pendingCount, setPendingCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProposals = useCallback(async () => {
    try {
      const response = await api.get(`/inbox?merchant_id=${merchantId}`);
      setProposals(response.data.items);
      setPendingCount(response.data.pending_count);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch proposals');
    } finally {
      setLoading(false);
    }
  }, [merchantId]);

  // Initial fetch
  useEffect(() => {
    fetchProposals();
  }, [fetchProposals]);

  // SSE Real-time Updates (The "Alive" Feed)
  useEffect(() => {
    if (!merchantId) return;

    const streamUrl = `${api.defaults.baseURL}/inbox/stream?merchant_id=${merchantId}`;
    const eventSource = new EventSource(streamUrl);

    eventSource.onmessage = (event) => {
      // General message handler (if we don't use named events)
      console.log('SSE Message:', event.data);
    };

    // Listen for 'update' events from the backend
    eventSource.addEventListener('update', (event) => {
      const data = JSON.parse(event.data);
      console.log('📬 Inbox Update Received:', data);
      
      // Refresh the list when anything changes
      fetchProposals();
      
      // We could also play a subtle notification sound here for the "Premium" feel
      if (data.action === 'created') {
        const audio = new Audio('/sounds/notification.mp3');
        audio.play().catch(() => {}); // Browser might block auto-play
      }
    });

    eventSource.onerror = (err) => {
      console.error('SSE Error:', err);
      eventSource.close();
      
      // Attempt reconnection after 5 seconds
      setTimeout(() => {
        // This will trigger a re-run of this effect
        setLoading(prev => prev); 
      }, 5000);
    };

    return () => {
      eventSource.close();
    };
  }, [merchantId, fetchProposals]);

  const approve = async (id: string) => {
    setProposals(prev => prev.map(p => p.id === id ? { ...p, status: 'approved' } : p));
    try {
      await api.post(`/inbox/${id}/approve?merchant_id=${merchantId}`);
      // No need to fetchProposals here, the SSE 'update' event will trigger it!
    } catch (err: any) {
      setError(err.message || 'Approval failed');
      await fetchProposals(); 
    }
  };

  const reject = async (id: string, reason?: string) => {
    setProposals(prev => prev.map(p => p.id === id ? { ...p, status: 'rejected' } : p));
    try {
      await api.post(`/inbox/${id}/reject?merchant_id=${merchantId}${reason ? `&reason=${reason}` : ''}`);
    } catch (err: any) {
      setError(err.message || 'Rejection failed');
      await fetchProposals();
    }
  };



  const removeSKU = async (id: string, sku: string) => {
    try {
      await api.patch(`/inbox/${id}/items?merchant_id=${merchantId}&sku=${sku}`);
      await fetchProposals();
    } catch (err: any) {
      setError(err.message || 'Failed to remove SKU');
    }
  };

  const chat = async (id: string, message: string) => {
    // Optimistic update (optional, but let's wait for loading state in UI)
    try {
      await api.post(`/inbox/${id}/chat?merchant_id=${merchantId}`, { message });
      // SSE will trigger update, or we can fetch
      await fetchProposals();
    } catch (err: any) {
      setError(err.message || 'Failed to send message');
      throw err;
    }
  };

  return {
    proposals,
    pending_count: pendingCount,
    loading,
    error,
    approve,
    reject,
    removeSKU,
    chat,
    refresh: fetchProposals
  };
}

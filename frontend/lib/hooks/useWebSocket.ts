import { useEffect, useRef, useState, useCallback } from 'react';

export interface WebSocketMessage {
  type: 'agent_thought' | 'inbox_update' | 'campaign_update' | 'inventory_update' | 'stats_update';
  data: any;
  timestamp: string;
}

export function useWebSocket(merchantId: string | null) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 5;

  const connect = useCallback(() => {
    if (!merchantId) return;
    
    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close();
    }

    const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const wsUrl = baseUrl.replace(/^http/, 'ws') + `/api/ws/${merchantId}`;
    
    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setError(null);
        reconnectAttemptsRef.current = 0;
        
        // Subscribe to all update channels
        ws.send(JSON.stringify({
          action: 'subscribe',
          channels: ['agent_activity', 'inbox', 'campaigns', 'inventory', 'stats']
        }));
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as WebSocketMessage;
          setLastMessage(message);
        } catch (err) {
          console.error('WebSocket message parse error:', err);
        }
      };

      ws.onerror = (err) => {
        console.error('WebSocket error:', err);
        setError('WebSocket connection error');
        setIsConnected(false);
      };

      ws.onclose = () => {
        setIsConnected(false);
        
        // Attempt reconnection with exponential backoff
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
          reconnectAttemptsRef.current++;
          
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        }
      };
    } catch (err) {
      setError('Failed to create WebSocket connection');
      setIsConnected(false);
    }
  }, [merchantId]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  const sendMessage = useCallback((message: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
      return true;
    }
    return false;
  }, []);

  return {
    isConnected,
    lastMessage,
    error,
    sendMessage,
    reconnect: connect,
  };
}

// Specialized hook for agent activity updates
export function useAgentActivityStream(merchantId: string | null) {
  const { lastMessage, isConnected } = useWebSocket(merchantId);
  const [activities, setActivities] = useState<any[]>([]);

  useEffect(() => {
    if (lastMessage?.type === 'agent_thought' || lastMessage?.type === 'stats_update') {
      setActivities(prev => [lastMessage.data, ...prev].slice(0, 20));
    }
  }, [lastMessage]);

  return {
    activities,
    isConnected,
    latestActivity: activities[0] || null,
  };
}

// Hook for real-time inbox updates
export function useInboxStream(merchantId: string | null, onUpdate?: (data: any) => void) {
  const { lastMessage, isConnected } = useWebSocket(merchantId);

  useEffect(() => {
    if (lastMessage?.type === 'inbox_update' && onUpdate) {
      onUpdate(lastMessage.data);
    }
  }, [lastMessage, onUpdate]);

  return {
    isConnected,
    lastInboxUpdate: lastMessage?.type === 'inbox_update' ? lastMessage.data : null,
  };
}

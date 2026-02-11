import { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  suggestions?: AIProductSuggestion[];
  campaign_idea?: AICampaignIdea;
}

export interface AIProductSuggestion {
  product_id: string;
  name: string;
  reason: string;
  confidence: number;
  current_price: number;
  suggested_price?: number;
  image_url?: string;
}

export interface AICampaignIdea {
  title: string;
  description: string;
  target_segment: string;
  discount_percentage: number;
  expected_lift: number;
  confidence: number;
}

export interface ChatSession {
  id: string;
  messages: ChatMessage[];
  created_at: string;
  updated_at: string;
}

// Fetch chat history
const fetchChatHistory = async (merchantId: string, sessionId?: string): Promise<ChatSession> => {
  const { data, error } = await apiClient.GET('/api/agents/chat/history', {
    params: { 
      query: { 
        merchant_id: merchantId,
        ...(sessionId && { session_id: sessionId })
      } 
    },
  });
  if (error) throw new Error(JSON.stringify(error));
  return data as ChatSession;
};

// Send chat message
const sendChatMessage = async (
  merchantId: string, 
  message: string, 
  sessionId?: string
): Promise<ChatMessage> => {
  const { data, error } = await apiClient.POST('/api/agents/chat', {
    body: {
      merchant_id: merchantId,
      message,
      ...(sessionId && { session_id: sessionId }),
    },
  });
  if (error) throw new Error(JSON.stringify(error));
  return data as ChatMessage;
};

// React Query Hooks
export function useChatHistory(merchantId: string, sessionId?: string) {
  return useQuery({
    queryKey: ['chat', 'history', merchantId, sessionId],
    queryFn: () => fetchChatHistory(merchantId, sessionId),
    enabled: !!merchantId,
    staleTime: 60000,
  });
}

export function useSendMessage() {
  const queryClient = useQueryClient();
  const [isThinking, setIsThinking] = useState(false);

  const mutation = useMutation({
    mutationFn: async ({
      merchantId,
      message,
      sessionId,
    }: {
      merchantId: string;
      message: string;
      sessionId?: string;
    }) => {
      setIsThinking(true);
      try {
        const response = await sendChatMessage(merchantId, message, sessionId);
        return response;
      } finally {
        setIsThinking(false);
      }
    },
    onSuccess: (data, variables) => {
      // Invalidate and refetch chat history
      queryClient.invalidateQueries({
        queryKey: ['chat', 'history', variables.merchantId, variables.sessionId],
      });
    },
  });

  return {
    ...mutation,
    isThinking,
  };
}

// Hook for managing chat state
export function useAIChat(merchantId: string) {
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [localMessages, setLocalMessages] = useState<ChatMessage[]>([]);
  const { data: history, isLoading: isHistoryLoading } = useChatHistory(merchantId, sessionId);
  const { mutateAsync: sendMessage, isPending: isSending, isThinking } = useSendMessage();

  // Sync local messages with history
  if (history?.messages && localMessages.length === 0) {
    setLocalMessages(history.messages);
  }

  const addUserMessage = useCallback(async (content: string) => {
    const userMessage: ChatMessage = {
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    };

    setLocalMessages((prev) => [...prev, userMessage]);

    try {
      const response = await sendMessage({ merchantId, message: content, sessionId });
      
      // Update session ID if returned
      if ('session_id' in response && response.session_id) {
        setSessionId(response.session_id as string);
      }

      setLocalMessages((prev) => [...prev, response]);
      return response;
    } catch (error) {
      // Remove the user message on error
      setLocalMessages((prev) => prev.slice(0, -1));
      throw error;
    }
  }, [merchantId, sessionId, sendMessage]);

  const clearChat = useCallback(() => {
    setLocalMessages([]);
    setSessionId(undefined);
  }, []);

  return {
    messages: localMessages,
    isLoading: isHistoryLoading || isSending,
    isThinking,
    sendMessage: addUserMessage,
    clearChat,
    sessionId,
  };
}

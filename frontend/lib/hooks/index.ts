// Dashboard hooks
export {
  useDashboardStats,
  useRevenueData,
  useInventoryHealth,
  useCampaignPerformance,
  useAgentActivity,
  usePredictiveInsights,
  useRefreshDashboard,
  type DashboardStats,
  type RevenueDataPoint,
  type InventoryHealthData,
  type CampaignPerformance,
  type AgentActivity,
  type PredictiveInsights,
} from './useDashboard';

// WebSocket hooks
export {
  useWebSocket,
  useAgentActivityStream,
  useInboxStream,
  type WebSocketMessage,
} from './useWebSocket';

// Toast hooks
export {
  useToast,
  type ToastType,
  type Toast,
} from './useToast';

// AI Chat hooks
export {
  useAIChat,
  useChatHistory,
  useSendMessage,
  type ChatMessage,
  type AIProductSuggestion,
  type AICampaignIdea,
  type ChatSession,
} from './useAIChat';

// Re-export existing hooks
export { useInbox, type Proposal } from './useInbox';

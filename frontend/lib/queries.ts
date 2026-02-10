import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from './api';
import { useAuth } from './context/MerchantContext';

// --- Types ---
export interface InboxItem {
  id: string;
  merchant_id: string;
  status: 'pending' | 'approved' | 'rejected' | 'executed' | 'failed';
  task_type: string;
  proposal_data: any;
  urgency_score: number;
  created_at: string;
}

export interface Product {
    id: string;
    title: string;
    velocity_score: number;
    is_dead_stock: boolean;
    images?: string[];
}

export interface DashboardSummary {
  merchant_name: string;
  metrics: {
    recovered_revenue: number;
    roi_multiplier: number;
    stagnant_inventory_count: number;
    stagnant_inventory_value: number;
    pending_proposals: number;
  };
  daily_summary: string;
}

export interface Thought {
  id: string;
  agent_type: string;
  thought_type: string;
  summary: string;
  detailed_reasoning?: Record<string, any>;
  execution_id?: string;
  confidence_score: number;
  step_number: number;
  created_at: string;
}

export interface Campaign {
  id: string;
  name: string;
  type: string;
  status: 'active' | 'paused' | 'completed' | 'draft';
  revenue: number;
  emails_sent: number;
  sms_sent: number;
  conversions: number;
  created_at: string;
}

export interface CampaignListResponse {
  campaigns: Campaign[];
  total: number;
  active_count: number;
  total_revenue: number;
  total_spend: number;
}

// --- Hooks ---

/**
 * Fetch campaigns for the authenticated merchant.
 * No need to pass merchant_id - extracted from JWT on backend.
 */
export const useCampaigns = (status?: string) => {
  const { isAuthenticated } = useAuth();
  
  return useQuery({
    queryKey: ['campaigns', status],
    queryFn: async () => {
      const { data } = await api.get('/campaigns', { 
        params: { status } 
      });
      return data as CampaignListResponse;
    },
    enabled: isAuthenticated,
  });
};

/**
 * Pause or resume a campaign.
 */
export const useCampaignAction = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ id, action }: { id: string; action: 'pause' | 'resume' }) => {
      const { data } = await api.post(`/campaigns/${id}/${action}`);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
    },
  });
};

/**
 * Fetch inbox items for the authenticated merchant.
 */
export const useInbox = () => {
  const { isAuthenticated } = useAuth();
  
  return useQuery({
    queryKey: ['inbox'],
    queryFn: async () => {
      const { data } = await api.get('/inbox');
      return (data.items || []) as InboxItem[];
    },
    enabled: isAuthenticated,
    refetchInterval: 10000,
  });
};

/**
 * Approve or reject an inbox item.
 */
export const useChangeStatus = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ id, action }: { id: string; action: 'approve' | 'reject' }) => {
      const endpoint = action === 'approve' ? `/inbox/${id}/approve` : `/inbox/${id}/reject`;
      const { data } = await api.post(endpoint);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inbox'] });
    },
  });
};

/**
 * Fetch products for the authenticated merchant.
 */
export const useProducts = (options: { is_dead_stock?: boolean, severity?: string } = {}) => {
  const { isAuthenticated } = useAuth();
  
  return useQuery({
    queryKey: ['products', options],
    queryFn: async () => {
      const { data } = await api.get('/products', { 
        params: { 
          is_dead_stock: options.is_dead_stock,
          severity: options.severity
        } 
      });
      return data.products as Product[];
    },
    enabled: isAuthenticated,
  });
};

/**
 * Fetch dead stock summary for the authenticated merchant.
 */
export const useDeadStockSummary = () => {
  const { isAuthenticated } = useAuth();
  
  return useQuery({
    queryKey: ['dead-stock-summary'],
    queryFn: async () => {
      const { data } = await api.get('/products/dead-stock-summary');
      return data;
    },
    enabled: isAuthenticated,
  });
};

/**
 * Fetch dashboard summary for the authenticated merchant.
 * Note: API path changed from /merchants/{id}/dashboard/summary to /merchants/me/dashboard/summary
 */
export const useDashboardSummary = () => {
  const { isAuthenticated } = useAuth();
  
  return useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: async () => {
      const { data } = await api.get('/merchants/me/dashboard/summary');
      return data as DashboardSummary;
    },
    enabled: isAuthenticated,
  });
};

/**
 * Fetch agent thoughts for the authenticated merchant.
 */
export const useThoughts = () => {
  const { isAuthenticated } = useAuth();
  
  return useQuery({
    queryKey: ['thoughts'],
    queryFn: async () => {
      const { data } = await api.get('/thoughts');
      return (data || []) as Thought[];
    },
    enabled: isAuthenticated,
    refetchInterval: 5000,
  });
};

/**
 * Fetch specific thoughts for a forensic execution chain.
 */
export const useThoughtsByExecution = (executionId?: string) => {
  const { isAuthenticated } = useAuth();
  
  return useQuery({
    queryKey: ['thoughts', executionId],
    queryFn: async () => {
      const { data } = await api.get('/thoughts', {
        params: { execution_id: executionId }
      });
      return (data || []) as Thought[];
    },
    enabled: isAuthenticated && !!executionId,
  });
};



// =============================================================================
// BACKWARD COMPATIBILITY WRAPPERS
// These allow old code using merchantId parameter to still work
// =============================================================================

export const useCampaignsCompat = (merchantId: string, status?: string) => {
  return useCampaigns(status);
};

export const useInboxCompat = (merchantId: string) => {
  return useInbox();
};

export const useProductsCompat = (merchantId: string, options: { is_dead_stock?: boolean, severity?: string } = {}) => {
  return useProducts(options);
};

export const useDeadStockSummaryCompat = (merchantId: string) => {
  return useDeadStockSummary();
};

export const useDashboardSummaryCompat = (merchantId: string) => {
  return useDashboardSummary();
};

export const useThoughtsCompat = (merchantId: string) => {
  return useThoughts();
};

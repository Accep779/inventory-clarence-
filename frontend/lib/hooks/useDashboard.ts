import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

// Types
export interface DashboardStats {
  recovered_revenue: number;
  recovered_revenue_change: number;
  inventory_velocity: number;
  inventory_velocity_change: number;
  stagnant_stock: number;
  stagnant_stock_change: number;
  active_campaigns: number;
  pending_approvals: number;
}

export interface RevenueDataPoint {
  name: string;
  value: number;
  forecast?: number;
}

export interface InventoryHealthData {
  moving: number;
  slow: number;
  dead: number;
}

export interface CampaignPerformance {
  name: string;
  value: number;
  roi: number;
}

export interface AgentActivity {
  id: string;
  agent: string;
  action: string;
  timestamp: string;
  icon?: string;
  color?: string;
}

export interface PredictiveInsights {
  forecast_revenue_30d: number;
  confidence: number;
  at_risk_inventory: {
    product_id: string;
    name: string;
    confidence: number;
    days_to_stockout: number;
    recommended_price: number;
    price_probability: number;
  }[];
  trend_direction: 'up' | 'down' | 'stable';
  trend_percentage: number;
}

// API functions
const fetchDashboardStats = async (merchantId: string): Promise<DashboardStats> => {
  const { data, error } = await apiClient.GET('/api/dashboard/stats', {
    params: { query: { merchant_id: merchantId } },
  });
  if (error) throw new Error(JSON.stringify(error));
  return data as DashboardStats;
};

const fetchRevenueData = async (merchantId: string): Promise<RevenueDataPoint[]> => {
  const { data, error } = await apiClient.GET('/api/dashboard/revenue-history', {
    params: { query: { merchant_id: merchantId, months: 7 } },
  });
  if (error) throw new Error(JSON.stringify(error));
  return data as RevenueDataPoint[];
};

const fetchInventoryHealth = async (merchantId: string): Promise<InventoryHealthData> => {
  const { data, error } = await apiClient.GET('/api/products/inventory-health', {
    params: { query: { merchant_id: merchantId } },
  });
  if (error) throw new Error(JSON.stringify(error));
  return data as InventoryHealthData;
};

const fetchCampaignPerformance = async (merchantId: string): Promise<CampaignPerformance[]> => {
  const { data, error } = await apiClient.GET('/api/campaigns/performance', {
    params: { query: { merchant_id: merchantId } },
  });
  if (error) throw new Error(JSON.stringify(error));
  return data as CampaignPerformance[];
};

const fetchAgentActivity = async (merchantId: string): Promise<AgentActivity[]> => {
  const { data, error } = await apiClient.GET('/api/agent-activity', {
    params: { query: { merchant_id: merchantId, limit: 10 } },
  });
  if (error) throw new Error(JSON.stringify(error));
  return data as AgentActivity[];
};

const fetchPredictiveInsights = async (merchantId: string): Promise<PredictiveInsights> => {
  const { data, error } = await apiClient.GET('/api/insights/predictive', {
    params: { query: { merchant_id: merchantId, days: 30 } },
  });
  if (error) throw new Error(JSON.stringify(error));
  return data as PredictiveInsights;
};

// React Query Hooks
export function useDashboardStats(merchantId: string) {
  return useQuery({
    queryKey: ['dashboard', 'stats', merchantId],
    queryFn: () => fetchDashboardStats(merchantId),
    enabled: !!merchantId,
    staleTime: 30000, // 30 seconds
    refetchInterval: 60000, // Refresh every minute
  });
}

export function useRevenueData(merchantId: string) {
  return useQuery({
    queryKey: ['dashboard', 'revenue', merchantId],
    queryFn: () => fetchRevenueData(merchantId),
    enabled: !!merchantId,
    staleTime: 60000,
  });
}

export function useInventoryHealth(merchantId: string) {
  return useQuery({
    queryKey: ['dashboard', 'inventory-health', merchantId],
    queryFn: () => fetchInventoryHealth(merchantId),
    enabled: !!merchantId,
    staleTime: 60000,
  });
}

export function useCampaignPerformance(merchantId: string) {
  return useQuery({
    queryKey: ['dashboard', 'campaigns', merchantId],
    queryFn: () => fetchCampaignPerformance(merchantId),
    enabled: !!merchantId,
    staleTime: 60000,
  });
}

export function useAgentActivity(merchantId: string) {
  return useQuery({
    queryKey: ['dashboard', 'agent-activity', merchantId],
    queryFn: () => fetchAgentActivity(merchantId),
    enabled: !!merchantId,
    staleTime: 30000,
    refetchInterval: 30000, // Refresh every 30 seconds for real-time feel
  });
}

export function usePredictiveInsights(merchantId: string) {
  return useQuery({
    queryKey: ['dashboard', 'insights', merchantId],
    queryFn: () => fetchPredictiveInsights(merchantId),
    enabled: !!merchantId,
    staleTime: 300000, // 5 minutes
  });
}

// Refresh mutation for manual refresh
export function useRefreshDashboard() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (merchantId: string) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['dashboard', 'stats', merchantId] }),
        queryClient.invalidateQueries({ queryKey: ['dashboard', 'revenue', merchantId] }),
        queryClient.invalidateQueries({ queryKey: ['dashboard', 'inventory-health', merchantId] }),
        queryClient.invalidateQueries({ queryKey: ['dashboard', 'campaigns', merchantId] }),
        queryClient.invalidateQueries({ queryKey: ['dashboard', 'agent-activity', merchantId] }),
        queryClient.invalidateQueries({ queryKey: ['dashboard', 'insights', merchantId] }),
      ]);
      return true;
    },
  });
}

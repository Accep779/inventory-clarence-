import React, { useState, useEffect } from 'react';
import Head from 'next/head';
import { motion } from 'framer-motion';
import { useQueryClient } from '@tanstack/react-query';
import {
  TrendingUp,
  TrendingDown,
  DollarSign,
  Package,
  Zap,
  Users,
  Target,
  ArrowRight,
  Sparkles,
  Activity,
  BarChart3,
  ShoppingBag,
  RefreshCw,
  Bot,
  Brain,
  MessageSquare,
  PieChart,
} from 'lucide-react';

// UI Components
import { StatCard, MiniStatCard } from '@/components/ui/stat-card';
import { ChartCard } from '@/components/ui/chart';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';
import { ToastContainer } from '@/components/ui/Toast';
import { useToast } from '@/lib/hooks/useToast';
import { DashboardSkeleton, ActivityItemSkeleton } from '@/components/ui/SkeletonLoader';

// Dashboard Components
import { InboxWidget } from '@/components/dashboard/InboxWidget';
import { AIChatDrawer } from '@/components/dashboard/AIChatDrawer';
import { InsightsPanel } from '@/components/dashboard/InsightsPanel';

// Hooks
import { 
  useDashboardStats, 
  useRevenueData, 
  useInventoryHealth, 
  useCampaignPerformance, 
  useAgentActivity,
  useRefreshDashboard,
  AgentActivity,
  RevenueDataPoint,
} from '@/lib/hooks/useDashboard';
import { useInbox } from '@/lib/hooks/useInbox';
import { useWebSocket } from '@/lib/hooks/useWebSocket';

// Get merchant ID from localStorage or use demo
const getMerchantId = () => {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('cephly_merchant_id') || 'demo_merchant';
  }
  return 'demo_merchant';
};

// Color palette for charts
const defaultColors = [
  'hsl(260, 60%, 55%)',
  'hsl(270, 70%, 45%)',
  'hsl(220, 90%, 60%)',
  'hsl(180, 70%, 45%)',
  'hsl(320, 70%, 50%)',
];

export default function DashboardPage() {
  const [merchantId, setMerchantId] = useState('demo_merchant');
  const [isChatOpen, setIsChatOpen] = useState(false);
  const { toasts, success, error: showError, removeToast } = useToast();
  const queryClient = useQueryClient();

  // Initialize merchant ID on client side
  useEffect(() => {
    setMerchantId(getMerchantId());
  }, []);

  // Fetch real data
  const { 
    data: stats, 
    isLoading: statsLoading, 
    error: statsError,
    refetch: refetchStats 
  } = useDashboardStats(merchantId);
  
  const { 
    data: revenueData, 
    isLoading: revenueLoading,
    refetch: refetchRevenue 
  } = useRevenueData(merchantId);
  
  const { 
    data: inventoryHealth, 
    isLoading: inventoryLoading,
    refetch: refetchInventory 
  } = useInventoryHealth(merchantId);
  
  const { 
    data: campaignData, 
    isLoading: campaignLoading,
    refetch: refetchCampaigns 
  } = useCampaignPerformance(merchantId);
  
  const { 
    data: agentActivities, 
    isLoading: activityLoading,
    refetch: refetchActivity 
  } = useAgentActivity(merchantId);

  // Inbox data
  const { 
    proposals, 
    pending_count: pendingCount,
    loading: inboxLoading, 
    approve, 
    reject,
    refresh: refreshInbox,
  } = useInbox(merchantId);

  // WebSocket for real-time updates
  const { isConnected, lastMessage } = useWebSocket(merchantId);

  // Handle WebSocket messages
  useEffect(() => {
    if (lastMessage) {
      switch (lastMessage.type) {
        case 'stats_update':
          queryClient.invalidateQueries({ queryKey: ['dashboard', 'stats', merchantId] });
          break;
        case 'inbox_update':
          refreshInbox();
          break;
        case 'agent_thought':
          queryClient.invalidateQueries({ queryKey: ['dashboard', 'agent-activity', merchantId] });
          break;
      }
    }
  }, [lastMessage, merchantId, queryClient, refreshInbox]);

  // Manual refresh handler
  const handleRefresh = async () => {
    await Promise.all([
      refetchStats(),
      refetchRevenue(),
      refetchInventory(),
      refetchCampaigns(),
      refetchActivity(),
      refreshInbox(),
    ]);
    success('Dashboard refreshed', 'All data has been updated');
  };

  // Handle inbox approval
  const handleApprove = async (id: string) => {
    try {
      await approve(id);
      success('Campaign approved', 'The campaign has been queued for execution');
      // Refresh stats after approval
      setTimeout(() => refetchStats(), 500);
    } catch (err) {
      showError('Approval failed', 'Please try again');
    }
  };

  // Handle inbox rejection
  const handleReject = async (id: string) => {
    try {
      await reject(id);
      success('Campaign rejected', 'The proposal has been dismissed');
    } catch (err) {
      showError('Rejection failed', 'Please try again');
    }
  };

  const isLoading = statsLoading || revenueLoading || inventoryLoading || campaignLoading;

  // Handle errors
  if (statsError) {
    return (
      <ErrorBoundary>
        <div className="min-h-screen bg-[hsl(var(--bg-primary))] flex items-center justify-center">
          <div className="text-center p-8">
            <AlertCircle className="w-16 h-16 text-rose-400 mx-auto mb-4" />
            <h2 className="text-xl font-bold text-[hsl(var(--text-primary))] mb-2">
              Failed to load dashboard
            </h2>
            <p className="text-[hsl(var(--text-secondary))] mb-4">
              There was an error loading your dashboard data.
            </p>
            <button 
              onClick={handleRefresh}
              className="btn-primary flex items-center gap-2 mx-auto"
            >
              <RefreshCw className="w-4 h-4" />
              Try Again
            </button>
          </div>
        </div>
      </ErrorBoundary>
    );
  }

  return (
    <>
      <Head>
        <title>Dashboard | Cephly</title>
      </Head>

      <div className="min-h-screen bg-[hsl(var(--bg-primary))]">
        {/* Top Navigation Bar */}
        <header className="sticky top-0 z-40 bg-[hsl(var(--bg-primary)/0.8)] backdrop-blur-xl border-b border-[hsl(var(--border-subtle))]">
          <div className="max-w-[1600px] mx-auto px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-8">
                {/* Logo */}
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[hsl(var(--accent-primary))] to-[hsl(var(--accent-secondary))] flex items-center justify-center">
                    <Bot className="w-5 h-5 text-white" />
                  </div>
                  <span className="text-xl font-bold text-gradient">Cephly</span>
                </div>

                {/* Nav Links */}
                <nav className="hidden md:flex items-center gap-1">
                  <a href="/" className="nav-item active">
                    <BarChart3 className="w-4 h-4" />
                    Dashboard
                  </a>
                  <a href="/inventory" className="nav-item">
                    <ShoppingBag className="w-4 h-4" />
                    Inventory
                  </a>
                  <a href="/campaigns" className="nav-item">
                    <Target className="w-4 h-4" />
                    Campaigns
                  </a>
                  <a href="/customers" className="nav-item">
                    <Users className="w-4 h-4" />
                    Customers
                  </a>
                </nav>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-3">
                {/* WebSocket connection indicator */}
                <div className={`hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium ${
                  isConnected 
                    ? 'bg-emerald-400/10 text-emerald-400' 
                    : 'bg-amber-400/10 text-amber-400'
                }`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-emerald-400' : 'bg-amber-400'} animate-pulse`} />
                  {isConnected ? 'Live' : 'Connecting...'}
                </div>

                <button
                  onClick={handleRefresh}
                  disabled={statsLoading}
                  className={`btn-secondary ${statsLoading ? 'animate-pulse' : ''}`}
                >
                  <RefreshCw className={`w-4 h-4 ${statsLoading ? 'animate-spin' : ''}`} />
                  <span className="hidden sm:inline">Refresh</span>
                </button>

                <button 
                  onClick={() => setIsChatOpen(true)}
                  className="btn-secondary flex items-center gap-2"
                >
                  <MessageSquare className="w-4 h-4" />
                  <span className="hidden sm:inline">Ask AI</span>
                </button>

                <button className="btn-primary flex items-center gap-2">
                  <Sparkles className="w-4 h-4" />
                  New Campaign
                </button>
              </div>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="max-w-[1600px] mx-auto px-6 py-8">
          <ErrorBoundary>
            {/* Welcome Section */}
            <div className="mb-8">
              <div className="flex items-center gap-3 mb-2">
                <Brain className="w-6 h-6 text-[hsl(var(--accent-primary))]" />
                <h1 className="text-2xl font-bold text-[hsl(var(--text-primary))]">
                  Good morning, Alpha Store
                </h1>
              </div>
              <p className="text-[hsl(var(--text-secondary))]">
                Your AI agents have been working overnight. Here&apos;s what&apos;s happening with your inventory.
              </p>
            </div>

            {isLoading ? (
              <DashboardSkeleton />
            ) : (
              <>
                {/* Stats Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                  <StatCard
                    title="Recovered Revenue"
                    value={stats ? `$${stats.recovered_revenue.toLocaleString()}` : '$0'}
                    change={stats ? `${stats.recovered_revenue_change >= 0 ? '+' : ''}${stats.recovered_revenue_change}%` : '+0%'}
                    changeType={stats && stats.recovered_revenue_change >= 0 ? 'positive' : 'negative'}
                    icon={DollarSign}
                    iconColor="hsl(260, 60%, 55%)"
                    variant="elevated"
                  />
                  <StatCard
                    title="Inventory Velocity"
                    value={stats?.inventory_velocity?.toFixed(1) || '0.0x'}
                    change={stats ? `${stats.inventory_velocity_change >= 0 ? '+' : ''}${stats.inventory_velocity_change}` : '+0'}
                    changeType={stats && stats.inventory_velocity_change >= 0 ? 'positive' : 'negative'}
                    icon={TrendingUp}
                    iconColor="hsl(150, 70%, 40%)"
                    variant="elevated"
                  />
                  <StatCard
                    title="Stagnant Stock"
                    value={stats ? `${stats.stagnant_stock} Units` : '0 Units'}
                    change={stats ? `${stats.stagnant_stock_change >= 0 ? '+' : ''}${stats.stagnant_stock_change}` : '0'}
                    changeType={stats && stats.stagnant_stock_change <= 0 ? 'positive' : 'negative'}
                    icon={Package}
                    iconColor="hsl(320, 70%, 50%)"
                    variant="elevated"
                  />
                  <StatCard
                    title="Active Campaigns"
                    value={stats?.active_campaigns?.toString() || '0'}
                    subtitle={pendingCount > 0 ? `${pendingCount} pending approval` : 'All approved'}
                    icon={Target}
                    iconColor="hsl(40, 90%, 50%)"
                    variant="elevated"
                  />
                </div>

                {/* Two Column Layout - Main Content + Sidebar */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
                  {/* Main Content - Left Column (2/3) */}
                  <div className="lg:col-span-2 space-y-6">
                    {/* Revenue Chart */}
                    <ChartCard
                      title="Revenue Recovery"
                      subtitle="Monthly revenue from clearance campaigns with forecasting"
                      action={
                        <select className="input-modern text-sm py-1.5">
                          <option>Last 7 months</option>
                          <option>Last 12 months</option>
                          <option>This year</option>
                        </select>
                      }
                    >
                      {revenueData && <AreaChartWithForecast data={revenueData} />}
                    </ChartCard>

                    {/* Secondary Charts */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <ChartCard
                        title="Campaign Performance"
                        subtitle="Revenue by campaign type"
                      >
                        {campaignData && <BarChartWidget data={campaignData} />}
                      </ChartCard>

                      <ChartCard
                        title="Inventory Health"
                        subtitle="Distribution by velocity"
                      >
                        {inventoryHealth && (
                          <div className="space-y-3">
                            {[
                              { name: 'Moving', value: inventoryHealth.moving, color: defaultColors[0] },
                              { name: 'Slow', value: inventoryHealth.slow, color: defaultColors[3] },
                              { name: 'Dead', value: inventoryHealth.dead, color: defaultColors[4] },
                            ].map((item) => (
                              <div key={item.name} className="flex items-center gap-3">
                                <div 
                                  className="w-3 h-3 rounded-full shrink-0"
                                  style={{ backgroundColor: item.color }}
                                />
                                <span className="text-sm text-[hsl(var(--text-secondary))] flex-1">
                                  {item.name}
                                </span>
                                <div className="flex items-center gap-2 flex-1">
                                  <div className="flex-1 h-2 bg-[hsl(var(--bg-tertiary))] rounded-full overflow-hidden">
                                    <motion.div
                                      initial={{ width: 0 }}
                                      animate={{ width: `${item.value}%` }}
                                      transition={{ duration: 1, delay: 0.2 }}
                                      className="h-full rounded-full"
                                      style={{ backgroundColor: item.color }}
                                    />
                                  </div>
                                  <span className="text-sm font-medium text-[hsl(var(--text-primary))] w-10 text-right">
                                    {item.value}%
                                  </span>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </ChartCard>
                    </div>

                    {/* Recent Activity */}
                    <div className="bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-default))] rounded-xl p-6">
                      <div className="flex items-center justify-between mb-6">
                        <div>
                          <h3 className="text-lg font-semibold text-[hsl(var(--text-primary))]">
                            Recent Agent Activity
                          </h3>
                          <p className="text-sm text-[hsl(var(--text-tertiary))]">
                            Real-time actions taken by your AI agents
                          </p>
                        </div>
                        <button className="text-sm text-[hsl(var(--accent-primary))] hover:underline">
                          View all
                        </button>
                      </div>

                      <div className="space-y-3">
                        {activityLoading ? (
                          <>
                            <ActivityItemSkeleton />
                            <ActivityItemSkeleton />
                            <ActivityItemSkeleton />
                            <ActivityItemSkeleton />
                          </>
                        ) : agentActivities && agentActivities.length > 0 ? (
                          agentActivities.slice(0, 4).map((activity: AgentActivity, i: number) => (
                            <ActivityItem key={activity.id} activity={activity} index={i} />
                          ))
                        ) : (
                          <div className="text-center py-8">
                            <p className="text-sm text-[hsl(var(--text-secondary))]">
                              No recent activity
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Sidebar - Right Column (1/3) */}
                  <div className="space-y-6">
                    {/* AI Predictive Insights */}
                    <InsightsPanel merchantId={merchantId} />

                    {/* Pending Approvals Widget */}
                    <InboxWidget
                      proposals={proposals}
                      isLoading={inboxLoading}
                      onApprove={handleApprove}
                      onReject={handleReject}
                      onViewAll={() => window.location.href = '/inbox'}
                    />
                  </div>
                </div>
              </>
            )}
          </ErrorBoundary>
        </main>
      </div>

      {/* AI Chat Drawer */}
      <AIChatDrawer
        merchantId={merchantId}
        isOpen={isChatOpen}
        onClose={() => setIsChatOpen(false)}
      />

      {/* Toast Notifications */}
      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </>
  );
}

// Activity Item Component
function ActivityItem({ activity, index }: { activity: AgentActivity; index: number }) {
  const agentIcons: Record<string, React.ElementType> = {
    Observer: Activity,
    Strategy: Sparkles,
    Matchmaker: Users,
    Execution: Zap,
    default: Bot,
  };
  
  const agentColors: Record<string, string> = {
    Observer: 'hsl(260, 60%, 55%)',
    Strategy: 'hsl(40, 90%, 50%)',
    Matchmaker: 'hsl(150, 70%, 40%)',
    Execution: 'hsl(320, 70%, 50%)',
    default: 'hsl(200, 60%, 50%)',
  };

  const Icon = agentIcons[activity.agent] || agentIcons.default;
  const color = agentColors[activity.agent] || agentColors.default;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.1 }}
      className="flex items-start gap-4 p-4 rounded-lg bg-[hsl(var(--bg-tertiary)/0.5)] border border-[hsl(var(--border-subtle))] hover:border-[hsl(var(--border-default))] transition-colors"
    >
      <div
        className="p-2 rounded-lg shrink-0"
        style={{ backgroundColor: `${color}20` }}
      >
        <Icon className="w-4 h-4" style={{ color }} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-medium text-[hsl(var(--text-primary))]">
            {activity.agent}
          </span>
          <span className="text-[hsl(var(--text-tertiary))]">•</span>
          <span className="text-xs text-[hsl(var(--text-tertiary))]">
            {new Date(activity.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
        <p className="text-sm text-[hsl(var(--text-secondary))] line-clamp-2">
          {activity.action}
        </p>
      </div>
    </motion.div>
  );
}

// Re-export chart components with custom styling
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

function AreaChartWithForecast({ data }: { data: RevenueDataPoint[] }) {
  return (
    <div className="h-[280px]">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="hsl(260, 60%, 55%)" stopOpacity={0.3}/>
              <stop offset="95%" stopColor="hsl(260, 60%, 55%)" stopOpacity={0}/>
            </linearGradient>
            <linearGradient id="colorForecast" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="hsl(40, 90%, 50%)" stopOpacity={0.3}/>
              <stop offset="95%" stopColor="hsl(40, 90%, 50%)" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border-subtle))" />
          <XAxis 
            dataKey="name" 
            stroke="hsl(var(--text-tertiary))"
            fontSize={12}
            tickLine={false}
            axisLine={false}
          />
          <YAxis 
            stroke="hsl(var(--text-tertiary))"
            fontSize={12}
            tickLine={false}
            axisLine={false}
            tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'hsl(var(--bg-secondary))',
              border: '1px solid hsl(var(--border-default))',
              borderRadius: '8px',
              fontSize: '12px',
            }}
            formatter={(value: number) => [`$${value.toLocaleString()}`, 'Revenue']}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke="hsl(260, 60%, 55%)"
            strokeWidth={2}
            fillOpacity={1}
            fill="url(#colorRevenue)"
          />
          {data.some(d => d.forecast !== undefined) && (
            <Area
              type="monotone"
              dataKey="forecast"
              stroke="hsl(40, 90%, 50%)"
              strokeDasharray="5 5"
              strokeWidth={2}
              fillOpacity={1}
              fill="url(#colorForecast)"
            />
          )}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

import { BarChart, Bar, XAxis as BarXAxis, YAxis as BarYAxis, CartesianGrid as BarCartesianGrid, Tooltip as BarTooltip, ResponsiveContainer as BarResponsiveContainer } from 'recharts';

function BarChartWidget({ data }: { data: any[] }) {
  return (
    <div className="h-[250px]">
      <BarResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <BarCartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border-subtle))" vertical={false} />
          <BarXAxis 
            dataKey="name" 
            stroke="hsl(var(--text-tertiary))"
            fontSize={11}
            tickLine={false}
            axisLine={false}
          />
          <BarYAxis 
            stroke="hsl(var(--text-tertiary))"
            fontSize={12}
            tickLine={false}
            axisLine={false}
            tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
          />
          <BarTooltip
            contentStyle={{
              backgroundColor: 'hsl(var(--bg-secondary))',
              border: '1px solid hsl(var(--border-default))',
              borderRadius: '8px',
              fontSize: '12px',
            }}
            formatter={(value: number) => [`$${value.toLocaleString()}`, 'Revenue']}
          />
          <Bar 
            dataKey="value" 
            fill="hsl(260, 60%, 55%)" 
            radius={[4, 4, 0, 0]}
          />
        </BarChart>
      </BarResponsiveContainer>
    </div>
  );
}

// Import AlertCircle for error state
import { AlertCircle } from 'lucide-react';

// Add CSS for text gradient
const textGradientStyles = `
  .text-gradient {
    background: linear-gradient(135deg, hsl(var(--accent-primary)) 0%, hsl(var(--accent-secondary)) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
`;

import React from 'react';
import Head from 'next/head';
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
} from 'lucide-react';
import { StatCard, MiniStatCard } from '@/components/ui/stat-card';
import {
  AreaChartWidget,
  BarChartWidget,
  PieChartWidget,
  ChartCard,
} from '@/components/ui/chart';

// Mock data for charts
const revenueData = [
  { name: 'Jan', value: 12000 },
  { name: 'Feb', value: 19000 },
  { name: 'Mar', value: 15000 },
  { name: 'Apr', value: 25000 },
  { name: 'May', value: 22000 },
  { name: 'Jun', value: 32000 },
  { name: 'Jul', value: 38000 },
];

const inventoryData = [
  { name: 'Moving', value: 65 },
  { name: 'Slow', value: 25 },
  { name: 'Dead', value: 10 },
];

const campaignData = [
  { name: 'Flash Sale', value: 4500 },
  { name: 'Bundle Deal', value: 3200 },
  { name: 'Email Blast', value: 2800 },
  { name: 'SMS Campaign', value: 1500 },
];

const rfmData = [
  { name: 'Champions', value: 120 },
  { name: 'Loyal', value: 280 },
  { name: 'Potential', value: 450 },
  { name: 'At Risk', value: 180 },
  { name: 'Lost', value: 95 },
];

export default function DashboardPage() {
  const [isLoading, setIsLoading] = React.useState(false);

  const handleRefresh = () => {
    setIsLoading(true);
    setTimeout(() => setIsLoading(false), 1000);
  };

  return (
    <>
      <Head>
        <title>Dashboard | Cephly</title>
      </Head>

      <div className="min-h-screen bg-[hsl(var(--bg-primary))]">
        {/* Top Navigation Bar */}
        <header className="sticky top-0 z-50 bg-[hsl(var(--bg-primary)/0.8)] backdrop-blur-xl border-b border-[hsl(var(--border-subtle))]">
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
                  <a href="#" className="nav-item active">
                    <BarChart3 className="w-4 h-4" />
                    Dashboard
                  </a>
                  <a href="#" className="nav-item">
                    <ShoppingBag className="w-4 h-4" />
                    Inventory
                  </a>
                  <a href="#" className="nav-item">
                    <Target className="w-4 h-4" />
                    Campaigns
                  </a>
                  <a href="#" className="nav-item">
                    <Users className="w-4 h-4" />
                    Customers
                  </a>
                </nav>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-3">
                <button
                  onClick={handleRefresh}
                  className={`btn-secondary ${isLoading ? 'animate-pulse' : ''}`}
                >
                  <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
                  <span className="hidden sm:inline">Refresh</span>
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

          {/* AI Insights Banner */}
          <div className="mb-8 p-4 rounded-xl border border-[hsl(var(--accent-primary)/0.3)] bg-gradient-to-r from-[hsl(var(--accent-primary)/0.1)] to-transparent">
            <div className="flex items-start gap-4">
              <div className="p-2 rounded-lg bg-[hsl(var(--accent-primary)/0.2)]">
                <Sparkles className="w-5 h-5 text-[hsl(var(--accent-primary))]" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-[hsl(var(--text-primary))] mb-1">
                  AI Insight: 3 high-value dead stock items detected
                </h3>
                <p className="text-sm text-[hsl(var(--text-secondary))] mb-3">
                  The Observer Agent found $12,450 in stuck inventory. The Strategy Agent recommends a flash sale campaign to recover value within 7 days.
                </p>
                <div className="flex gap-3">
                  <button className="btn-primary text-sm px-4 py-2">
                    Review Proposal
                    <ArrowRight className="w-4 h-4 inline ml-1" />
                  </button>
                  <button className="btn-secondary text-sm px-4 py-2">
                    Dismiss
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <StatCard
              title="Recovered Revenue"
              value="$128,402"
              change="+12.4%"
              changeType="positive"
              icon={DollarSign}
              iconColor="hsl(260, 60%, 55%)"
              variant="elevated"
            />
            <StatCard
              title="Inventory Velocity"
              value="4.8x"
              change="+0.6"
              changeType="positive"
              icon={TrendingUp}
              iconColor="hsl(150, 70%, 40%)"
              variant="elevated"
            />
            <StatCard
              title="Stagnant Stock"
              value="312 Units"
              change="-45"
              changeType="positive"
              icon={Package}
              iconColor="hsl(320, 70%, 50%)"
              variant="elevated"
            />
            <StatCard
              title="Active Campaigns"
              value="7"
              subtitle="3 pending approval"
              icon={Target}
              iconColor="hsl(40, 90%, 50%)"
              variant="elevated"
            />
          </div>

          {/* Charts Section */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
            {/* Revenue Chart */}
            <div className="lg:col-span-2">
              <ChartCard
                title="Revenue Recovery"
                subtitle="Monthly revenue from clearance campaigns"
                action={
                  <select className="input-modern text-sm py-1.5">
                    <option>Last 7 months</option>
                    <option>Last 12 months</option>
                    <option>This year</option>
                  </select>
                }
              >
                <AreaChartWidget
                  data={revenueData}
                  dataKey="value"
                  xAxisKey="name"
                  height={280}
                />
              </ChartCard>
            </div>

            {/* Inventory Distribution */}
            <ChartCard
              title="Inventory Health"
              subtitle="Distribution by velocity"
            >
              <PieChartWidget
                data={inventoryData}
                dataKey="value"
                nameKey="name"
                height={200}
              />
              <div className="mt-4 space-y-2">
                {inventoryData.map((item, i) => (
                  <div key={item.name} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-3 h-3 rounded-full"
                        style={{ backgroundColor: defaultColors[i] }}
                      />
                      <span className="text-[hsl(var(--text-secondary))]">{item.name}</span>
                    </div>
                    <span className="font-medium text-[hsl(var(--text-primary))]">{item.value}%</span>
                  </div>
                ))}
              </div>
            </ChartCard>
          </div>

          {/* Secondary Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            <ChartCard
              title="Campaign Performance"
              subtitle="Revenue by campaign type"
            >
              <BarChartWidget
                data={campaignData}
                dataKey="value"
                xAxisKey="name"
                height={250}
              />
            </ChartCard>

            <ChartCard
              title="Customer Segments"
              subtitle="RFM distribution"
            >
              <BarChartWidget
                data={rfmData}
                dataKey="value"
                xAxisKey="name"
                height={250}
              />
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
                  Actions taken by your AI agents
                </p>
              </div>
              <button className="text-sm text-[hsl(var(--accent-primary))] hover:underline">
                View all
              </button>
            </div>

            <div className="space-y-4">
              {[
                {
                  agent: 'Observer',
                  action: 'Scanned 1,247 products and identified 23 dead stock items',
                  time: '2 hours ago',
                  icon: Activity,
                  color: 'hsl(260, 60%, 55%)',
                },
                {
                  agent: 'Strategy',
                  action: 'Generated flash sale proposal for "Summer Collection"',
                  time: '4 hours ago',
                  icon: Sparkles,
                  color: 'hsl(40, 90%, 50%)',
                },
                {
                  agent: 'Matchmaker',
                  action: 'Updated RFM segments for 847 customers',
                  time: '6 hours ago',
                  icon: Users,
                  color: 'hsl(150, 70%, 40%)',
                },
                {
                  agent: 'Execution',
                  action: 'Deployed email campaign to 320 at-risk customers',
                  time: '8 hours ago',
                  icon: Zap,
                  color: 'hsl(320, 70%, 50%)',
                },
              ].map((activity, i) => (
                <div
                  key={i}
                  className="flex items-start gap-4 p-4 rounded-lg bg-[hsl(var(--bg-tertiary)/0.5)] border border-[hsl(var(--border-subtle))] hover:border-[hsl(var(--border-default))] transition-colors"
                >
                  <div
                    className="p-2 rounded-lg"
                    style={{ backgroundColor: `${activity.color}20` }}
                  >
                    <activity.icon className="w-4 h-4" style={{ color: activity.color }} />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-[hsl(var(--text-primary))]">
                        {activity.agent}
                      </span>
                      <span className="text-[hsl(var(--text-tertiary))]">•</span>
                      <span className="text-sm text-[hsl(var(--text-tertiary))]">{activity.time}</span>
                    </div>
                    <p className="text-sm text-[hsl(var(--text-secondary))]">{activity.action}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </main>
      </div>
    </>
  );
}

const defaultColors = [
  'hsl(260, 60%, 55%)',
  'hsl(270, 70%, 45%)',
  'hsl(220, 90%, 60%)',
  'hsl(180, 70%, 45%)',
  'hsl(320, 70%, 50%)',
];

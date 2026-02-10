import React from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { 
  BarChart3, 
  TrendingUp, 
  PieChart, 
  Activity, 
  Calendar,
  Download,
  Filter,
  ArrowUpRight,
  ArrowDownRight,
  Zap,
  MousePointer2,
  DollarSign
} from 'lucide-react';

import api from '@/lib/api';
import { useAuth } from '@/lib/context/MerchantContext';

export default function AnalyticsPage() {
  const { merchantId } = useAuth();
  const [data, setData] = React.useState<any>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    if (!merchantId) return;
    
    const fetchStats = async () => {
      try {
        const response = await api.get(`/analytics/stats?merchant_id=${merchantId}`);
        setData(response.data);
      } catch (err) {
        console.error('Failed to fetch analytics:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
    // Refresh every 5 minutes
    const interval = setInterval(fetchStats, 300000);
    return () => clearInterval(interval);
  }, [merchantId]);

  if (loading) return <AppShell title="Loading..."><div className="p-20 text-center font-mono animate-pulse">Scanning Ledger...</div></AppShell>;

  return (
    <AppShell title="System Analytics">
       <div className="flex flex-col gap-8">
          {/* HEADER */}
          <div className="flex justify-between items-end">
             <div>
                <h1 className="text-4xl font-extrabold tracking-tight text-white mb-2">System Analytics</h1>
                <p className="text-slate-400 font-medium tracking-tight">Full-spectrum performance attribution and <span className="text-white italic">Neural Forecasting</span>.</p>
             </div>
             {/* ... filters ... */}
          </div>

          {/* MAIN STATS */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
             <MetricCard 
                label="Total Revenue Recovery" 
                value={`$${data?.total_recovered_revenue?.toLocaleString()}`} 
                change="+14.2%" 
                trend="up" 
                icon={DollarSign} 
             />
             <MetricCard 
                label="Agent ROI Multiplier" 
                value={`${data?.roi_multiplier}x`} 
                change="+2.1%" 
                trend="up" 
                icon={Zap} 
             />
             <MetricCard 
                label="Agent Contribution" 
                value={data?.agent_contribution || "92.4%"} 
                change="+0.4%" 
                trend="up" 
                icon={Activity} 
             />
          </div>

          {/* CHART GRID */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
             <ChartWrapper title="Revenue Recovery over Time" icon={Activity}>
                <div className="w-full h-80 bg-gradient-to-t from-indigo-500/5 to-transparent rounded-2xl border border-dashed border-slate-800 flex items-center justify-center text-slate-400 font-mono text-xs p-8 text-center">
                   {/* In a real app, we'd map data.history to a LineChart */}
                   <div className="flex items-end gap-1 h-32">
                     {data?.history?.map((h: any, i: number) => (
                       <div key={i} className="w-8 bg-indigo-500/40 rounded-t-sm" style={{ height: `${(h.revenue / 4000) * 100}%` }} />
                     ))}
                   </div>
                </div>
             </ChartWrapper>
             <ChartWrapper title="Neural Conv. Rate" icon={PieChart}>
                <div className="w-full h-80 bg-gradient-to-t from-purple-500/5 to-transparent rounded-2xl border border-dashed border-slate-800 flex flex-col items-center justify-center">
                   <p className="text-4xl font-black text-white">{data?.metrics?.conversion_rate}%</p>
                   <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mt-2">Conversion across channels</p>
                </div>
             </ChartWrapper>
          </div>
       </div>
    </AppShell>
  );
}

function MetricCard({ label, value, change, trend, icon: Icon }: any) {
  return (
    <div className="bg-slate-900/40 backdrop-blur-xl border border-slate-800/60 p-8 rounded-[32px] group hover:border-slate-700 transition-all transition-duration-300">
       <div className="flex justify-between items-start mb-6">
          <div className="p-4 rounded-2xl bg-slate-800 border border-slate-700/50 group-hover:border-slate-600 transition-colors">
             <Icon className="w-6 h-6 text-slate-300" />
          </div>
          <div className={`flex items-center gap-1 px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest ${trend === 'up' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-pink-500/10 text-pink-400'}`}>
             {trend === 'up' ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
             {change}
          </div>
       </div>
       <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">{label}</p>
       <p className="text-3xl font-black text-white">{value}</p>
    </div>
  );
}

function ChartWrapper({ title, icon: Icon, children }: any) {
  return (
    <div className="bg-slate-900/40 backdrop-blur-xl border border-slate-800/60 rounded-[32px] p-8">
       <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
             <div className="p-2.5 rounded-xl bg-slate-800 border border-slate-700/50 flex items-center justify-center">
                <Icon className="w-5 h-5 text-slate-400" />
             </div>
             <h3 className="text-lg font-bold text-white tracking-tight">{title}</h3>
          </div>
          <button className="p-2 rounded-lg hover:bg-slate-800 text-slate-500 hover:text-white transition-all">
             <Download className="w-4 h-4" />
          </button>
       </div>
       {children}
    </div>
  );
}

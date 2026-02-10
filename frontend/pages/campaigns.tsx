import React from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { 
  Megaphone, 
  Plus, 
  Play, 
  Pause, 
  BarChart, 
  Users, 
  MousePointer2, 
  DollarSign,
  Calendar,
  MoreHorizontal,
  ChevronRight,
  Sparkles,
  RefreshCw
} from 'lucide-react';
import api from '@/lib/api';
import { useAuth } from '@/lib/context/MerchantContext';


// Mock data for UI development/preview
const mockCampaigns = [
  {
    id: 1,
    name: "Summer Clearance Wave 1",
    status: "Active",
    type: "Email + SMS", 
    roi: "14.2x",
    revenue: "$124,500",
    reach: "125k"
  },
  {
    id: 2,
    name: "VIP Early Access",
    status: "Completed", 
    type: "Email Only",
    roi: "18.5x",
    revenue: "$98,200", 
    reach: "45k"
  }
];


export default function CampaignCenter() {
  const { merchantId } = useAuth();
  const [campaigns, setCampaigns] = React.useState<any[]>([]);
  const [stats, setStats] = React.useState<any>(null);
  const [loading, setLoading] = React.useState(true);

  const fetchCampaignData = async () => {
    try {
      const res = await api.get('/campaigns');
      setCampaigns(res.data.campaigns);
      setStats({
        total_revenue: res.data.total_revenue,
        active_count: res.data.active_count,
        total_spend: res.data.total_spend
      });
    } catch (err) {
      console.error('Failed to fetch campaigns:', err);
    } finally {
      setLoading(false);
    }
  };

  React.useEffect(() => {
    if (merchantId) {
      fetchCampaignData();
    }
  }, [merchantId]);
  return (
    <AppShell title="Campaign Center">
       <div className="flex flex-col gap-8">
          {/* HEADER */}
          <div className="flex justify-between items-end">
             <div>
                <h1 className="text-4xl font-extrabold tracking-tight mb-2 text-white">Campaign Command Center</h1>
                <p className="text-slate-400 font-medium tracking-tight">AI-orchestrated marketing execution for <span className="text-white">78-figure precision</span>.</p>
             </div>
             <div className="flex gap-3">
                <button className="px-5 py-3 bg-slate-800/50 hover:bg-slate-800 rounded-xl border border-slate-700/50 text-[10px] font-black uppercase tracking-widest transition-all flex items-center gap-2">
                   <RefreshCw className="w-4 h-4 text-slate-500" /> Refresh Intelligence
                </button>
                <button className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 rounded-xl shadow-lg shadow-indigo-600/20 text-[10px] font-black uppercase tracking-widest transition-all flex items-center gap-2 text-white">
                   <Plus className="w-4 h-4" /> Create Intelligence Wave
                </button>
             </div>
          </div>

          {/* PERFORMANCE SNAPSHOT */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
             <CampaignKPI label="Total Attributed Sales" value="$842,500" change="+18.2%" icon={DollarSign} />
             <CampaignKPI label="Total Conversions" value="12,410" change="+5.4%" icon={Users} />
             <CampaignKPI label="Avg. Click-Through" value="3.82%" change="+0.8%" icon={MousePointer2} />
             <CampaignKPI label="Campaign ROI" value="12.4x" change="+1.2x" icon={BarChart} />
          </div>

          {/* ACTIVE CAMPAIGNS GRID */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-4">
             {loading ? (
                <div className="col-span-2 text-center py-20 text-slate-500 font-mono">Loading Neural Intelligence...</div>
             ) : campaigns.length === 0 ? (
                <div className="col-span-2 text-center py-20 text-slate-500 font-mono">No active campaigns found. Initializing...</div>
             ) : (
             campaigns.map((c) => (
               <div key={c.id} className="bg-slate-900/40 backdrop-blur-xl border border-slate-800/60 rounded-[32px] p-8 group hover:border-indigo-500/30 transition-all shadow-xl relative overflow-hidden">
                  <div className={`absolute top-0 right-0 w-48 h-48 bg-gradient-to-br transition-opacity opacity-5 -mr-24 -mt-24 group-hover:opacity-10 ${c.status === 'active' ? 'from-emerald-500 to-transparent' : 'from-slate-500 to-transparent'}`} />
                  
                  <div className="flex justify-between items-start mb-6">
                     <div className="flex items-center gap-3">
                        <div className={`w-3 h-3 rounded-full ${c.status === 'active' ? 'bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]' : 'bg-slate-700'}`} />
                        <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">{c.status} Layer</span>
                     </div>
                     <button className="p-2 rounded-xl bg-slate-800/50 border border-slate-700/50 text-slate-400 group-hover:text-white transition-colors">
                        <MoreHorizontal className="w-5 h-5" />
                     </button>
                  </div>

                  <div className="mb-8">
                     <h3 className="text-2xl font-black mb-1 group-hover:text-indigo-400 transition-colors tracking-tight">{c.name}</h3>
                     <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">{c.type}</p>
                  </div>

                  <div className="grid grid-cols-3 gap-4 mb-8">
                     <div>
                        <p className="text-[10px] font-bold text-slate-600 uppercase tracking-widest mb-1">ROI</p>
                        <p className="text-lg font-black text-white">{c.revenue > 0 ? (c.revenue / (c.revenue * 0.15 || 1)).toFixed(1) + 'x' : '0.0x'}</p>
                     </div>
                     <div>
                        <p className="text-[10px] font-bold text-slate-600 uppercase tracking-widest mb-1">Attribution</p>
                        <p className="text-lg font-black text-white">${c.revenue.toLocaleString()}</p>
                     </div>
                     <div>
                        <p className="text-[10px] font-bold text-slate-600 uppercase tracking-widest mb-1">Reach</p>
                        <p className="text-lg font-black text-white">{((c.emails_sent || 0) + (c.sms_sent || 0)).toLocaleString()}</p>
                     </div>
                  </div>

                  <div className="flex gap-2">
                     <button className="flex-1 py-3 bg-slate-800/50 hover:bg-slate-800 border border-slate-700/50 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all flex items-center justify-center gap-2 group/btn">
                        {c.status === 'active' ? <Pause className="w-3.5 h-3.5 group-hover/btn:text-pink-500 transition-colors" /> : <Play className="w-3.5 h-3.5 group-hover/btn:text-emerald-500 transition-colors" />}
                        {c.status === 'active' ? 'Halt Wave' : 'Propagate'}
                     </button>
                     <button className="px-5 py-3 bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/20 rounded-xl text-[10px] font-black uppercase tracking-widest text-indigo-400 flex items-center gap-2 transition-all group/btn2">
                        Analytics <ChevronRight className="w-3.5 h-3.5 transform group-hover/btn2:translate-x-1 transition-transform" />
                     </button>
                  </div>
               </div>
             )))}

             {/* CREATE NEW CARD */}
             <div className="bg-slate-900/10 border-2 border-dashed border-slate-800/50 rounded-[32px] p-8 flex flex-col items-center justify-center gap-4 hover:border-indigo-500/40 hover:bg-slate-900/20 transition-all group cursor-pointer min-h-[300px]">
                <div className="w-16 h-16 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center group-hover:scale-110 transition-transform shadow-xl">
                   <Megaphone className="w-8 h-8 text-slate-500 group-hover:text-indigo-400" />
                </div>
                <div className="text-center">
                   <p className="text-lg font-black text-slate-400 tracking-tight group-hover:text-white transition-colors">Start New Intelligence Wave</p>
                   <p className="text-[10px] font-bold text-slate-600 uppercase tracking-widest mt-1">Multi-channel autonomous execution</p>
                </div>
             </div>
          </div>
       </div>
    </AppShell>
  );
}

function CampaignKPI({ label, value, change, icon: Icon }: any) {
  return (
    <div className="bg-slate-900/40 backdrop-blur-xl border border-slate-800/60 p-6 rounded-[24px]">
       <div className="flex justify-between items-start mb-4">
          <Icon className="w-5 h-5 text-slate-500" />
          <span className="text-[10px] font-black text-emerald-400 tracking-wide">{change}</span>
       </div>
       <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">{label}</p>
       <p className="text-2xl font-black text-white">{value}</p>
    </div>
  );
}

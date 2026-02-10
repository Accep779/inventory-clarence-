import React from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { 
  Users, 
  UserPlus, 
  TrendingUp, 
  Timer,
  Search,
  Filter,
  RefreshCcw,
  Zap,
  Target
} from 'lucide-react';
import api from '@/lib/api';
import { useAuth } from '@/lib/context/MerchantContext';
import ActiveJourneys from '@/components/reactivation/ActiveJourneys';

export default function CRMPage() {
  const [loading, setLoading] = React.useState(true);
  const [journeys, setJourneys] = React.useState([]);

  React.useEffect(() => {
    const fetchCRMData = async () => {
      try {
        const statsRes = await api.get('/crm/stats');
        setStats(statsRes.data);
        
        const journeysRes = await api.get('/crm/journeys');
        setJourneys(journeysRes.data);
      } catch (err) {
        console.error('Failed to fetch CRM data:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchCRMData();
  }, []);

  const [stats, setStats] = React.useState<any>(null);

  return (
    <AppShell title="Customer Relations">
      <div className="flex flex-col gap-8">
        {/* HEADER */}
        <div className="flex justify-between items-end">
          <div>
            <h1 className="text-4xl font-extrabold tracking-tight text-white mb-2">Customer Relations</h1>
            <p className="text-slate-400 font-medium tracking-tight">Systematic retention via <span className="text-white italic">Neural Reactivation</span>.</p>
          </div>
          <div className="flex gap-3">
             <button className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl shadow-lg shadow-indigo-600/20 text-[10px] font-black uppercase tracking-widest transition-all flex items-center gap-2">
                <Target className="w-4 h-4" /> Start Scan
             </button>
          </div>
        </div>

        {/* CRM STATS */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
           <StatCard label="Total Reachable" value={stats?.total_reachable?.toLocaleString() || "..."} icon={Users} trend="+3.2%" />
           <StatCard label="At Risk (Slipping)" value={stats?.at_risk_count?.toLocaleString() || "..."} icon={Timer} trend="-21" color="amber" />
           <StatCard label="Churn Recovered" value={stats?.recovered_count?.toLocaleString() || "..."} icon={Sync} trend="+12.5%" color="emerald" />
           <StatCard label="Neural Lift" value={stats?.neural_lift || "..."} icon={Zap} trend="+0.5%" color="indigo" />
        </div>

        {/* ACTIVE JOURNEYS SECTION */}
        <div className="bg-slate-900/20 border border-slate-800/40 rounded-3xl p-8 backdrop-blur-sm">
           <ActiveJourneys journeys={journeys} />
        </div>
      </div>
    </AppShell>
  );
}

function StatCard({ label, value, icon: Icon, trend, color = 'slate' }: any) {
  const colors: any = {
    indigo: 'from-indigo-500/20 to-indigo-500/5 text-indigo-400 border-indigo-500/20',
    emerald: 'from-emerald-500/20 to-emerald-500/5 text-emerald-400 border-emerald-500/20',
    amber: 'from-amber-500/20 to-amber-500/5 text-amber-400 border-amber-500/20',
    slate: 'from-slate-500/20 to-slate-500/5 text-slate-400 border-slate-800/60'
  };

  return (
    <div className={`bg-gradient-to-br ${colors[color]} border rounded-2xl p-6 relative overflow-hidden group`}>
       <div className="flex justify-between items-start relative z-10">
          <div>
             <p className="text-[10px] font-black opacity-60 uppercase tracking-widest mb-1">{label}</p>
             <h4 className="text-2xl font-black text-white">{value}</h4>
          </div>
          <div className="p-2 rounded-lg bg-black/20">
             <Icon className="w-5 h-5" />
          </div>
       </div>
       <div className="mt-4 flex items-center gap-2 relative z-10">
          <span className="text-[10px] font-black bg-white/10 px-1.5 py-0.5 rounded">{trend}</span>
          <span className="text-[10px] font-bold opacity-40 uppercase tracking-widest">this month</span>
       </div>
    </div>
  );
}

function Sync(props: any) {
  return <RefreshCcw {...props} />;
}

import React from 'react';
import { Shield, Key, Eye, EyeOff, List, History, Lock } from 'lucide-react';

interface SecurityAccessProps {
  data: any;
  onChange: (key: string, value: any) => void;
}

export default function SecurityAccess({ data, onChange }: SecurityAccessProps) {
  const [showKey, setShowKey] = React.useState(false);

  return (
    <div className="space-y-10">
      <div className="flex items-center gap-3">
         <div className="p-2 bg-emerald-500/10 rounded-xl">
            <Shield className="w-5 h-5 text-emerald-400" />
         </div>
         <h2 className="text-2xl font-bold text-white tracking-tight">Security & Access</h2>
      </div>

      {/* API KEYS SECTION */}
      <div className="space-y-6">
         <div className="flex items-center gap-2">
            <Key className="w-3.5 h-3.5 text-slate-500" />
            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Bypass API Key</label>
         </div>
         <div className="flex gap-4">
            <div className="flex-1 relative">
               <input 
                  type={showKey ? 'text' : 'password'}
                  value={data.apiKey || 'test/Pass3d'}
                  readOnly
                  className="w-full bg-[hsl(var(--bg-input))] border border-[hsl(var(--border-panel))] rounded-xl px-5 py-3.5 text-sm text-slate-300 font-mono pr-12"
               />
               <button 
                  onClick={() => setShowKey(!showKey)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-600 hover:text-white transition-colors"
               >
                  {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
               </button>
            </div>
            <button className="px-6 py-3.5 bg-slate-800 border border-slate-700 rounded-xl text-[10px] font-bold uppercase tracking-widest text-slate-400 hover:text-white hover:bg-slate-700 transition-all">
               Rotate Key
            </button>
         </div>
         <div className="p-4 bg-emerald-500/5 border border-emerald-500/10 rounded-2xl flex items-center gap-3">
            <Lock className="w-4 h-4 text-emerald-500/50" />
            <p className="text-[10px] text-emerald-500/70 font-medium leading-relaxed">
               This key is restricted to local development and sandbox operations only.
            </p>
         </div>
      </div>

      {/* ROLE PERMISSIONS MOCK */}
      <div className="space-y-6">
         <div className="flex items-center gap-2">
            <List className="w-3.5 h-3.5 text-slate-500" />
            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Access Permissions</label>
         </div>
         <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[
               { role: 'Administrator', access: 'Full Access', count: 1 },
               { role: 'Agent (System)', access: 'Autonomous API', count: 3 },
               { role: 'Viewer', access: 'Read-only Analytics', count: 4 }
            ].map((r, i) => (
               <div key={i} className="p-4 bg-[hsl(var(--bg-input))] border border-[hsl(var(--border-panel))] rounded-2xl flex justify-between items-center group hover:border-slate-700 transition-colors">
                  <div>
                     <p className="text-xs font-bold text-white mb-0.5">{r.role}</p>
                     <p className="text-[10px] text-slate-500 font-medium">{r.access}</p>
                  </div>
                  <div className="px-2 py-0.5 bg-slate-800 rounded text-[9px] font-black text-slate-500 group-hover:text-slate-300">
                     {r.count} Active
                  </div>
               </div>
            ))}
         </div>
      </div>

      {/* AUDIT LOG PREVIEW */}
      <div className="space-y-6 pt-4">
         <div className="flex items-center gap-2">
            <History className="w-3.5 h-3.5 text-slate-500" />
            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Recent Security Events</label>
         </div>
         <div className="space-y-3">
            {[
               { event: 'API Key Rotation', user: 'Alexander Gray', time: '2h ago', status: 'success' },
               { event: 'Configuration Change: Store DNA', user: 'Alexander Gray', time: '5h ago', status: 'success' },
               { event: 'Unauthorized Access Attempt', user: 'IP 192.168.1.1', time: '1d ago', status: 'failure' }
            ].map((e, i) => (
               <div key={i} className="flex items-center justify-between p-3 border-b border-white/5 last:border-0">
                  <div className="flex items-center gap-4">
                     <div className={`w-1.5 h-1.5 rounded-full ${e.status === 'success' ? 'bg-emerald-500' : 'bg-pink-500 shadow-[0_0_8px_rgba(236,72,153,0.5)]'}`} />
                     <div>
                        <p className="text-[11px] font-bold text-slate-300">{e.event}</p>
                        <p className="text-[9px] text-slate-600 font-medium">By {e.user}</p>
                     </div>
                  </div>
                  <span className="text-[9px] font-bold text-slate-700 uppercase">{e.time}</span>
               </div>
            ))}
         </div>
         <button className="text-[10px] font-black text-slate-600 hover:text-white uppercase tracking-widest flex items-center gap-2 transition-colors">
            View Full Audit Logs <List className="w-3 h-3" />
         </button>
      </div>
    </div>
  );
}

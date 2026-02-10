import React from 'react';
import { 
  Users, 
  RefreshCcw, 
  ArrowRight, 
  CheckCircle2, 
  Clock, 
  Mail, 
  MessageSquare, 
  TrendingUp,
  User
} from 'lucide-react';
import { motion } from 'framer-motion';

interface Journey {
  id: string;
  customer_name: string;
  status: 'active' | 'completed' | 'converted' | 'failed';
  current_touch: number;
  last_touch_at: string;
  next_touch_due_at: string;
  lifetime_value: number;
}

export default function ActiveJourneys({ journeys }: { journeys: Journey[] }) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between mb-2">
        <div>
          <h3 className="text-xl font-bold text-white flex items-center gap-2">
            <RefreshCcw className="w-5 h-5 text-indigo-400" />
            Active Reactivation Missions
          </h3>
          <p className="text-slate-500 text-xs font-medium uppercase tracking-widest mt-1">
            Re-engaging high-value sleepers via Neural Orchestration
          </p>
        </div>
        <div className="px-3 py-1 bg-indigo-500/10 border border-indigo-500/20 rounded-full">
           <span className="text-[10px] font-black text-indigo-400 uppercase tracking-widest">
             {journeys.length} Active
           </span>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4">
        {journeys.map((journey, idx) => (
          <motion.div 
            key={journey.id}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: idx * 0.1 }}
            className="group bg-slate-900/40 border border-slate-800/60 rounded-2xl p-6 hover:bg-slate-900/60 hover:border-indigo-500/30 transition-all cursor-pointer relative overflow-hidden"
          >
            {/* Background Glow */}
            <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/5 blur-[50px] group-hover:bg-indigo-500/10 transition-all" />

            <div className="flex items-center justify-between relative z-10">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-slate-800 border border-slate-700/50 flex items-center justify-center">
                  <User className="w-6 h-6 text-slate-400" />
                </div>
                <div>
                  <h4 className="font-bold text-white group-hover:text-indigo-400 transition-colors">{journey.customer_name}</h4>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-[10px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded font-black uppercase tracking-tighter">
                      LTV: ${journey.lifetime_value.toLocaleString()}
                    </span>
                    <span className="text-[10px] text-slate-500 font-bold uppercase tracking-widest flex items-center gap-1">
                      <Clock className="w-3 h-3" /> Step {journey.current_touch}/3
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-8">
                {/* PROGREESS STEPS */}
                <div className="flex items-center gap-2">
                   {[1, 2, 3].map(step => (
                     <div 
                        key={step} 
                        className={`w-8 h-1 rounded-full transition-all duration-500 ${
                          step < journey.current_touch 
                            ? 'bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.3)]' 
                            : step === journey.current_touch 
                              ? 'bg-indigo-500 animate-pulse' 
                              : 'bg-slate-800'
                        }`} 
                     />
                   ))}
                </div>

                <div className="text-right">
                  <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">Status</p>
                  <span className={`px-2 py-1 rounded text-[10px] font-black uppercase tracking-widest ${
                    journey.status === 'converted' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' :
                    journey.status === 'active' ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20' :
                    'bg-slate-800 text-slate-400'
                  }`}>
                    {journey.status}
                  </span>
                </div>

                <button className="p-2 rounded-lg bg-slate-800/50 border border-slate-700/50 text-slate-400 hover:text-white hover:bg-slate-800 transition-all">
                  <ArrowRight className="w-5 h-5" />
                </button>
              </div>
            </div>
          </motion.div>
        ))}
        
        {journeys.length === 0 && (
          <div className="py-20 text-center border-2 border-dashed border-slate-800/60 rounded-3xl">
            <Users className="w-12 h-12 text-slate-700 mx-auto mb-4" />
            <p className="text-slate-500 font-mono text-sm">No active reactivation journeys in orbit.</p>
          </div>
        )}
      </div>
    </div>
  );
}

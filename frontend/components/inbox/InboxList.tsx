import React from 'react';
import { Proposal } from '@/lib/hooks/useInbox';
import { Zap, Brain, MessageSquare, Clock, Inbox, Smartphone } from 'lucide-react';

interface InboxListProps {
  proposals: Proposal[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function InboxList({ proposals, selectedId, onSelect }: InboxListProps) {
  return (
    <div className="flex-1 overflow-y-auto custom-scrollbar bg-transparent">
      {proposals.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center p-12 text-center opacity-20">
           <Inbox className="w-10 h-10 mx-auto mb-4 text-slate-400" />
           <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400">Inbox Zero</p>
           <p className="text-[9px] text-slate-500 mt-2 font-medium">All proposals have been reviewed.</p>
        </div>
      ) : (
        proposals.map((p) => (
          <div 
            key={p.id}
            onClick={() => onSelect(p.id)}
            className={`relative cursor-pointer p-6 transition-all duration-300 border-b border-white/5 hover:bg-white/[0.02] ${
              selectedId === p.id ? 'bg-white/[0.03]' : ''
            }`}
          >
            {selectedId === p.id && (
              <div className="absolute left-0 top-0 bottom-0 w-[2px] bg-white shadow-[0_0_10px_rgba(255,255,255,0.5)]" />
            )}
            
            <div className="flex justify-between items-start mb-2">
              <span className={`text-[11px] font-bold tracking-tight transition-colors ${
                selectedId === p.id ? 'text-white' : 'text-slate-500 group-hover:text-slate-300'
              }`}>
                {p.proposal_data.title || `${p.type} Strategy`}
              </span>
              <span className="text-[8px] font-bold text-slate-700 uppercase tracking-widest mt-0.5">
                {new Date(p.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>

            <div className="flex items-center gap-2 mb-3">
              <div className={`px-1.5 py-0.5 rounded text-[8px] font-bold uppercase tracking-widest ${
                p.status === 'pending' 
                  ? 'bg-amber-500/5 border border-amber-500/10 text-amber-500/70' 
                  : p.status === 'approved'
                  ? 'bg-emerald-500/5 border border-emerald-500/10 text-emerald-500/70'
                  : 'bg-slate-900 border border-white/5 text-slate-600'
              }`}>
                {p.status}
              </div>
              
              {p.waiting_for_mobile_auth && (
                 <div className="flex items-center gap-1.5 px-1.5 py-0.5 rounded border bg-amber-500/10 border-amber-500/20 text-amber-500 text-[8px] font-bold uppercase tracking-widest animate-pulse">
                   <Smartphone className="w-2.5 h-2.5" />
                   <span>Auth Pending</span>
                 </div>
              )}
              
              <span className="text-[8px] font-bold text-slate-600 uppercase tracking-widest">{p.agent_type} agent</span>
            </div>

            <p className="text-[10px] text-slate-600 line-clamp-2 leading-relaxed font-medium">
              {p.proposal_data.description || "Synthesizing strategy..."}
            </p>
          </div>
        ))
      )}
    </div>
  );
}


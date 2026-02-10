import { Zap, Clock, Smartphone } from 'lucide-react';

interface InboxListRowProps {
  proposal: any;
  selected: boolean;
  onClick: () => void;
}

export function InboxListRow({ proposal, selected, onClick }: InboxListRowProps) {
  return (
    <div 
      onClick={onClick}
      className={`relative cursor-pointer p-6 transition-all duration-300 border-b border-slate-800/40 hover:bg-slate-800/20 ${
        selected ? 'bg-indigo-600/10' : ''
      }`}
    >
      {selected && (
        <div className="absolute left-0 top-0 bottom-0 w-1 bg-indigo-500 shadow-[0_0_15px_rgba(99,102,241,0.8)]" />
      )}
      
      <div className="flex justify-between items-start mb-2">
        <span className={`text-sm font-black tracking-tight transition-colors ${
          selected ? 'text-white' : 'text-slate-400 group-hover:text-slate-200'
        }`}>
          {proposal.title}
        </span>
        <span className="text-[10px] font-bold text-slate-600 uppercase tracking-widest mt-0.5">
          now
        </span>
      </div>

      <div className="flex items-center gap-3 mb-3">
        <div className={`px-2 py-0.5 rounded-md border text-[9px] font-black uppercase tracking-widest ${
          proposal.urgency === 'High' 
            ? 'bg-pink-500/10 border-pink-500/20 text-pink-500' 
            : 'bg-slate-800/40 border-slate-800/60 text-slate-500'
        }`}>
          {proposal.urgency} Urgency
        </div>
        
        {proposal.waiting_for_mobile_auth && (
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-md border bg-amber-500/10 border-amber-500/20 text-amber-500 text-[9px] font-black uppercase tracking-widest animate-pulse">
            <Smartphone className="w-3 h-3" />
            <span>Waiting for Auth</span>
          </div>
        )}

        {proposal.urgency === 'High' && !proposal.waiting_for_mobile_auth && (
          <Zap className="w-3 h-3 text-amber-500" fill="currentColor" />
        )}
      </div>

      <p className="text-xs text-slate-500 line-clamp-2 leading-relaxed font-medium">
        {proposal.description}
      </p>
    </div>
  );
}

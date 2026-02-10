import React from 'react';
import { Proposal } from '@/lib/hooks/useInbox';
import { 
  CheckCircle2, 
  XCircle, 
  TrendingUp, 
  Users, 
  Mail, 
  Smartphone, 
  AlertCircle,
  ArrowRight,
  ShieldCheck,
  BrainCircuit,
  PieChart
} from 'lucide-react';
import { AgentChatPanel } from './AgentChatPanel';



interface StrategyProposalDetailProps {
  proposal: Proposal;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onChat: (id: string, message: string) => Promise<void>;
}

export function StrategyProposalDetail({ proposal, onApprove, onReject, onChat }: StrategyProposalDetailProps) {
  const data = proposal.proposal_data;
  const pricing = data.pricing || {};
  const projections = data.projections || {};
  const copy = data.copy || data.campaign_copy || {};
  
  const isPending = proposal.status === 'pending';

  return (
    <div className="flex-1 flex flex-col bg-black/40 backdrop-blur-3xl overflow-hidden border-l border-white/5">
      {/* Header Section */}
      <div className="p-8 border-b border-white/5 bg-gradient-to-b from-white/[0.02] to-transparent">
        <div className="flex justify-between items-start mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center">
              <BrainCircuit className="w-5 h-5 text-white/50" />
            </div>
            <div>
              <h2 className="text-sm font-bold tracking-tight text-white/90">
                {data.product_title || 'Strategy Proposal'}
              </h2>
              <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mt-1">
                {data.strategy?.replace('_', ' ') || proposal.agent_type} Approach
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <span className="text-[9px] font-bold text-white/40 uppercase tracking-widest">Confidence</span>
            <span className="text-xs font-mono font-bold text-emerald-500">{proposal.confidence || '92'}%</span>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-6">
          <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5">
            <div className="flex items-center gap-2 mb-2 text-slate-500">
              <TrendingUp className="w-3.5 h-3.5" />
              <span className="text-[10px] font-bold uppercase tracking-widest">Revenue</span>
            </div>
            <p className="text-lg font-mono font-bold text-white/90">
              ${projections.revenue?.toLocaleString() || '2,450.00'}
            </p>
          </div>
          <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5">
            <div className="flex items-center gap-2 mb-2 text-slate-500">
              <Users className="w-3.5 h-3.5" />
              <span className="text-[10px] font-bold uppercase tracking-widest">Audience</span>
            </div>
            <p className="text-lg font-mono font-bold text-white/90">
              {data.audience?.total_customers?.toLocaleString() || data.audience_size || '450'}
            </p>
          </div>
          <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5">
            <div className="flex items-center gap-2 mb-2 text-slate-500">
              <PieChart className="w-3.5 h-3.5" />
              <span className="text-[10px] font-bold uppercase tracking-widest">Discount</span>
            </div>
            <p className="text-lg font-mono font-bold text-amber-500">
              {pricing.discount_percent || '30'}%
            </p>
          </div>
        </div>
      </div>

      {/* Content Section */}
      <div className="flex-1 overflow-y-auto p-8 pb-0 custom-scrollbar">
        <div className="grid grid-cols-1 gap-10">
          
          {/* Email Preview Section */}
          <section>
             <div className="flex items-center gap-2 mb-4">
                <Mail className="w-4 h-4 text-slate-500" />
                <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400">Email Live Preview</h3>
             </div>
             
             <div className="rounded-2xl border border-white/10 overflow-hidden shadow-2xl">
                <div className="bg-white/5 p-4 border-b border-white/5">
                   <div className="flex gap-1.5 mb-2">
                      <div className="w-2 h-2 rounded-full bg-red-500/30" />
                      <div className="w-2 h-2 rounded-full bg-amber-500/30" />
                      <div className="w-2 h-2 rounded-full bg-emerald-500/30" />
                   </div>
                   <p className="text-[10px] font-medium text-slate-400">
                      Subject: <span className="text-white/80">{copy.email_subject || 'Exclusive Offer...'}</span>
                   </p>
                </div>
                <div className="bg-white p-8 min-h-[200px] text-slate-800">
                   <div className="max-w-[400px] mx-auto text-center">
                      <div className="w-12 h-12 bg-slate-100 rounded-lg mx-auto mb-6 flex items-center justify-center font-bold text-slate-400 text-xs">LOGO</div>
                      <h1 className="text-xl font-bold mb-4 tracking-tight">
                         {copy.email_subject}
                      </h1>
                      <p className="text-sm leading-relaxed text-slate-500">
                         {copy.email_body || 'Generating brand-aligned content...'}
                      </p>
                      <div className="mt-8 px-6 py-2.5 bg-black text-white text-[10px] font-bold uppercase tracking-widest rounded-full inline-block">
                         Shop Clearance
                      </div>
                   </div>
                </div>
             </div>
          </section>

          {/* SMS Preview Section */}
          <section>
             <div className="flex items-center gap-2 mb-4">
                <Smartphone className="w-4 h-4 text-slate-500" />
                <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400">SMS Preview</h3>
             </div>
             
             <div className="max-w-[300px] rounded-2xl bg-white/5 border border-white/10 p-4 relative">
                <div className="absolute -left-1 top-4 w-2 h-2 bg-white/5 border-l border-b border-white/10 rotate-45" />
                <p className="text-[10px] leading-relaxed text-white/80">
                   {copy.sms_message || 'A limited offer just for you...'}
                </p>
                <p className="text-[8px] mt-2 text-slate-500 font-bold">Just now</p>
             </div>
          </section>

          {/* Reasoning & Constraints */}
          <section className="grid grid-cols-2 gap-6">
             <div className="p-6 rounded-2xl bg-emerald-500/[0.02] border border-emerald-500/10">
                <div className="flex items-center gap-2 mb-3 text-emerald-500">
                   <ShieldCheck className="w-4 h-4" />
                   <h3 className="text-[10px] font-bold uppercase tracking-widest">Safety Compliance</h3>
                </div>
                <ul className="space-y-2">
                   <li className="flex items-center gap-2 text-[9px] text-emerald-500/70 font-medium">
                      <div className="w-1 h-1 rounded-full bg-emerald-500" />
                      Within 5% margin floor
                   </li>
                   <li className="flex items-center gap-2 text-[9px] text-emerald-500/70 font-medium">
                      <div className="w-1 h-1 rounded-full bg-emerald-500" />
                      Confirmed in-stock inventory
                   </li>
                </ul>
             </div>
             <div className="p-6 rounded-2xl bg-blue-500/[0.02] border border-blue-500/10">
                <div className="flex items-center gap-2 mb-3 text-blue-500">
                   <AlertCircle className="w-4 h-4" />
                   <h3 className="text-[10px] font-bold uppercase tracking-widest">Agent Reasoning</h3>
                </div>
                <p className="text-[9px] text-blue-500/70 leading-relaxed font-medium">
                   {data.reasoning || "Predicted high engagement for winter-themed visuals based on current weather patterns and past customer behavior."}
                </p>
             </div>
          </section>
        </div>
      </div>

      {/* Action Section */}
      <AgentChatPanel 
         proposal={proposal} 
         onSendMessage={onChat} 
      />

      <div className="p-8 border-t border-white/5 bg-white/[0.01]">
        <div className="flex gap-4">
          <button 
            disabled={!isPending}
            onClick={() => onReject(proposal.id)}
            className="flex-1 px-6 py-4 rounded-xl border border-white/5 hover:bg-red-500/10 hover:border-red-500/20 text-slate-500 hover:text-red-500 transition-all font-bold text-[10px] uppercase tracking-widest flex items-center justify-center gap-2 disabled:opacity-20 disabled:cursor-not-allowed group"
          >
            <XCircle className="w-4 h-4 transition-transform group-hover:scale-110" />
            Reject Proposal
          </button>
          
          <button 
            disabled={!isPending}
            onClick={() => onApprove(proposal.id)}
            className="flex-[2] px-6 py-4 rounded-xl bg-white text-black hover:bg-slate-200 transition-all font-bold text-[10px] uppercase tracking-widest flex items-center justify-center gap-2 shadow-[0_0_20px_rgba(255,255,255,0.1)] disabled:opacity-20 disabled:cursor-not-allowed group"
          >
            <CheckCircle2 className="w-4 h-4 transition-transform group-hover:scale-110" />
            Authorize Execution
            <ArrowRight className="w-3.5 h-3.5 opacity-40" />
          </button>
        </div>
        {!isPending && (
          <p className="text-center mt-4 text-[9px] text-slate-500 font-bold uppercase tracking-widest flex items-center justify-center gap-1.5">
            <ShieldCheck className="w-3 h-3" />
            Authorized at {new Date(proposal.decided_at || Date.now()).toLocaleTimeString()}
          </p>
        )}
      </div>
    </div>
  );
}

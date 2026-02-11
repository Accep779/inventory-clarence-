import React from 'react';
import { Proposal } from '@/lib/hooks/useInbox';
import { 
  Check, 
  X, 
  Brain, 
  Zap, 
  Target, 
  TrendingUp, 
  Clock, 
  Info,
  Trash2,
  Package,
  ArrowRight,
  Loader2,
  Edit2,
  Send,
  ChevronDown
} from 'lucide-react';
import { AgentChatPanel } from './AgentChatPanel';
import ForensicReasoningPanel from './ForensicReasoningPanel';

interface ProposalDetailProps {
  proposal: Proposal | null;
  onApprove: (id: string) => void;
  onReject: (id: string, reason?: string) => void;
  onRemoveSKU: (id: string, sku: string) => void;
  onChat: (id: string, message: string) => Promise<void>;
}

export function ProposalDetail({ 
  proposal, 
  onApprove, 
  onReject, 
  onRemoveSKU, 
  onChat
}: ProposalDetailProps) {
  if (!proposal) {
    return (
       <div className="h-full flex flex-col items-center justify-center p-12 text-center opacity-20">
          <p className="text-[10px] font-bold uppercase tracking-[0.3em] text-slate-400">No Proposal Selected</p>
       </div>
    );
  }

  const isGenerating = proposal.status === 'GENERATING';

  return (
    <div className="h-full flex flex-col bg-transparent">
       <div className="flex-1 overflow-y-auto custom-scrollbar p-10 pb-0">
          {/* HEADER SECTION */}
          <div className="mb-12">
             <div className="flex items-center gap-3 mb-4">
                <span className="text-[9px] font-bold text-slate-500 uppercase tracking-widest px-2 py-0.5 border border-[hsl(var(--border-panel))] rounded">
                   {proposal.type}
                </span>
                <span className="w-1 h-1 rounded-full bg-slate-800" />
                <span className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">
                   {proposal.agent_type} Analysis
                </span>
             </div>
             <h2 className="text-2xl font-bold tracking-tight text-white mb-2 leading-tight">
                {proposal.proposal_data.title}
             </h2>
             <p className="text-xs text-slate-500 max-w-2xl leading-relaxed font-medium">
                {proposal.proposal_data.description}
             </p>
          </div>

          <div className="grid grid-cols-3 gap-8 mb-12">
             {/* CONFIDENCE */}
             <div className="space-y-3">
                <div className="flex items-center gap-2">
                   <Target className="w-3.5 h-3.5 text-slate-500" />
                   <span className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">Precision</span>
                </div>
                <div className="text-xl font-bold text-white">
                   {(proposal.confidence * 100).toFixed(0)}%
                </div>
                <div className="w-full h-[2px] bg-slate-900 overflow-hidden">
                   <div 
                     className="h-full bg-white transition-all duration-1000 ease-out shadow-[0_0_10px_rgba(255,255,255,0.5)]" 
                     style={{ width: `${proposal.confidence * 100}%` }} 
                   />
                </div>
             </div>

             {/* DIAGNOSTICS */}
              <div className="col-span-2 space-y-3">
                <div className="flex items-center gap-2">
                   <Zap className="w-3.5 h-3.5 text-slate-500" />
                   <span className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">Neural Reasoning</span>
                </div>
                <div className="space-y-4">
                  <div className="p-4 bg-[hsl(var(--bg-input))] border border-[hsl(var(--border-panel))] rounded-xl">
                     <p className="text-[10px] text-slate-400 leading-relaxed italic font-medium">
                        "{proposal.proposal_data.reasoning || "Analyzing historical sell-through and current market velocity to optimize liquidation delta."}"
                     </p>
                  </div>
                  
                  {proposal.origin_execution_id && (
                    <div className="mt-4 p-6 bg-slate-950/40 border border-slate-800/40 rounded-xl">
                       <ForensicReasoningPanel executionId={proposal.origin_execution_id} />
                    </div>
                  )}
                </div>
              </div>
          </div>

          {/* ITEM PREVIEW */}
          <div className="mb-12">
             <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-2">
                   <Package className="w-3.5 h-3.5 text-slate-500" />
                   <span className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">Batch Inventory</span>
                </div>
                <div className="text-[9px] font-bold text-slate-600 uppercase tracking-widest">
                   {proposal.proposal_data.items?.length || 0} SKUs Identified
                </div>
             </div>
             
             <div className="border border-[hsl(var(--border-panel))] rounded-xl overflow-hidden bg-[hsl(var(--bg-input))]">
                <table className="w-full text-left text-[10px]">
                   <thead>
                      <tr className="border-b border-[hsl(var(--border-panel))] bg-white/[0.02]">
                         <th className="px-4 py-3 font-bold text-slate-500 uppercase tracking-widest">Product</th>
                         <th className="px-4 py-3 font-bold text-slate-500 uppercase tracking-widest">Stock</th>
                         <th className="px-4 py-3 font-bold text-slate-500 uppercase tracking-widest">Value</th>
                         <th className="px-4 py-3 text-right"></th>
                      </tr>
                   </thead>
                   <tbody className="divide-y divide-[hsl(var(--border-panel))]">
                      {proposal.proposal_data.items?.map((item: any) => (
                         <tr key={item.sku} className="hover:bg-white/[0.02] transition-colors group">
                            <td className="px-4 py-3 font-medium text-slate-300">
                               {item.title}
                               <p className="text-[8px] text-slate-600 font-mono mt-0.5">{item.sku}</p>
                            </td>
                            <td className="px-4 py-3 text-slate-500">{item.quantity}</td>
                            <td className="px-4 py-3 text-slate-300 font-bold">${item.price || item.value}</td>
                            <td className="px-4 py-3 text-right">
                               <button 
                                 onClick={() => onRemoveSKU(proposal.id, item.sku)}
                                 disabled={proposal.status !== 'pending'}
                                 className="opacity-0 group-hover:opacity-100 p-1 text-slate-600 hover:text-pink-500 transition-all disabled:opacity-0"
                               >
                                  <Trash2 className="w-3 h-3" />
                               </button>
                            </td>
                         </tr>
                      ))}
                   </tbody>
                </table>
             </div>
          </div>
       </div>

       {/* ACTION DOCK & CHAT */}
       <div className="">
          
          <AgentChatPanel 
             proposal={proposal} 
             onSendMessage={onChat} 
          />

          <div className="p-8 border-t border-[hsl(var(--border-panel))] bg-[hsl(var(--bg-panel))] backdrop-blur-[var(--backdrop-blur)]">
             <div className="max-w-4xl mx-auto flex items-center justify-between gap-6">
                <div className="flex items-center gap-6">

                   
                   <button 
                     onClick={() => onReject(proposal.id)}
                     disabled={proposal.status !== 'pending'}
                     className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-600 hover:text-pink-500 transition-all font-medium disabled:opacity-30 disabled:cursor-not-allowed"
                   >
                      Discard
                   </button>
                </div>

                <button 
                  onClick={() => onApprove(proposal.id)}
                  disabled={isGenerating || proposal.status !== 'pending'}
                  className={`flex items-center gap-3 px-8 py-3 rounded-xl text-[10px] font-bold uppercase tracking-widest transition-all ${
                     isGenerating || proposal.status !== 'pending'
                        ? 'bg-slate-900 text-slate-700 cursor-not-allowed border border-[hsl(var(--border-panel))]'
                        : 'bg-white text-black hover:scale-[1.02] shadow-xl shadow-white/5 font-black'
                  }`}
                >
                   Execute Strategy <ArrowRight className="w-3 h-3" />
                </button>
             </div>
          </div>
       </div>
    </div>
  );
}

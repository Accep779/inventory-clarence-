import React from 'react';
import { useInbox } from '../../lib/hooks/useInbox';
import { InboxList } from './InboxList';
import { ProposalDetail } from './ProposalDetail';
import { StrategyProposalDetail } from './StrategyProposalDetail';
import { DevicePreviewPane } from './DevicePreviewPane';
import { Inbox, ShieldCheck, ArrowRight, Loader2, RefreshCcw } from 'lucide-react';

export function ThreePaneLayout() {
  const merchantId = "00000000-0000-0000-0000-000000000000"; // Demo ID
  const { 
    proposals, 
    pending_count, 
    loading, 
    error, 
    approve, 
    reject, 
    removeSKU,
    chat,
    refresh
  } = useInbox(merchantId);

  const [selectedId, setSelectedId] = React.useState<string | null>(null);

  // Auto-select first pending proposal
  React.useEffect(() => {
    if (proposals.length > 0 && !selectedId) {
      const firstPending = proposals.find(p => p.status === 'pending');
      if (firstPending) setSelectedId(firstPending.id);
    }
  }, [proposals, selectedId]);

  const selectedProposal = proposals.find(p => p.id === selectedId) || null;

  if (loading) {
    return (
      <div className="h-[600px] flex flex-col items-center justify-center text-slate-500 bg-black border border-white/5 rounded-3xl">
        <Loader2 className="w-8 h-8 animate-spin mb-4 text-indigo-500" />
        <p className="text-[10px] font-black uppercase tracking-widest text-slate-400">Syncing Neural Queue...</p>
      </div>
    );
  }

  return (
     <div className="flex flex-col h-full">
        {/* CONTAINER */}
        <div className="flex-1 flex bg-[hsl(var(--bg-app))] overflow-hidden relative border-t border-[hsl(var(--border-panel))]">
            
            {/* LEFT PANE: LIST */}
            <div className="w-[320px] border-r border-[hsl(var(--border-panel))] flex flex-col shrink-0">
               <div className="p-6 border-b border-[hsl(var(--border-panel))] flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 bg-indigo-500 rounded-sm" />
                    <h2 className="text-[10px] font-bold text-slate-300 uppercase tracking-widest">Inbox</h2>
                  </div>
                  <div className="px-2 py-0.5 bg-[hsl(var(--bg-input))] border border-[hsl(var(--border-panel))] rounded text-[9px] font-bold text-slate-500 uppercase tracking-widest">
                     {pending_count} New
                  </div>
               </div>
               <InboxList 
                  proposals={proposals} 
                  selectedId={selectedId} 
                  onSelect={setSelectedId} 
               />
               
               {error && (
                 <div className="p-6 border-t border-[hsl(var(--border-panel))]">
                    <p className="text-[10px] text-pink-500 font-bold uppercase tracking-wider mb-2">Network Error</p>
                    <button onClick={refresh} className="text-[9px] font-black text-slate-500 hover:text-white uppercase flex items-center gap-2">
                       <RefreshCcw className="w-3 h-3" /> Retry Sync
                    </button>
                 </div>
               )}
            </div>

            {/* CENTER PANE: DETAIL */}
            <div className="flex-1 min-w-0 h-full border-r border-[hsl(var(--border-panel))] bg-[hsl(var(--bg-panel))] backdrop-blur-[var(--backdrop-blur)]">
                {selectedProposal?.type === 'clearance_proposal' ? (
                  <StrategyProposalDetail 
                    proposal={selectedProposal} 
                    onApprove={approve}
                    onReject={reject}
                    onChat={chat}
                  />
                ) : (
                  <ProposalDetail 
                    proposal={selectedProposal} 
                    onApprove={approve}
                    onReject={reject}
                    onRemoveSKU={removeSKU}
                    onChat={chat}
                  />
                )}
            </div>

            {/* RIGHT PANE: PREVIEW */}
            <div className="w-[450px] shrink-0 bg-[hsl(var(--bg-app))]">
               <DevicePreviewPane proposal={selectedProposal} />
            </div>

        </div>
     </div>
  );
}


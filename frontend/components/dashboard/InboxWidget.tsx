import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Check, X, Inbox, ArrowRight, Sparkles } from 'lucide-react';
import { Proposal } from '@/lib/hooks/useInbox';
import { ProposalCardSkeleton } from '@/components/ui/SkeletonLoader';

interface InboxWidgetProps {
  proposals: Proposal[];
  isLoading: boolean;
  onApprove: (id: string) => Promise<void>;
  onReject: (id: string) => Promise<void>;
  onViewAll?: () => void;
}

export function InboxWidget({ 
  proposals, 
  isLoading, 
  onApprove, 
  onReject, 
  onViewAll 
}: InboxWidgetProps) {
  const pendingProposals = proposals.filter(p => p.status === 'pending').slice(0, 3);

  if (isLoading) {
    return (
      <div className="bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-default))] rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-[hsl(var(--text-primary))]">
            Pending Approvals
          </h3>
          <ProposalCardSkeleton />
        </div>
      </div>
    );
  }

  if (pendingProposals.length === 0) {
    return (
      <div className="bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-subtle))] rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Inbox className="w-5 h-5 text-[hsl(var(--text-secondary))]" />
            <h3 className="text-lg font-semibold text-[hsl(var(--text-primary))]">
              Pending Approvals
            </h3>
          </div>
          <span className="text-xs font-medium text-emerald-400 bg-emerald-400/10 px-2 py-1 rounded-full">
            Inbox Zero
          </span>
        </div>
        <div className="text-center py-8">
          <div className="w-12 h-12 rounded-full bg-[hsl(var(--bg-tertiary))] flex items-center justify-center mx-auto mb-3">
            <Sparkles className="w-6 h-6 text-[hsl(var(--accent-primary))]" />
          </div>
          <p className="text-sm text-[hsl(var(--text-secondary))]">
            All caught up! No pending proposals.
          </p>
          <p className="text-xs text-[hsl(var(--text-tertiary))] mt-1">
            AI agents will notify you when new campaigns are ready.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-default))] rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Inbox className="w-5 h-5 text-[hsl(var(--accent-primary))]" />
          <h3 className="text-lg font-semibold text-[hsl(var(--text-primary))]">
            Pending Approvals
          </h3>
          <span className="text-xs font-bold text-amber-400 bg-amber-400/10 px-2 py-1 rounded-full">
            {pendingProposals.length}
          </span>
        </div>
        <button 
          onClick={onViewAll}
          className="text-sm text-[hsl(var(--accent-primary))] hover:underline flex items-center gap-1"
        >
          View all
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>

      <div className="space-y-3">
        <AnimatePresence mode="popLayout">
          {pendingProposals.map((proposal) => (
            <PendingProposalCard
              key={proposal.id}
              proposal={proposal}
              onApprove={() => onApprove(proposal.id)}
              onReject={() => onReject(proposal.id)}
            />
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}

interface PendingProposalCardProps {
  proposal: Proposal;
  onApprove: () => Promise<void>;
  onReject: () => Promise<void>;
}

function PendingProposalCard({ proposal, onApprove, onReject }: PendingProposalCardProps) {
  const [isProcessing, setIsProcessing] = React.useState(false);
  const [action, setAction] = React.useState<'approve' | 'reject' | null>(null);

  const handleApprove = async () => {
    setIsProcessing(true);
    setAction('approve');
    await onApprove();
  };

  const handleReject = async () => {
    setIsProcessing(true);
    setAction('reject');
    await onReject();
  };

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: -100 }}
      transition={{ type: 'spring', stiffness: 400, damping: 30 }}
      className="p-4 rounded-xl border border-[hsl(var(--border-subtle))] bg-[hsl(var(--bg-tertiary)/0.5)] hover:border-[hsl(var(--border-default))] transition-colors"
    >
      <div className="flex justify-between items-start mb-2">
        <h4 className="font-medium text-[hsl(var(--text-primary))] line-clamp-1">
          {proposal.proposal_data?.title || `${proposal.type} Campaign`}
        </h4>
        <span className="text-xs text-[hsl(var(--text-tertiary))]">
          {new Date(proposal.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>

      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-bold text-amber-400 bg-amber-400/10 px-2 py-0.5 rounded">
          {proposal.status}
        </span>
        <span className="text-xs text-[hsl(var(--text-secondary))]">
          {proposal.agent_type} agent
        </span>
      </div>

      <p className="text-sm text-[hsl(var(--text-secondary))] line-clamp-2 mb-3">
        {proposal.proposal_data?.description || "Synthesizing strategy details..."}
      </p>

      <div className="flex gap-2">
        <button
          onClick={handleApprove}
          disabled={isProcessing}
          className={`flex-1 flex items-center justify-center gap-2 py-2 px-4 rounded-lg text-sm font-medium transition-all ${
            isProcessing && action === 'approve'
              ? 'bg-emerald-500/20 text-emerald-400 cursor-wait'
              : 'bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20'
          }`}
        >
          {isProcessing && action === 'approve' ? (
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
              className="w-4 h-4 border-2 border-emerald-400 border-t-transparent rounded-full"
            />
          ) : (
            <Check className="w-4 h-4" />
          )}
          {isProcessing && action === 'approve' ? 'Approving...' : 'Approve'}
        </button>

        <button
          onClick={handleReject}
          disabled={isProcessing}
          className={`flex-1 flex items-center justify-center gap-2 py-2 px-4 rounded-lg text-sm font-medium transition-all ${
            isProcessing && action === 'reject'
              ? 'bg-rose-500/20 text-rose-400 cursor-wait'
              : 'bg-rose-500/10 text-rose-400 hover:bg-rose-500/20'
          }`}
        >
          {isProcessing && action === 'reject' ? (
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
              className="w-4 h-4 border-2 border-rose-400 border-t-transparent rounded-full"
            />
          ) : (
            <X className="w-4 h-4" />
          )}
          {isProcessing && action === 'reject' ? 'Rejecting...' : 'Reject'}
        </button>
      </div>
    </motion.div>
  );
}

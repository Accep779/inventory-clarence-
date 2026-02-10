import React from 'react';
import { useThoughtsByExecution, Thought } from '../../lib/queries';

interface ForensicReasoningPanelProps {
  executionId: string;
  agentType?: string;
}

const ForensicReasoningPanel: React.FC<ForensicReasoningPanelProps> = ({ executionId, agentType }) => {
  const { data: thoughts, isLoading, error } = useThoughtsByExecution(executionId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8 animate-pulse">
        <div className="text-blue-400 font-mono text-sm">Reconstructing logic chain...</div>
      </div>
    );
  }

  if (error || !thoughts || thoughts.length === 0) {
    return (
      <div className="p-4 bg-slate-900/50 border border-slate-800 rounded-lg">
        <p className="text-slate-500 text-xs italic">No forensic trace found for this action.</p>
      </div>
    );
  }

  // Sort by step number just in case
  const sortedThoughts = [...thoughts].sort((a, b) => a.step_number - b.step_number);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 mb-2">
        <div className="p-1.5 bg-blue-500/10 rounded border border-blue-500/20">
          <span className="text-blue-400 text-[10px] font-bold uppercase tracking-wider">Forensics</span>
        </div>
        <h4 className="text-slate-300 text-sm font-semibold">Agent Reasoning Chain</h4>
      </div>

      <div className="relative pl-4 border-l border-slate-800 space-y-6">
        {sortedThoughts.map((thought, idx) => (
          <div key={thought.id} className="relative">
            {/* Step indicator dot */}
            <div className="absolute -left-[21px] top-1 w-2.5 h-2.5 rounded-full bg-slate-900 border-2 border-slate-700" />
            
            <div className="group">
              <div className="flex items-center justify-between mb-1">
                <span className="text-slate-500 text-[10px] font-mono">STEP {thought.step_number} • {thought.agent_type.toUpperCase()}</span>
                <span className={`text-[10px] font-mono ${thought.confidence_score > 0.8 ? 'text-emerald-400' : 'text-amber-400'}`}>
                  {(thought.confidence_score * 100).toFixed(0)}% CONF
                </span>
              </div>
              
              <div className="p-3 bg-slate-900/80 border border-slate-800 rounded hover:border-slate-700 transition-colors">
                <p className="text-slate-300 text-sm leading-relaxed">{thought.summary}</p>
                
                {thought.detailed_reasoning?._forensic_evidence && (
                  <div className="mt-2 pt-2 border-t border-slate-800/50">
                    <div className="text-slate-500 text-[9px] uppercase tracking-tighter mb-1">Evidence Snapshot</div>
                    <pre className="text-[10px] text-blue-300/80 font-mono overflow-auto max-h-24 p-2 bg-black/30 rounded">
                      {JSON.stringify(thought.detailed_reasoning._forensic_evidence, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
      
      <div className="pt-2 text-center">
        <p className="text-[9px] text-slate-600 uppercase font-mono tracking-widest">End of Logic Trace</p>
      </div>
    </div>
  );
};

export default ForensicReasoningPanel;

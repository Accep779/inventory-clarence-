import React, { useState, useEffect } from 'react';
import { ChevronRight, ChevronDown, Sparkles } from 'lucide-react';

// --- Types ---
interface ThoughtStep {
  step: number;
  text: string;
}

interface AgentEntry {
  id: string;
  agent: string;
  agentColor: string;
  timestamp: string;
  thinking?: {
    duration: string;
    steps: ThoughtStep[];
  };
  conclusion?: string;
  handoffTo?: string;
  tags?: string[];
  status: 'thinking' | 'completed';
}

export default function AgentThoughtStream() {
  const [entries, setEntries] = useState<AgentEntry[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>('1');

  useEffect(() => {
    const mockEntries: AgentEntry[] = [
      {
        id: '1',
        agent: 'Observer Agent',
        agentColor: 'text-emerald-400',
        timestamp: 'Now',
        thinking: {
          duration: '2.4s',
          steps: [
            { step: 1, text: 'Connecting to Shopify Inventory API...' },
            { step: 2, text: 'Scanning 842 SKUs for velocity < 0.1/month' },
            { step: 3, text: 'Cross-referencing with seasonal trends data' },
            { step: 4, text: 'Detected anomaly: "Winter Scarf" (SKU-772) velocity down 45%' },
          ]
        },
        conclusion: 'Found 3 stagnant inventory items in Winter Collection. Passing to Strategy Agent.',
        handoffTo: 'Strategy Agent',
        status: 'completed'
      },
      {
        id: '2',
        agent: 'Strategy Agent',
        agentColor: 'text-amber-400',
        timestamp: '30s ago',
        thinking: {
          duration: '3.1s',
          steps: [
            { step: 1, text: 'Received inventory data from Observer' },
            { step: 2, text: 'Evaluating clearance options: Discount vs Bundle vs Flash Sale' },
            { step: 3, text: 'Simulating 40% discount impact on brand perception' },
            { step: 4, text: 'Bundle strategy selected: pair with high-velocity Beanie (SKU-991)' },
            { step: 5, text: 'Calculating optimal bundle price: $45 (15% savings)' },
          ]
        },
        conclusion: 'Strategy: "Winter Warmth Bundle" targeting Loyalist segment.',
        handoffTo: 'Copywriter Agent',
        status: 'completed'
      },
      {
        id: '3',
        agent: 'Copywriter Agent',
        agentColor: 'text-pink-400',
        timestamp: 'Now',
        thinking: {
          duration: '1.8s',
          steps: [
            { step: 1, text: 'Reading brand voice guidelines: "Warm, Direct, Premium"' },
            { step: 2, text: 'Ingesting Loyalist segment demographics' },
            { step: 3, text: 'Generating 3 email subject line variants...' },
          ]
        },
        tags: ['Drafting', 'In Progress'],
        status: 'thinking'
      },
    ];
    setEntries(mockEntries);
  }, []);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex-1 overflow-y-auto custom-scrollbar px-4 py-3 space-y-1">
        {entries.map((entry) => (
          <div key={entry.id} className="flex gap-3">
            {/* Timeline dot */}
            <div className="flex flex-col items-center pt-1.5 shrink-0">
              <div className={`w-2.5 h-2.5 rounded-full ${
                entry.status === 'thinking' 
                  ? 'bg-indigo-500 ring-4 ring-indigo-500/20 animate-pulse' 
                  : 'bg-slate-600'
              }`} />
              <div className="flex-1 w-px bg-white/5 mt-2" />
            </div>

            {/* Content */}
            <div className="flex-1 pb-5">
              {/* Header */}
              <div className="flex items-baseline justify-between mb-1">
                <span className={`text-xs font-semibold ${entry.agentColor}`}>
                  {entry.agent}
                </span>
                <span className="text-[10px] text-slate-600">{entry.timestamp}</span>
              </div>

              {/* Thinking Process (Collapsible) */}
              {entry.thinking && (
                <div className="mt-1">
                  <button
                    onClick={() => setExpandedId(expandedId === entry.id ? null : entry.id)}
                    className="flex items-center gap-1.5 text-[11px] text-slate-500 hover:text-slate-300 transition-colors"
                  >
                    {expandedId === entry.id ? (
                      <ChevronDown className="w-3 h-3" />
                    ) : (
                      <ChevronRight className="w-3 h-3" />
                    )}
                    <span>Thought for {entry.thinking.duration}</span>
                  </button>

                  {expandedId === entry.id && (
                    <div className="mt-2 pl-3 border-l border-white/5 space-y-2">
                      {entry.thinking.steps.map((step) => (
                        <div key={step.step} className="flex gap-2 text-[12px] text-slate-400">
                          <span className="text-slate-600 shrink-0">{step.step}.</span>
                          <span className="leading-relaxed">{step.text}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Conclusion */}
              {entry.conclusion && (
                <div className="mt-3 p-2.5 bg-white/[0.02] rounded-lg border border-white/5">
                  <div className="flex items-center gap-1.5 mb-1">
                    <Sparkles className="w-3 h-3 text-indigo-400" />
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Conclusion</span>
                  </div>
                  <p className="text-[12px] text-slate-200 leading-relaxed">{entry.conclusion}</p>
                </div>
              )}

              {/* Handoff */}
              {entry.handoffTo && (
                <div className="mt-2 flex items-center gap-2 text-[10px] text-indigo-400">
                  <span className="text-slate-600">→</span>
                  <span className="font-medium">Handoff to {entry.handoffTo}</span>
                </div>
              )}

              {/* Tags */}
              {entry.tags && (
                <div className="flex gap-1.5 mt-2">
                  {entry.tags.map((tag) => (
                    <span 
                      key={tag}
                      className="px-1.5 py-0.5 text-[9px] font-medium text-slate-400 bg-white/5 rounded border border-white/5"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

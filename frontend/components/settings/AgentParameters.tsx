import React from 'react';
import { Cpu, Zap, Target, Sliders } from 'lucide-react';

interface AgentParametersProps {
  data: any;
  onChange: (key: string, value: any) => void;
}

export default function AgentParameters({ data, onChange }: AgentParametersProps) {
  return (
    <div className="space-y-10">
      <div className="flex items-center gap-3">
         <div className="p-2 bg-purple-500/10 rounded-xl">
            <Cpu className="w-5 h-5 text-purple-400" />
         </div>
         <h2 className="text-2xl font-bold text-white tracking-tight">Agent Parameters</h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-10">
         {/* LLM TEMPERATURE */}
         <div className="space-y-4">
            <div className="flex justify-between items-center">
               <div className="flex items-center gap-2">
                  <Zap className="w-3.5 h-3.5 text-slate-500" />
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Model Temperature</label>
               </div>
               <span className="text-xs font-bold text-purple-400">{data.temperature}</span>
            </div>
            <input 
               type="range" 
               min="0" 
               max="1" 
               step="0.1"
               value={data.temperature}
               onChange={(e) => onChange('temperature', parseFloat(e.target.value))}
               className="w-full h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-purple-500"
            />
            <div className="flex justify-between text-[8px] font-bold text-slate-700 uppercase tracking-widest">
               <span>Precise</span>
               <span>Creative</span>
            </div>
         </div>

         {/* MAX TOKENS */}
         <div className="space-y-4">
            <div className="flex justify-between items-center">
               <div className="flex items-center gap-2">
                  <Target className="w-3.5 h-3.5 text-slate-500" />
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Reasoning Depth</label>
               </div>
               <span className="text-xs font-bold text-purple-400">{data.maxTokens}</span>
            </div>
            <select 
               value={data.maxTokens}
               onChange={(e) => onChange('maxTokens', parseInt(e.target.value))}
               className="w-full bg-[hsl(var(--bg-input))] border border-[hsl(var(--border-panel))] rounded-xl px-4 py-3 text-sm text-slate-200 outline-none focus:ring-2 focus:ring-purple-500/50 transition-all appearance-none cursor-pointer"
            >
               <option value="512">Focused (512 tokens)</option>
               <option value="1024">Balanced (1k tokens)</option>
               <option value="2048">Deep Analysis (2k tokens)</option>
               <option value="4096">Neural Stress (4k tokens)</option>
            </select>
         </div>

         {/* STRATEGY VELOCITY */}
         <div className="space-y-4">
            <div className="flex justify-between items-center">
               <div className="flex items-center gap-2">
                  <Sliders className="w-3.5 h-3.5 text-slate-500" />
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Strategy Velocity</label>
               </div>
               <span className="text-xs font-bold text-purple-400">{data.velocity}x</span>
            </div>
            <input 
               type="range" 
               min="1" 
               max="10" 
               step="1"
               value={data.velocity}
               onChange={(e) => onChange('velocity', parseInt(e.target.value))}
               className="w-full h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-purple-500"
            />
            <p className="text-[9px] text-slate-500 leading-relaxed italic">
               Higher velocity increases frequency of inventory scans and proposal generation.
            </p>
         </div>

         {/* CREATIVITY BIAS */}
         <div className="space-y-4">
            <div className="flex justify-between items-center">
                <div className="flex items-center gap-2">
                    <Zap className="w-3.5 h-3.5 text-slate-500" />
                    <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Creativity Bias</label>
                </div>
                <span className="text-xs font-bold text-purple-400">{data.creativity}%</span>
            </div>
            <input 
               type="range" 
               min="0" 
               max="100" 
               value={data.creativity}
               onChange={(e) => onChange('creativity', parseInt(e.target.value))}
               className="w-full h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-purple-500"
            />
            <p className="text-[9px] text-slate-500 leading-relaxed italic">
               Influences the AD copy variation and multi-modal asset generation variance.
            </p>
         </div>
      </div>
    </div>
  );
}

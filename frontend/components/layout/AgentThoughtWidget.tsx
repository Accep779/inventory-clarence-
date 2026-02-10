import React from 'react';
import { X, Minus } from 'lucide-react';
import AgentThoughtStream from './AgentThoughtStream';

interface AgentThoughtWidgetProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function AgentThoughtWidget({ isOpen, onClose }: AgentThoughtWidgetProps) {
  const [isMinimized, setIsMinimized] = React.useState(false);

  if (!isOpen) return null;

  return (
    <div 
      className={`fixed z-40 transition-all duration-300 ease-out ${
        isMinimized 
          ? 'bottom-6 right-6 w-64 h-12' 
          : 'bottom-6 right-6 w-[340px] h-[480px]'
      }`}
    >
      <div className="w-full h-full bg-[#0a0d12]/95 backdrop-blur-xl rounded-xl shadow-2xl shadow-black/40 border border-indigo-500/20 flex flex-col overflow-hidden">
        {/* Compact Header */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/5 shrink-0">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full border-2 border-indigo-500 flex items-center justify-center">
              <div className="w-1.5 h-1.5 rounded-full bg-indigo-500" />
            </div>
            <span className="text-[11px] font-bold text-slate-200 uppercase tracking-widest">Agent Stream</span>
          </div>
          
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider">Live</span>
            </div>
            <button
              onClick={() => setIsMinimized(!isMinimized)}
              className="p-1 text-slate-500 hover:text-white transition-colors"
            >
              <Minus className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={onClose}
              className="p-1 text-slate-500 hover:text-white transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Content */}
        {!isMinimized && (
          <div className="flex-1 overflow-hidden">
            <AgentThoughtStream />
          </div>
        )}

        {/* Minimized State */}
        {isMinimized && (
          <div className="flex-1 flex items-center px-4">
            <span className="text-[10px] text-slate-500">3 agents active...</span>
          </div>
        )}
      </div>
    </div>
  );
}

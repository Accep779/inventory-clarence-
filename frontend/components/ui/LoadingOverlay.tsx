
import React from 'react';
import { Loader2, Sparkles } from 'lucide-react';

interface LoadingOverlayProps {
  isLoading: boolean;
  message?: string;
  subMessage?: string;
}

export function LoadingOverlay({ isLoading, message = "Processing...", subMessage }: LoadingOverlayProps) {
  if (!isLoading) return null;

  return (
    <div className="absolute inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex flex-col items-center justify-center rounded-2xl animate-in fade-in duration-300">
       <div className="relative mb-6">
          <div className="absolute inset-0 bg-indigo-500/20 blur-xl rounded-full animate-pulse" />
          <Loader2 className="w-12 h-12 text-indigo-400 animate-spin relative z-10" />
       </div>
       
       <h3 className="text-lg font-bold text-white mb-2">{message}</h3>
       
       {subMessage && (
         <div className="flex items-center gap-2 text-indigo-300/80 text-xs font-medium uppercase tracking-widest bg-indigo-500/10 px-3 py-1 rounded-full">
            <Sparkles className="w-3 h-3" />
            {subMessage}
         </div>
       )}
    </div>
  );
}

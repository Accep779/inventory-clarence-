import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Clock, Loader2, Sparkles } from 'lucide-react';
import { Proposal } from '@/lib/hooks/useInbox';

interface AgentChatPanelProps {
  proposal: Proposal;
  onSendMessage: (id: string, message: string) => Promise<void>;
}

export function AgentChatPanel({ proposal, onSendMessage }: AgentChatPanelProps) {
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [proposal.chat_history, sending]);

  const handleSend = async () => {
    if (!message.trim() || sending) return;
    
    setSending(true);
    try {
      await onSendMessage(proposal.id, message);
      setMessage('');
    } catch (e) {
      console.error(e);
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const history = proposal.chat_history || [];

  return (
    <div className="flex flex-col h-full bg-[hsl(var(--bg-panel))] border-t border-[hsl(var(--border-panel))]">
      {/* Messages Area */}
      {history.length > 0 && (
         <div 
           ref={scrollRef}
           className="flex-1 overflow-y-auto p-6 space-y-4 max-h-[300px] border-b border-[hsl(var(--border-panel))] custom-scrollbar"
         >
           {history.map((msg, idx) => (
             <div 
               key={idx} 
               className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}
             >
               <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
                 msg.role === 'user' ? 'bg-indigo-500/20 text-indigo-400' : 'bg-slate-800 text-emerald-400'
               }`}>
                 {msg.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
               </div>
               
               <div className={`flex flex-col max-w-[80%] ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                 <div className={`p-3 rounded-2xl text-xs font-medium leading-relaxed ${
                   msg.role === 'user' 
                     ? 'bg-indigo-600 text-white rounded-tr-sm' 
                     : 'bg-slate-800 text-slate-200 rounded-tl-sm border border-slate-700'
                 }`}>
                   {msg.content}
                 </div>
                 <span className="text-[9px] text-slate-600 mt-1 flex items-center gap-1">
                   <Clock className="w-2.5 h-2.5" />
                   {new Date(msg.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                 </span>
               </div>
             </div>
           ))}
           
           {sending && (
             <div className="flex gap-3">
               <div className="w-8 h-8 rounded-lg bg-slate-800 text-emerald-400 flex items-center justify-center shrink-0 animate-pulse">
                 <Sparkles className="w-4 h-4" />
               </div>
               <div className="p-3 bg-slate-800/50 rounded-2xl rounded-tl-sm border border-slate-800 flex items-center gap-2">
                 <Loader2 className="w-3 h-3 animate-spin text-slate-500" />
                 <span className="text-xs text-slate-500 italic">Thinking...</span>
               </div>
             </div>
           )}
         </div>
      )}

      {/* Input Area */}
      <div className="p-4 bg-[hsl(var(--bg-input))]">
         <div className="relative group">
            <div className="absolute -inset-0.5 bg-gradient-to-r from-indigo-500/20 to-purple-500/20 rounded-xl opacity-0 group-focus-within:opacity-100 transition duration-500 blur-sm"></div>
            <div className="relative flex items-center bg-[hsl(var(--bg-app))] rounded-xl border border-[hsl(var(--border-panel))] group-focus-within:border-indigo-500/30 transition-colors">
               <input 
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  onKeyDown={handleKeyDown}
                  disabled={sending}
                  type="text"
                  placeholder={history.length === 0 ? "Instruct agents to adjust parameters..." : "Reply to agent..."}
                  className="w-full bg-transparent border-none py-3 px-4 text-sm text-slate-200 placeholder:text-slate-600 focus:ring-0 focus:outline-none disabled:opacity-50"
               />
               <button 
                  onClick={handleSend}
                  disabled={!message.trim() || sending}
                  className="mr-2 p-2 rounded-lg text-slate-400 hover:text-indigo-400 hover:bg-white/5 transition-all disabled:opacity-30 disabled:hover:bg-transparent"
               >
                  {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
               </button>
            </div>
         </div>
         {history.length === 0 && (
           <p className="text-[9px] text-slate-600 mt-2 text-center">
             💡 Pro Tip: Try "Increase discount to 25%" or "Target local customers only"
           </p>
         )}
      </div>
    </div>
  );
}

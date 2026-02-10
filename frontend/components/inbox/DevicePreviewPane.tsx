import React from 'react';
import { Proposal } from '@/lib/hooks/useInbox';
import { Smartphone, Monitor, ShieldCheck, Sparkles, MessageSquare } from 'lucide-react';

interface DevicePreviewPaneProps {
  proposal: Proposal | null;
}

export function DevicePreviewPane({ proposal }: DevicePreviewPaneProps) {
  const [view, setView] = React.useState<'mobile' | 'desktop'>('mobile');

  return (
    <div className="h-full flex flex-col bg-[hsl(var(--bg-app))]">
       {/* HEADER */}
       <div className="p-6 border-b border-[hsl(var(--border-panel))] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Smartphone className="w-3.5 h-3.5 text-slate-500" />
            <h3 className="text-[10px] font-bold text-slate-300 uppercase tracking-widest">
               Device Preview
            </h3>
          </div>
          <div className="flex gap-1">
             <div className="w-1.5 h-1.5 rounded-full bg-slate-700" />
             <div className="w-1.5 h-1.5 rounded-full bg-slate-700" />
          </div>
       </div>

       <div className="flex-1 p-12 flex items-center justify-center overflow-hidden bg-[hsl(var(--bg-app))] group relative">
          {!proposal ? (
            <div className="flex flex-col items-center justify-center opacity-20">
               <Smartphone className="w-10 h-10 text-slate-500 mb-4" />
               <p className="text-[9px] font-bold uppercase tracking-[0.2em] text-slate-500">Preview Standby</p>
            </div>
          ) : (
             <>
                {/* DEVICE TOGGLE OVERLAY */}
                <div className="absolute top-4 right-4 flex bg-slate-900/50 rounded-lg p-0.5 z-20">
                   <button 
                      onClick={() => setView('mobile')}
                      className={`p-1 rounded transition-all ${view === 'mobile' ? 'bg-white/10 text-white' : 'text-slate-600 hover:text-white'}`}
                    >
                      <Smartphone className="w-3.5 h-3.5" />
                   </button>
                   <button 
                      onClick={() => setView('desktop')}
                      className={`p-1 rounded transition-all ${view === 'desktop' ? 'bg-white/10 text-white' : 'text-slate-600 hover:text-white'}`}
                    >
                      <Monitor className="w-3.5 h-3.5" />
                   </button>
                </div>

                {/* REALISTIC PHONE FRAME */}
                <div 
                  className={`relative transition-all duration-700 ease-[cubic-bezier(0.23,1,0.32,1)] ${
                    view === 'mobile' ? 'w-[300px] h-[600px]' : 'w-[500px] h-[320px] rounded-[1.5rem]'
                  }`}
                >
                  {/* Exterior Frame (Titanium) */}
                  <div className={`absolute inset-0 bg-[#2d2d2d] rounded-[3rem] shadow-[0_0_0_2px_#3a3a3a,0_0_0_6px_#1a1a1a,0_20px_50px_-10px_rgba(0,0,0,0.5)] ${view === 'desktop' ? 'rounded-[1.5rem]' : ''}`}>
                    
                    {/* BUTTONS (Mobile Only) */}
                    {view === 'mobile' && (
                      <>
                        <div className="absolute top-28 -left-[7px] w-[5px] h-8 bg-[#1a1a1a] rounded-l-md" /> {/* Mute */}
                        <div className="absolute top-44 -left-[7px] w-[5px] h-14 bg-[#1a1a1a] rounded-l-md" /> {/* Vol Up */}
                        <div className="absolute top-64 -left-[7px] w-[5px] h-14 bg-[#1a1a1a] rounded-l-md" /> {/* Vol Down */}
                        <div className="absolute top-52 -right-[7px] w-[5px] h-20 bg-[#1a1a1a] rounded-r-md" /> {/* Power */}
                      </>
                    )}

                    {/* Inner Bezel (Black Glass Edge) */}
                    <div className={`absolute inset-[6px] bg-black rounded-[2.6rem] overflow-hidden border border-white/5 ${view === 'desktop' ? 'rounded-[1.2rem] inset-[4px]' : ''}`}>
                      
                         {/* Dynamic Island / Notch Area */}
                         {view === 'mobile' && (
                            <div className="absolute top-0 left-0 right-0 h-8 z-30 flex justify-center pt-2">
                               <div className="w-24 h-6 bg-black rounded-full flex items-center justify-between px-2">
                                   <div className="w-1.5 h-1.5 rounded-full bg-[#1a1a1a]" /> {/* Lens */}
                                   <div className="w-1.5 h-1.5 rounded-full bg-green-500/20" /> {/* Active Indicator */}
                               </div>
                            </div>
                         )}

                         {/* Status Bar */}
                         <div className="absolute top-0 left-0 right-0 h-10 px-6 flex justify-between items-end pb-2 z-20">
                            <span className="text-[10px] font-semibold text-black/80">9:41</span>
                            <div className="flex gap-1.5">
                                <div className="w-3 h-3 text-black/80"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14H9V8h2v8zm4 0h-2V8h2v8z"/></svg></div>
                                <div className="w-4 h-3 rounded-sm border border-black/30 bg-black/80 relative text-[8px] flex items-center justify-center font-bold text-white">4G</div>
                                <div className="w-5 h-2.5 rounded-sm border border-black/30 relative ml-0.5">
                                   <div className="absolute inset-0.5 right-1 bg-black/80 rounded-[1px]" />
                                </div>
                            </div>
                         </div>
                      
                         {/* SCREEN CONTENT */}
                         <div className="absolute inset-0 bg-white pt-10 overflow-hidden flex flex-col">
                            {/* Browser Bar (if desktop) */}
                            {view === 'desktop' && (
                              <div className="h-8 bg-slate-100 border-b border-slate-200 flex items-center px-4 gap-2">
                                 <div className="flex gap-1">
                                    <div className="w-2 h-2 rounded-full bg-pink-400" />
                                    <div className="w-2 h-2 rounded-full bg-amber-400" />
                                    <div className="w-2 h-2 rounded-full bg-emerald-400" />
                                 </div>
                                 <div className="flex-1 mx-4 h-5 bg-white rounded border border-slate-200 text-[8px] text-slate-400 flex items-center px-2">
                                    cephly.store/winter-collection
                                 </div>
                              </div>
                            )}

                            <div className="flex-1 overflow-y-auto custom-scrollbar p-6">
                              <div className="w-full h-40 bg-slate-50 rounded-xl mb-4 flex items-center justify-center border border-slate-100 relative overflow-hidden group/image">
                                  <Sparkles className="w-8 h-8 text-slate-200 group-hover/image:text-indigo-400 transition-colors" />
                                  <div className="absolute inset-0 bg-gradient-to-tr from-indigo-500/5 to-purple-500/5 opacity-0 group-hover/image:opacity-100 transition-opacity" />
                              </div>
                              <h4 className="text-xl font-extrabold tracking-tight mb-2 text-black leading-tight">
                                {proposal.proposal_data.preview_headline || 'Exclusive Offer'}
                              </h4>
                              <p className="text-xs font-medium text-slate-500 mb-8 leading-relaxed">
                                {proposal.proposal_data.preview_body || 'Our AI agent identified a perfect match for your style. Grab it now at a unique discount.'}
                              </p>
                              <div className="h-12 w-full bg-black rounded-xl flex items-center justify-center text-[10px] font-bold uppercase tracking-widest text-white shadow-xl shadow-black/20 hover:scale-[1.02] transition-transform cursor-pointer">
                                Shop Now
                              </div>

                              <div className="mt-8 pt-8 border-t border-slate-100">
                                 <div className="flex items-center justify-between opacity-50 mb-3">
                                    <div className="w-12 h-2 bg-slate-200 rounded-full" />
                                    <div className="w-8 h-8 rounded-full bg-slate-200" />
                                 </div>
                                 <div className="space-y-2 opacity-50">
                                    <div className="w-full h-2 bg-slate-200 rounded-full" />
                                    <div className="w-2/3 h-2 bg-slate-200 rounded-full" />
                                 </div>
                              </div>
                            </div>

                            {/* Home Indicator */}
                            {view === 'mobile' && (
                               <div className="absolute bottom-1 left-1/2 -translate-x-1/2 w-32 h-1 bg-black/90 rounded-full" />
                            )}
                         </div>
                    </div>
                  </div>
                </div>
                
                {/* OVERLAY FOR STATUS */}
                {proposal.status === 'GENERATING' && (
                  <div className="absolute inset-0 bg-black/80 backdrop-blur-sm flex flex-col items-center justify-center z-30">
                     <div className="w-8 h-8 rounded-full border border-white/10 border-t-white animate-spin mb-4" />
                     <p className="text-[9px] font-bold uppercase tracking-[0.2em] text-white animate-pulse">Neural Render</p>
                  </div>
                )}
             </>
          )}
       </div>

       <div className="p-8 border-t border-[hsl(var(--border-panel))] space-y-6">
          <div className="flex items-center gap-2 opacity-30">
             <ShieldCheck className="w-3.5 h-3.5 text-slate-400" />
             <span className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">Brand Safety Verified</span>
          </div>
          <div className="bg-[hsl(var(--bg-input))] p-4 rounded-xl border border-[hsl(var(--border-panel))]">
             <div className="flex items-center gap-2 mb-2">
                <MessageSquare className="w-3 h-3 text-slate-500" />
                <span className="text-[8px] font-bold text-slate-400 uppercase tracking-widest">Context</span>
             </div>
             <p className="text-[10px] text-slate-500 italic leading-relaxed font-medium">
                {proposal ? `"Modern, high-contrast visual with dynamic product layering."` : "Awaiting selection..."}
             </p>
          </div>
       </div>
    </div>
  );
}


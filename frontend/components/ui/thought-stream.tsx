"use client"

import { useEffect, useState, useRef } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Settings, ArrowUp, Brain, Info, AlertTriangle, CheckCircle } from "lucide-react"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { useThoughts, Thought } from "@/lib/queries"

export function ThoughtStream() {
  const { data: thoughts, isLoading } = useThoughts()
  
  return (
    <div className="flex flex-col h-full bg-[#0B0E14] border-l border-white/5">
       {/* HEADER */}
       <div className="h-16 flex items-center justify-between px-6 border-b border-white/5 bg-[#0B0E14] shrink-0">
          <div className="flex items-center gap-3">
             <Brain className="w-4 h-4 text-indigo-500 animate-[pulse_3s_ease-in-out_infinite]" />
             <span className="text-xs font-bold uppercase tracking-widest text-slate-400">Agent Stream</span>
          </div>
          <div className="flex items-center gap-2">
             <div className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />
             <span className="text-[10px] font-bold text-indigo-400 tracking-wider">LIVE</span>
          </div>
       </div>

       {/* TIMELINE CONTENT */}
       <ScrollArea className="flex-1 p-6">
          <div className="relative border-l border-slate-800 ml-2 space-y-8 pl-8 pb-10">
             {isLoading && (
               <div className="text-slate-500 text-xs font-mono animate-pulse">Connecting to neural stream...</div>
             )}
             
             {!isLoading && (!thoughts || thoughts.length === 0) && (
               <div className="text-slate-600 text-xs font-mono italic">No active thoughts. Agents are standing by.</div>
             )}

             {thoughts?.map((thought, index) => (
                <div key={thought.id} className="relative group">
                   {/* Timeline Dot */}
                   <span className={cn(
                      "absolute -left-[37px] top-1.5 h-4 w-4 rounded-full border-2 border-[#0B0E14] z-10",
                      index === 0 ? "bg-indigo-500 ring-4 ring-indigo-500/20" : "bg-slate-700 group-hover:bg-slate-600"
                   )} />

                   <div className="flex items-center justify-between mb-1">
                      <span className={cn(
                         "text-[10px] font-bold uppercase tracking-tighter font-mono",
                         thought.agent_type === "observer" && "text-indigo-400",
                         thought.agent_type === "strategy" && "text-emerald-400",
                         thought.agent_type === "matchmaker" && "text-purple-400",
                      )}>
                         {thought.agent_type} Agent
                      </span>
                      <span className="text-[10px] text-slate-600 font-mono">
                         {new Date(thought.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      </span>
                   </div>

                   <div className="flex items-start gap-2">
                      {thought.thought_type === 'warning' && <AlertTriangle className="w-3 h-3 text-amber-500 shrink-0 mt-0.5" />}
                      {thought.thought_type === 'decision' && <CheckCircle className="w-3 h-3 text-emerald-500 shrink-0 mt-0.5" />}
                      {thought.thought_type === 'analysis' && <Info className="w-3 h-3 text-indigo-400 shrink-0 mt-0.5" />}
                      <p className="text-sm text-slate-300 mb-3 leading-relaxed">
                         {thought.summary}
                      </p>
                   </div>

                   {thought.detailed_reasoning && (
                      <div className="bg-slate-900/50 rounded-lg p-3 border border-white/5 font-mono text-[10px] text-slate-400 space-y-1 overflow-x-hidden">
                         {Object.entries(thought.detailed_reasoning).map(([key, value]) => (
                            <div key={key} className="flex gap-2">
                               <span className="text-slate-600 shrink-0 opacity-50">{">"}</span>
                               <span className="text-slate-500 truncate"><span className="text-slate-400">{key}:</span> {JSON.stringify(value)}</span>
                            </div>
                         ))}
                      </div>
                   )}
                </div>
             ))}
          </div>
       </ScrollArea>

       {/* CHAT INPUT AREA */}
       <div className="p-4 border-t border-white/5 bg-[#0B0E14] shrink-0">
          <div className="relative">
             <Input 
                placeholder="Ask agents to analyze..." 
                className="bg-slate-900/50 border-white/10 text-slate-300 placeholder:text-slate-600 pr-10 focus-visible:ring-indigo-500/50 focus-visible:border-indigo-500/50"
             />
             <div className="absolute right-2 top-2 p-1 rounded-md bg-white/5 hover:bg-white/10 transition-colors cursor-pointer text-slate-400 hover:text-white">
                <ArrowUp className="w-4 h-4" />
             </div>
          </div>
       </div>

    </div>
  )
}

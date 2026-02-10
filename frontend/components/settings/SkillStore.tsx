import React from 'react';
import { useSkills, useSkillToggle } from '../../lib/queries/command-center';
import { Sparkles, Activity, AlertCircle, PlayCircle, Loader2 } from 'lucide-react';

export default function SkillStore() {
    const { data, isLoading, error } = useSkills();
    const toggleMutation = useSkillToggle();

    if (isLoading) {
        return (
            <div className="flex flex-col items-center justify-center p-20 text-slate-500 gap-4">
                <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
                <p className="text-sm font-medium tracking-wide">Scanning Agent Capabilities...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="p-8 border border-red-500/20 bg-red-500/5 rounded-2xl flex items-center gap-4 text-red-400">
                <AlertCircle className="w-6 h-6" />
                <div>
                    <p className="font-bold">Failed to load skills</p>
                    <p className="text-sm opacity-80">Is the Agent API online?</p>
                </div>
            </div>
        );
    }

    // Fallback if empty
    if (!data?.skills || data.skills.length === 0) {
        return (
            <div className="text-center p-12 bg-slate-900/50 rounded-3xl border border-slate-800">
                <Sparkles className="w-12 h-12 text-slate-700 mx-auto mb-4" />
                <h3 className="text-lg font-bold text-white">No Skills Installed</h3>
                <p className="text-slate-500 mt-2">Add folders to <code className="text-indigo-400 bg-indigo-950/30 px-2 py-1 rounded">backend/app/skills/</code> to teach the agent new tricks.</p>
            </div>
        );
    }

    return (
        <div className="space-y-8">
            <div>
                <h2 className="text-2xl font-bold text-white flex items-center gap-3">
                    <Sparkles className="w-6 h-6 text-amber-400" />
                    Agent Skill Store
                </h2>
                <p className="text-slate-400 mt-2">Manage the autonomous capabilities of your workforce. Installed skills appear here automatically.</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {data.skills.map((skill) => (
                    <SkillCard
                        key={skill.name}
                        skill={skill}
                        onToggle={() => toggleMutation.mutate({ skillName: skill.name, active: !skill.active })}
                        isToggling={toggleMutation.isPending}
                    />
                ))}
            </div>
        </div>
    );
}


function SkillCard({ skill, onToggle, isToggling }: any) {
    return (
        <div className={`
      relative overflow-hidden
      p-6 rounded-3xl border transition-all duration-300 group
      ${skill.active
                ? 'bg-indigo-900/10 border-indigo-500/30 shadow-2xl shadow-indigo-900/20 hover:border-indigo-500/50'
                : 'bg-slate-950/30 border-slate-800 hover:border-slate-700 opacity-60 hover:opacity-100'}
    `}>
            {/* Active Indicator Glow */}
            {skill.active && (
                <div className="absolute -top-10 -right-10 w-32 h-32 bg-indigo-500/20 rounded-full blur-3xl pointer-events-none" />
            )}

            <div className="flex justify-between items-start mb-6">
                <div>
                    <div className={`
                w-10 h-10 rounded-2xl flex items-center justify-center mb-4
                ${skill.active ? 'bg-indigo-500 text-white shadow-lg shadow-indigo-500/30' : 'bg-slate-800 text-slate-500'}
            `}>
                        <Sparkles className="w-5 h-5" />
                    </div>
                    <h3 className="text-lg font-black text-white tracking-tight">{formatName(skill.name)}</h3>
                    <p className="text-xs font-bold text-slate-500 uppercase tracking-widest mt-1">v1.2.0 • {skill.tool_count} Tools</p>
                </div>

                <button
                    onClick={onToggle}
                    disabled={isToggling}
                    className={`
                px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all
                ${skill.active
                            ? 'bg-emerald-500/10 text-emerald-400 hover:bg-red-500/10 hover:text-red-400'
                            : 'bg-slate-800 text-slate-400 hover:bg-indigo-500 hover:text-white'}
            `}
                >
                    {skill.active ? 'Installed' : 'Install'}
                </button>
            </div>

            <p className="text-sm font-medium text-slate-400 leading-relaxed mb-6 h-12">
                {skill.description || "No description provided in SKILL.md"}
            </p>

            {/* Footer Meta */}
            <div className="flex items-center gap-4 pt-6 border-t border-white/5">
                <div className="flex items-center gap-2">
                    <Activity className={`w-3 h-3 ${skill.active ? 'text-emerald-400 animate-pulse' : 'text-slate-600'}`} />
                    <span className={`text-[10px] uppercase font-bold tracking-wider ${skill.active ? 'text-emerald-400' : 'text-slate-600'}`}>
                        {skill.active ? 'Running' : 'Offline'}
                    </span>
                </div>
                <div className="flex items-center gap-2">
                    <PlayCircle className="w-3 h-3 text-slate-600" />
                    <span className="text-[10px] uppercase font-bold tracking-wider text-slate-500">
                        Auto-exec enabled
                    </span>
                </div>
            </div>
        </div>
    );
}

function formatName(name: string) {
    return name.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
}


import React, { useState } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import {
   Shield,
   Bell,
   Zap,
   Globe,
   Cpu,
   Fingerprint
} from 'lucide-react';

// Sub‑page components
// Sub‑page components
import StoreDNA from '../components/settings/StoreDNA';
import AgentParameters from '../components/settings/AgentParameters';
import SecurityAccess from '../components/settings/SecurityAccess';
// [PHASE 7] Command Center Components
import DigestStatus from '../components/settings/DigestStatus';
import GatewayHub from '../components/settings/GatewayHub';
import SkillStore from '../components/settings/SkillStore';


export default function SettingsPage() {
   const [activeSection, setActiveSection] = useState('storeDNA');

   // Master state for all settings
   const [settings, setSettings] = useState({
      // Store DNA
      brandTone: 'luxury',
      autonomy: 85,
      primaryObjective: 'revenue',
      identityDescription: 'Our brand is defined by quiet luxury and archival quality. We serve high-net-worth individuals who value longevity over trends.',
      // Agent Parameters
      temperature: 0.7,
      maxTokens: 1024,
      velocity: 5,
      creativity: 65,
      // Security
      apiKey: 'test/Pass3d'
   });

   const [hasChanges, setHasChanges] = useState(false);
   const [isSaving, setIsSaving] = useState(false);

   const handleSettingChange = (key: string, value: any) => {
      setSettings(prev => ({ ...prev, [key]: value }));
      setHasChanges(true);
   };

   const handleReset = () => {
      // In a real app, this would re-fetch from the backend. For now, just logic.
      if (confirm('Revert all changes to last saved state?')) {
         setHasChanges(false);
      }
   };

   const handleSave = async () => {
      setIsSaving(true);
      // Simulate API call
      console.log('Saving settings:', settings);
      await new Promise(resolve => setTimeout(resolve, 800));
      setIsSaving(false);
      setHasChanges(false);
   };

   return (
      <AppShell title="System Settings">
         <div className="flex flex-col gap-12 max-w-6xl mx-auto pb-20">

            {/* HEADER & GLOBAL ACTIONS */}
            <div className="flex justify-between items-end">
               <div>
                  <h1 className="text-4xl font-extrabold tracking-tight text-white mb-2">System Control</h1>
                  <p className="text-slate-400 font-medium tracking-tight">Configure autonomous behavior, system security, and <span className="text-white italic">Store DNA</span>.</p>
               </div>

               {hasChanges && (
                  <div className="flex items-center gap-4 animate-in fade-in slide-in-from-right-4 duration-300">
                     <button
                        onClick={handleReset}
                        className="px-6 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 hover:text-white transition-colors"
                     >
                        Reset
                     </button>
                     <button
                        onClick={handleSave}
                        disabled={isSaving}
                        className="bg-white text-black px-8 py-3 rounded-xl text-[10px] font-black uppercase tracking-widest hover:scale-[1.02] active:scale-[0.98] transition-all shadow-xl shadow-white/10 flex items-center gap-2"
                     >
                        {isSaving && <Zap className="w-3 h-3 animate-spin" />}
                        {isSaving ? 'Processing...' : 'Sync Changes'}
                     </button>
                  </div>
               )}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-12">
               {/* SUB-NAV */}
               <div className="lg:col-span-1 space-y-1">
                  <SettingsNav active={activeSection === 'storeDNA'} icon={Fingerprint} label="Store DNA" onClick={() => setActiveSection('storeDNA')} />
                  <SettingsNav active={activeSection === 'agentParams'} icon={Cpu} label="Agent Parameters" onClick={() => setActiveSection('agentParams')} />
                  <SettingsNav active={activeSection === 'skills'} icon={Zap} label="Skill Store" onClick={() => setActiveSection('skills')} />

                  <div className="h-px bg-slate-800 my-4" />

                  <SettingsNav active={activeSection === 'notifications'} icon={Bell} label="Anti-Fatigue Shield" onClick={() => setActiveSection('notifications')} />
                  <SettingsNav active={activeSection === 'api'} icon={Globe} label="Gateway Hub" onClick={() => setActiveSection('api')} />
                  <SettingsNav active={activeSection === 'security'} icon={Shield} label="Security Check" onClick={() => setActiveSection('security')} />
               </div>

               {/* MAIN CONTENT AREA */}
               <div className="lg:col-span-3 space-y-12">
                  <div className="bg-[hsl(var(--bg-panel))] backdrop-blur-[var(--backdrop-blur)] border border-[hsl(var(--border-panel))] rounded-[40px] p-12 shadow-2xl">
                     {activeSection === 'storeDNA' && <StoreDNA data={settings} onChange={handleSettingChange} />}
                     {activeSection === 'agentParams' && <AgentParameters data={settings} onChange={handleSettingChange} />}
                     {activeSection === 'security' && <SecurityAccess data={settings} onChange={handleSettingChange} />}

                     {/* [PHASE 7] WIRED COMPONENTS */}
                     {activeSection === 'notifications' && <DigestStatus />}
                     {activeSection === 'api' && <GatewayHub />}
                     {activeSection === 'skills' && <SkillStore />}

                  </div>

                  {/* AGENT FLEET STATUS - Only shown for Agent Parameters */}
                  {activeSection === 'agentParams' && (
                     <div className="bg-[hsl(var(--bg-panel))] backdrop-blur-[var(--backdrop-blur)] border border-[hsl(var(--border-panel))] rounded-[40px] p-12 shadow-2xl">
                        <div className="flex items-center justify-between mb-10">
                           <h3 className="text-xl font-bold text-white tracking-tight flex items-center gap-3">
                              <div className="p-2 bg-indigo-500/10 rounded-xl">
                                 <Cpu className="w-5 h-5 text-indigo-400" />
                              </div>
                              Agent Fleet Status
                           </h3>
                           <div className="flex items-center gap-2 px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-full">
                              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                              <span className="text-[9px] font-black text-emerald-500 uppercase tracking-widest">Healthy</span>
                           </div>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                           <AgentStatusCard name="Observer" status="Online" load="12%" color="emerald" />
                           <AgentStatusCard name="Strategy" status="Optimizing" load="84%" color="amber" />
                           <AgentStatusCard name="Matchmaker" status="Active" load="32%" color="indigo" />
                        </div>
                     </div>
                  )}
               </div>
            </div>
         </div>
      </AppShell>
   );
}


function SettingsNav({ icon: Icon, label, active, onClick }: any) {
   return (
      <button
         onClick={onClick}
         className={`w-full flex items-center gap-3 px-5 py-3.5 rounded-2xl transition-all group ${active ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20 border border-indigo-500/20' : 'text-slate-500 hover:text-white hover:bg-slate-800/50'}`}
      >
         <Icon className={`w-5 h-5 ${active ? 'text-white' : 'group-hover:text-white'}`} />
         <span className="font-bold tracking-tight text-sm">{label}</span>
      </button>
   );
}

function ObjectiveOption({ icon: Icon, label, sub, active }: any) {
   return (
      <div className={`p-4 rounded-2xl border flex items-center gap-4 cursor-pointer transition-all ${active ? 'bg-indigo-600/10 border-indigo-500/40' : 'bg-slate-950/40 border-slate-800/60 hover:border-slate-700'}`}>
         <div className={`p-2.5 rounded-xl ${active ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20' : 'bg-slate-900 text-slate-500'}`}>
            <Icon className="w-5 h-5" />
         </div>
         <div>
            <p className={`text-sm font-black ${active ? 'text-white' : 'text-slate-300'}`}>{label}</p>
            <p className="text-[10px] font-bold text-slate-500 uppercase">{sub}</p>
         </div>
      </div>
   );
}

function AgentStatusCard({ name, status, load, color }: any) {
   const colors: any = {
      emerald: 'bg-emerald-500 shadow-emerald-500/20 text-emerald-500',
      amber: 'bg-amber-500 shadow-amber-500/20 text-amber-500',
      indigo: 'bg-indigo-500 shadow-indigo-500/20 text-indigo-500',
   };

   return (
      <div className="p-6 bg-slate-950/40 border border-slate-800/60 rounded-2xl group hover:border-slate-700 transition-all">
         <div className="flex justify-between items-start mb-4">
            <span className="text-sm font-black text-white">{name}</span>
            <div className={`w-2 h-2 rounded-full ${colors[color]} shadow-[0_0_8px]`} />
         </div>
         <div className="flex items-end justify-between">
            <div>
               <p className="text-[10px] font-black uppercase text-slate-500 tracking-widest leading-none mb-1">Status</p>
               <p className={`text-xs font-black ${colors[color].split(' ')[2]}`}>{status}</p>
            </div>
            <div className="text-right">
               <p className="text-[10px] font-black uppercase text-slate-500 tracking-widest leading-none mb-1">Load</p>
               <p className="text-xs font-black text-white">{load}</p>
            </div>
         </div>
      </div>
   );
}


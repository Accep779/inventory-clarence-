import React, { useState } from 'react';
import { useGatewayConfig, useGatewayUpdate } from '../../lib/queries/command-center';
import { Globe, RefreshCw, CheckCircle, Mail, MessageSquare, Monitor, Terminal } from 'lucide-react';

export default function GatewayHub() {
    const { data, isLoading } = useGatewayConfig();

    if (isLoading) return <div className="text-slate-500 p-12">Loading Gateway status...</div>;

    return (
        <div className="space-y-8">
            <div>
                <h2 className="text-2xl font-bold text-white flex items-center gap-3">
                    <Globe className="w-6 h-6 text-indigo-400" />
                    Universal Gateway
                </h2>
                <p className="text-slate-400 mt-2">Connect your agent to the outside world. Configure API keys for each channel plugin.</p>
            </div>

            <div className="space-y-4">
                {data?.channels.map((channel) => (
                    <ChannelRow key={channel.channel_id} channel={channel} />
                ))}
            </div>
        </div>
    );
}

function ChannelRow({ channel }: any) {
    const updateMutation = useGatewayUpdate();
    const [isExpanded, setIsExpanded] = useState(false);

    // Icon mapping
    const Icons: any = {
        email: Mail,
        sms: MessageSquare,
        whatsapp: MessageSquare,
        terminal: Terminal
    };
    const Icon = Icons[channel.channel_id] || Monitor;

    return (
        <div className="bg-slate-950/40 border border-slate-800 rounded-2xl overflow-hidden transition-all hover:border-slate-700">
            <div
                className="p-6 flex items-center justify-between cursor-pointer"
                onClick={() => setIsExpanded(!isExpanded)}
            >
                <div className="flex items-center gap-4">
                    <div className={`p-3 rounded-xl ${channel.is_active ? 'bg-indigo-500/10 text-indigo-400' : 'bg-slate-900 text-slate-600'}`}>
                        <Icon className="w-5 h-5" />
                    </div>
                    <div>
                        <h4 className="font-bold text-white text-lg tracking-tight capitalize">{channel.provider}</h4>
                        <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">{channel.channel_id}</p>
                    </div>
                </div>

                <div className="flex items-center gap-6">
                    <div className="flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full ${channel.is_active ? 'bg-emerald-500 animate-pulse' : 'bg-slate-700'}`} />
                        <span className={`text-xs font-bold uppercase tracking-widest ${channel.is_active ? 'text-emerald-500' : 'text-slate-600'}`}>
                            {channel.status}
                        </span>
                    </div>

                    <button className="text-xs font-bold text-slate-400 hover:text-white uppercase tracking-widest">
                        {isExpanded ? 'Close' : 'Configure'}
                    </button>
                </div>
            </div>

            {/* Config Panel */}
            {isExpanded && (
                <div className="px-6 pb-6 pt-0 animate-in slide-in-from-top-2">
                    <div className="p-6 bg-slate-900/50 rounded-xl border border-slate-800/50 space-y-4">
                        <div>
                            <label className="block text-[10px] font-black uppercase text-slate-500 tracking-widest mb-2">
                                API Key / Connection String
                            </label>
                            <input
                                type="password"
                                placeholder="sk_live_..."
                                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-sm text-white focus:outline-none focus:border-indigo-500 transition-colors"
                            />
                        </div>
                        <div className="flex justify-end pt-2">
                            <button className="bg-white text-black px-6 py-2 rounded-lg text-xs font-bold uppercase tracking-widest hover:bg-slate-200">
                                Save Credentials
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

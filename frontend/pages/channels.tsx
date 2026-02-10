import React, { useState, useEffect } from 'react';
import Head from 'next/head';
import { Globe, Store, ShoppingBag, CheckCircle2, AlertCircle, ExternalLink, Settings, Plus } from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8081';

const CHANNELS = [
    { id: 'ebay', name: 'eBay', icon: ShoppingBag, description: 'Reach 130M+ buyers globally.' },
    { id: 'amazon', name: 'Amazon', icon: Globe, description: 'Sell on the world\'s largest marketplace.' },
];

export default function ChannelsPage() {
    const [enabledChannels, setEnabledChannels] = useState<string[]>([]);
    const [externalEnabled, setExternalEnabled] = useState(true);
    const [loading, setLoading] = useState(false); // Ideally fetch initial state
    const [connecting, setConnecting] = useState<string | null>(null);

    // Mock initial fetch
    useEffect(() => {
        // In real app: fetch merchant settings
        // setEnabledChannels(['ebay']); 
    }, []);

    const handleConnect = async (channelId: string) => {
        setConnecting(channelId);
        // Redirect to OAuth flow
        // Ideally this hits a backend endpoint to get the auth URL
        // For now, simulating
        setTimeout(() => {
            // alert(`Redirecting to ${channelId} auth...`);
            // Simulate success for demo
            setEnabledChannels(prev => [...prev, channelId]);
            setConnecting(null);
        }, 1500);

        // Real implementation:
        // window.location.href = `${API_BASE}/api/channels/${channelId}/auth`;
    };

    const toggleGlobal = () => {
        setExternalEnabled(!externalEnabled);
        // save to backend
    };

    return (
        <div className="min-h-screen bg-[#0B0E14] text-white p-8">
            <Head>
                <title>External Channels | Cephly</title>
            </Head>

            <div className="max-w-4xl mx-auto space-y-8">

                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-3xl font-extrabold tracking-tight mb-2">External Channels</h1>
                        <p className="text-slate-400">Expand your reach by listing clearance inventory on third-party marketplaces.</p>
                    </div>
                    <div className="flex items-center gap-3 bg-slate-900 border border-slate-800 rounded-lg p-2 pr-4">
                        <div
                            onClick={toggleGlobal}
                            className={`w-10 h-6 rounded-full relative cursor-pointer transition-colors ${externalEnabled ? 'bg-indigo-600' : 'bg-slate-700'}`}
                        >
                            <div className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full transition-all ${externalEnabled ? 'translate-x-4' : ''}`} />
                        </div>
                        <span className="text-sm font-bold text-slate-300">
                            {externalEnabled ? 'Global Routing Enabled' : 'Global Routing Disabled'}
                        </span>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {CHANNELS.map(channel => {
                        const isConnected = enabledChannels.includes(channel.id);
                        return (
                            <div key={channel.id} className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6 relative overflow-hidden group hover:border-slate-700 transition-all">
                                <div className="flex items-start justify-between mb-4">
                                    <div className="p-3 bg-slate-800 rounded-xl">
                                        <channel.icon className="w-8 h-8 text-indigo-400" />
                                    </div>
                                    {isConnected ? (
                                        <div className="flex items-center gap-2 px-3 py-1 bg-green-500/10 border border-green-500/20 rounded-full">
                                            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                                            <span className="text-xs font-bold text-green-400 uppercase tracking-wide">Connected</span>
                                        </div>
                                    ) : (
                                        <div className="flex items-center gap-2 px-3 py-1 bg-slate-800 border border-slate-700 rounded-full">
                                            <div className="w-2 h-2 bg-slate-500 rounded-full" />
                                            <span className="text-xs font-bold text-slate-500 uppercase tracking-wide">Not Connected</span>
                                        </div>
                                    )}
                                </div>

                                <h3 className="text-xl font-bold mb-2">{channel.name}</h3>
                                <p className="text-slate-400 text-sm mb-6 h-10">{channel.description}</p>

                                {isConnected ? (
                                    <div className="flex items-center gap-3">
                                        <button className="flex-1 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm font-bold transition-all border border-slate-700">
                                            Manage Settings
                                        </button>
                                        <button className="p-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-lg border border-red-500/20 transition-all">
                                            <Settings className="w-5 h-5" />
                                        </button>
                                    </div>
                                ) : (
                                    <button
                                        onClick={() => handleConnect(channel.id)}
                                        disabled={connecting === channel.id || !externalEnabled}
                                        className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl font-bold transition-all shadow-lg shadow-indigo-600/20 flex items-center justify-center gap-2"
                                    >
                                        {connecting === channel.id ? (
                                            <>Connecting...</>
                                        ) : (
                                            <>
                                                Connect {channel.name}
                                                <ExternalLink className="w-4 h-4" />
                                            </>
                                        )}
                                    </button>
                                )}
                            </div>
                        );
                    })}
                </div>

                {/* Routing Rules Preview */}
                <div className="bg-slate-900/30 border border-slate-800 rounded-2xl p-6">
                    <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                        <Settings className="w-5 h-5 text-slate-400" />
                        Routing Preferences
                    </h3>

                    <div className="space-y-4">
                        <div className="flex items-center justify-between p-4 bg-slate-950/50 rounded-xl border border-slate-800">
                            <div>
                                <h4 className="font-bold text-slate-300">Excluded Categories</h4>
                                <p className="text-xs text-slate-500">Products in these categories will never be listed externally.</p>
                            </div>
                            <button className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-xs font-bold transition-all border border-slate-700 flex items-center gap-2">
                                <Plus className="w-3 h-3" />
                                Add Category
                            </button>
                        </div>

                        {/* Visual of logic */}
                        <div className="p-4 rounded-xl border border-slate-800 bg-slate-950/30 font-mono text-xs text-slate-500 space-y-1">
                            <p className="text-slate-400 font-bold mb-2">Current Logic:</p>
                            <p>IF stock &lt;= 20 AND stale &lt; 14d THEN <span className="text-indigo-400">Store Only</span></p>
                            <p>IF stock &gt; 20 AND stale &gt; 14d THEN <span className="text-emerald-400">Store + External (40%)</span></p>
                            <p>IF stock &gt; 50 AND stale &gt; 30d THEN <span className="text-amber-400">Store + External (Priority 70%)</span></p>
                        </div>
                    </div>
                </div>

            </div>
        </div>
    );
}

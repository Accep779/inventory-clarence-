import React from 'react';
import { useDigestQueue, useDigestFlush } from '../../lib/queries/command-center';
import { Inbox, Shield, Trash2, Send } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

export default function DigestStatus() {
    const { data, isLoading } = useDigestQueue();
    const flushMutation = useDigestFlush();

    if (isLoading) return <div className="text-slate-500 p-12">Checking Anti-Fatigue status...</div>;

    return (
        <div className="space-y-8">
            <div className="flex justify-between items-end">
                <div>
                    <h2 className="text-2xl font-bold text-white flex items-center gap-3">
                        <Shield className="w-6 h-6 text-emerald-400" />
                        Anti-Fatigue Shield
                    </h2>
                    <p className="text-slate-400 mt-2">
                        We intercept low-priority notifications to prevent burnout.
                        They are batched here until the daily briefing.
                    </p>
                </div>

                {(data?.queue_size || 0) > 0 && (
                    <button
                        onClick={() => flushMutation.mutate()}
                        disabled={flushMutation.isPending}
                        className="bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-3 rounded-xl text-xs font-bold uppercase tracking-widest flex items-center gap-2 transition-all shadow-lg shadow-indigo-600/20"
                    >
                        <Send className="w-4 h-4" />
                        {flushMutation.isPending ? 'Flushing...' : 'Send Digest Now'}
                    </button>
                )}
            </div>

            <div className="bg-slate-950 border border-slate-800 rounded-3xl overflow-hidden min-h-[300px]">
                {/* Stats Header */}
                <div className="bg-slate-900/50 px-8 py-4 border-b border-slate-800 flex items-center gap-8">
                    <div className="flex items-center gap-3">
                        <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                        <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">Shield Active</span>
                    </div>
                    <div className="h-4 w-px bg-slate-800" />
                    <span className="text-xs font-bold text-white uppercase tracking-widest">
                        {data?.queue_size || 0} Messages Intercepted
                    </span>
                </div>

                {/* Queue List */}
                <div className="divide-y divide-slate-800/50">
                    {data?.items.map((item: any) => (
                        <div key={item.id} className="px-8 py-5 hover:bg-white/[0.02] transition-colors flex items-start gap-6 group">
                            <div className="mt-1 p-2 bg-slate-900 rounded-lg text-slate-500 group-hover:text-amber-400 transition-colors">
                                <Inbox className="w-4 h-4" />
                            </div>
                            <div className="flex-1">
                                <div className="flex items-center gap-3 mb-1">
                                    <span className="px-2 py-0.5 rounded bg-slate-800 text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                                        {item.priority} priority
                                    </span>
                                    <span className="text-[10px] font-bold text-slate-600 uppercase tracking-widest">
                                        • {item.topic || 'General'}
                                    </span>
                                    <span className="text-[10px] font-bold text-slate-600 ml-auto uppercase tracking-widest">
                                        {formatDistanceToNow(new Date(item.created_at), { addSuffix: true })}
                                    </span>
                                </div>
                                <p className="text-sm font-medium text-slate-300 line-clamp-1">
                                    {item.content}
                                </p>
                            </div>
                        </div>
                    ))}

                    {(!data?.items || data.items.length === 0) && (
                        <div className="p-20 flex flex-col items-center justify-center text-slate-600">
                            <Shield className="w-12 h-12 mb-4 opacity-20" />
                            <p className="font-medium">All quiet. No pending interruptions.</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

import React, { useState } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { 
  Search, 
  Filter, 
  Download, 
  ArrowUpRight, 
  AlertTriangle,
  History,
  Archive,
  BarChart2,
  MoreVertical,
  ChevronRight,
  Zap,
  Tag
} from 'lucide-react';
import api from '@/lib/api';
import { useAuth } from '@/lib/context/MerchantContext';
import { motion } from 'framer-motion';


export default function InventoryHub() {
  const [searchTerm, setSearchTerm] = useState('');
  const { merchantId } = useAuth();
  const [products, setProducts] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [deadCount, setDeadCount] = useState(0);
  const [loading, setLoading] = useState(true);

  React.useEffect(() => {
    if (!merchantId) return;

    const fetchProducts = async () => {
      try {
        const res = await api.get('/products', {
          params: { limit: 50, offset: 0 }
        });
        setProducts(res.data.products);
        setTotal(res.data.total);
        setDeadCount(res.data.dead_stock_count);
      } catch (err) {
        console.error('Failed to fetch products:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchProducts();
  }, [merchantId]);

  return (
    <AppShell title="Inventory Hub">
       <div className="flex flex-col gap-8">
          {/* HEADER */}
          <div className="flex justify-between items-end">
             <div>
                <h1 className="text-4xl font-extrabold tracking-tight mb-2">Inventory Hub</h1>
                <p className="text-slate-400 font-medium tracking-tight">Systematic monitoring of <span className="text-white">{total.toLocaleString()} active SKUs</span> across all channels.</p>
             </div>
             <div className="flex gap-3">
                <button className="px-5 py-2.5 bg-slate-800/50 hover:bg-slate-800 rounded-xl border border-slate-700/50 text-xs font-black uppercase tracking-widest transition-all flex items-center gap-2">
                   <Download className="w-4 h-4" /> Export Report
                </button>
                <button className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 rounded-xl shadow-lg shadow-indigo-600/20 text-xs font-black uppercase tracking-widest transition-all flex items-center gap-2">
                   <Zap className="w-4 h-4" /> Run Audit
                </button>
             </div>
          </div>

          {/* QUICK STATS */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
             <InventoryStat label="Total SKUs" value={total.toLocaleString()} sub="Catalog size" icon={BarChart2} color="indigo" />
             <InventoryStat label="Dead Stock" value={`${((deadCount / (total || 1)) * 100).toFixed(1)}%`} sub={`${deadCount} items at risk`} icon={AlertTriangle} color="pink" />
             <InventoryStat label="Avg. Velocity" value="0.52" sub="Daily turn rate" icon={ArrowUpRight} color="emerald" />
             <InventoryStat label="Audit Status" value="Healthy" sub="System Online" icon={History} color="amber" />
          </div>

          {/* FILTER & TABLE SECTION */}
          <div className="bg-slate-900/40 backdrop-blur-xl border border-slate-800/60 rounded-[32px] overflow-hidden flex flex-col shadow-2xl">
             <div className="p-6 border-b border-slate-800/60 flex items-center justify-between bg-slate-900/20">
                <div className="flex items-center gap-4 bg-slate-950/50 border border-slate-800/50 rounded-2xl px-4 py-2 w-96 transition-all focus-within:ring-2 focus-within:ring-indigo-500/50 shadow-inner">
                   <Search className="w-4 h-4 text-slate-500" />
                   <input 
                     placeholder="Filter by SKU, Title, or Category..." 
                     className="bg-transparent border-none outline-none text-sm text-slate-200 placeholder:text-slate-600 w-full"
                     value={searchTerm}
                     onChange={(e) => setSearchTerm(e.target.value)}
                   />
                </div>
                <div className="flex gap-2">
                   <button className="p-2.5 rounded-xl border border-slate-800 bg-slate-900/50 hover:bg-slate-800 text-slate-400 hover:text-white transition-all">
                      <Filter className="w-5 h-5" />
                   </button>
                   <div className="h-10 w-[1px] bg-slate-800 mx-2" />
                   <div className="flex gap-2">
                      {['ALL Products', 'Dead Stock', 'Trending'].map((t) => (
                        <button key={t} className={`px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${t === 'ALL Products' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20' : 'text-slate-500 hover:text-white hover:bg-slate-800'}`}>
                           {t}
                        </button>
                      ))}
                   </div>
                </div>
             </div>

             <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                   <thead>
                      <tr className="border-b border-slate-800/60 transition-colors">
                         <th className="px-8 py-5 text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Product Info</th>
                         <th className="px-8 py-5 text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 text-center">Velocity</th>
                         <th className="px-8 py-5 text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 text-center">Stock Level</th>
                         <th className="px-8 py-5 text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 text-center">Capital Value</th>
                         <th className="px-8 py-5 text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 text-center">Intelligence Status</th>
                         <th className="px-8 py-5 text-[10px] font-black uppercase tracking-[0.2em] text-slate-500"></th>
                      </tr>
                   </thead>
                   <tbody className="divide-y divide-slate-800/40">
                      {products.map((p) => (
                        <tr key={p.id} className="group hover:bg-slate-800/30 transition-all cursor-pointer">
                           <td className="px-8 py-6">
                              <div className="flex items-center gap-4">
                                 <div className="w-12 h-12 rounded-xl bg-slate-800 border border-slate-700/50 flex items-center justify-center p-2 group-hover:border-slate-500 transition-colors">
                                    <Tag className="w-6 h-6 text-slate-500" />
                                 </div>
                                 <div>
                                    <p className="font-bold text-slate-200 group-hover:text-white transition-colors tracking-tight">{p.title}</p>
                                    <p className="text-[10px] font-black uppercase tracking-widest text-slate-500/80">{p.sku}</p>
                                 </div>
                              </div>
                           </td>
                           <td className="px-8 py-6">
                              <div className="flex flex-col items-center gap-2">
                                 <span className={`text-sm font-black ${p.velocity_score < 0.2 ? 'text-pink-500' : 'text-emerald-500'}`}>{p.velocity_score?.toFixed(2) || '0.00'}</span>
                                 <div className="w-20 h-1 hidden md:block bg-slate-800 rounded-full overflow-hidden">
                                    <div className={`h-full rounded-full ${p.velocity_score < 0.2 ? 'bg-pink-500' : 'bg-emerald-500'}`} style={{ width: `${(p.velocity_score || 0) * 100}%` }} />
                                 </div>
                              </div>
                           </td>
                           <td className="px-8 py-6 text-center">
                              <span className="text-sm font-bold text-slate-300">{p.total_inventory} Units</span>
                           </td>
                           <td className="px-8 py-6 text-center font-black text-slate-200">
                              ${(p.inventory_value || 0).toLocaleString()}
                           </td>
                           <td className="px-8 py-6 text-center">
                              <div className="flex justify-center">
                                 <div className={`flex items-center gap-2 px-3 py-1 rounded-lg border text-[10px] font-black uppercase tracking-widest whitespace-nowrap ${
                                    p.dead_stock_severity === 'critical' ? 'bg-pink-500/10 border-pink-500/30 text-pink-500' :
                                    p.dead_stock_severity === 'high' ? 'bg-amber-500/10 border-amber-500/30 text-amber-500' :
                                    p.dead_stock_severity === 'moderate' ? 'bg-indigo-500/10 border-indigo-500/30 text-indigo-500' :
                                    'bg-slate-800/50 border-slate-700 text-slate-500'
                                 }`}>
                                    {p.dead_stock_severity || 'Healthy'} Priority
                                 </div>
                              </div>
                           </td>
                           <td className="px-8 py-6 text-right">
                              <button className="p-2 rounded-lg hover:bg-slate-700 text-slate-500 hover:text-white transition-all">
                                 <MoreVertical className="w-5 h-5" />
                              </button>
                           </td>
                        </tr>
                      ))}
                   </tbody>
                </table>
             </div>
             
             <div className="p-6 border-t border-slate-800/60 flex items-center justify-between bg-slate-900/20 text-xs font-bold text-slate-500">
                <span>Showing {products.length} of {total.toLocaleString()} active items</span>
                <div className="flex gap-2">
                   <button className="px-4 py-2 rounded-lg border border-slate-800 bg-slate-900/50 hover:bg-slate-800 disabled:opacity-50">Previous</button>
                   <button className="px-4 py-2 rounded-lg border border-slate-800 bg-slate-900/50 hover:bg-slate-800">Next</button>
                </div>
             </div>
          </div>
       </div>
    </AppShell>
  );
}

function InventoryStat({ label, value, sub, icon: Icon, color }: any) {
  const colors: any = {
    indigo: 'text-indigo-400 border-indigo-500/20 bg-indigo-500/5',
    pink: 'text-pink-400 border-pink-500/20 bg-pink-500/5',
    emerald: 'text-emerald-400 border-emerald-500/20 bg-emerald-500/5',
    amber: 'text-amber-400 border-amber-500/20 bg-amber-500/5',
  };

  return (
     <div className="bg-slate-900/40 backdrop-blur-xl border border-slate-800/60 p-5 rounded-[24px] flex items-center gap-5 hover:border-slate-700 transition-all cursor-default">
        <div className={`p-4 rounded-2xl border ${colors[color]} flex items-center justify-center`}>
           <Icon className="w-6 h-6" />
        </div>
        <div>
           <p className="text-[10px] font-black uppercase text-slate-500 tracking-widest mb-0.5">{label}</p>
           <p className="text-xl font-black text-white">{value}</p>
           <p className="text-[10px] text-slate-500 font-bold uppercase tracking-tight">{sub}</p>
        </div>
     </div>
  );
}

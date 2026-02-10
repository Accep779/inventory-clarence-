import React, { useState, useRef } from 'react';
import { Fingerprint, Sparkles, Upload, FileText, DollarSign, Globe, CheckCircle, AlertCircle, Download, RefreshCw } from 'lucide-react';
import { useMerchant } from '@/lib/context/MerchantContext';
import { LoadingOverlay } from '@/components/ui/LoadingOverlay';

interface StoreDNAProps {
  data: any;
  onChange: (key: string, value: any) => void;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8081';

export default function StoreDNA({ data, onChange }: StoreDNAProps) {
  // Get merchant ID from context
  const { merchantId } = useMerchant();
  
  // Upload states
  const [brandGuideStatus, setBrandGuideStatus] = useState<'idle' | 'uploading' | 'success' | 'error'>('idle');
  const [floorPricingStatus, setFloorPricingStatus] = useState<'idle' | 'uploading' | 'success' | 'error'>('idle');
  const [floorPricingResult, setFloorPricingResult] = useState<any>(null);
  const [scrapeStatus, setScrapeStatus] = useState<'idle' | 'scraping' | 'success' | 'error'>('idle');
  const [storeUrl, setStoreUrl] = useState('');
  
  const brandGuideRef = useRef<HTMLInputElement>(null);
  const floorPricingRef = useRef<HTMLInputElement>(null);

  const handleBrandGuideUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    setBrandGuideStatus('uploading');
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const res = await fetch(`${API_BASE}/api/dna/brand-guide?merchant_id=${merchantId}`, {
        method: 'POST',
        body: formData
      });
      if (res.ok) {
        setBrandGuideStatus('success');
        setTimeout(() => setBrandGuideStatus('idle'), 3000);
      } else {
        setBrandGuideStatus('error');
      }
    } catch {
      setBrandGuideStatus('error');
    }
  };

  const handleFloorPricingUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    setFloorPricingStatus('uploading');
    setFloorPricingResult(null);
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const res = await fetch(`${API_BASE}/api/dna/floor-pricing?merchant_id=${merchantId}`, {
        method: 'POST',
        body: formData
      });
      const result = await res.json();
      setFloorPricingResult(result);
      if (res.ok && result.status !== 'FAILED') {
        setFloorPricingStatus('success');
      } else {
        setFloorPricingStatus('error');
      }
    } catch {
      setFloorPricingStatus('error');
    }
  };

  const handleScrapeStore = async () => {
    if (!storeUrl) return;
    
    setScrapeStatus('scraping');
    try {
      const res = await fetch(`${API_BASE}/api/dna/scrape?merchant_id=${merchantId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ store_url: storeUrl })
      });
      if (res.ok) {
        setScrapeStatus('success');
        setTimeout(() => setScrapeStatus('idle'), 3000);
      } else {
        setScrapeStatus('error');
      }
    } catch {
      setScrapeStatus('error');
    }
  };

  const downloadTemplate = () => {
    const template = 'sku,cost_price,min_margin_pct,floor_price,liquidation_mode,notes\nSKU-001,25.00,20,,false,Regular product\nSKU-002,15.00,15,18.00,true,Clearance item';
    const blob = new Blob([template], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'floor_pricing_template.csv';
    a.click();
  };

  return (
    <div className="space-y-10 relative">
       {/* Global Overlay for critical blocking actions */}
       <LoadingOverlay 
         isLoading={scrapeStatus === 'scraping'} 
         message="Analyzing Store DNA" 
         subMessage="Extracting brand signals & tone..."
       />
       <LoadingOverlay 
         isLoading={brandGuideStatus === 'uploading'} 
         message="Ingesting Brand Guide" 
         subMessage="Vectorizing identity context..." 
       />

       {/* HEADER */}
       <div className="flex items-center gap-3">
          <div className="p-2 bg-indigo-500/10 rounded-xl">
             <Fingerprint className="w-5 h-5 text-indigo-400" />
          </div>
          <h2 className="text-2xl font-bold text-white tracking-tight">Store DNA</h2>
       </div>

       {/* STORE INTELLIGENCE - First, to populate brand data */}
       <div className="p-6 bg-slate-950/40 border border-slate-800/60 rounded-2xl space-y-4 relative overflow-hidden">
         <div className="flex items-center gap-3">
           <Globe className="w-5 h-5 text-cyan-400" />
           <div>
             <p className="text-sm font-bold text-white">Store Intelligence</p>
             <p className="text-[10px] text-slate-500">Enter your store URL to auto-extract brand context and voice</p>
           </div>
         </div>
         <div className="flex gap-3 relative z-10">
           <input 
             type="url"
             value={storeUrl}
             onChange={(e) => setStoreUrl(e.target.value)}
             placeholder="https://your-store.myshopify.com"
             className="flex-1 bg-[hsl(var(--bg-input))] border border-[hsl(var(--border-panel))] rounded-xl px-4 py-3 text-sm text-slate-200 outline-none focus:ring-2 focus:ring-cyan-500/50"
           />
           <button 
             onClick={handleScrapeStore}
             disabled={scrapeStatus === 'scraping' || !storeUrl}
             className="px-6 py-3 bg-cyan-600/20 border border-cyan-500/30 rounded-xl text-cyan-400 font-bold text-xs uppercase tracking-widest hover:bg-cyan-600/30 transition-all disabled:opacity-50 flex items-center gap-2"
           >
             <Globe className="w-3 h-3" /> Analyze
           </button>
         </div>
         {scrapeStatus === 'success' && (
           <div className="p-3 bg-emerald-500/10 rounded-lg text-xs text-emerald-400 animate-in fade-in slide-in-from-top-2">
             ✓ Store analyzed! Brand signals extracted and saved.
           </div>
         )}
       </div>

      {/* BRAND VOICE - Auto-populated from analysis */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
         <div className="space-y-3">
            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block">Brand Voice & Persona</label>
            <div className="w-full bg-[hsl(var(--bg-input))] border border-[hsl(var(--border-panel))] rounded-xl px-4 py-3">
               {data.brandTone ? (
                  <p className="text-sm text-slate-200">{data.brandTone}</p>
               ) : (
                  <p className="text-sm text-slate-600 italic">Analyze your store URL above to detect brand voice...</p>
               )}
            </div>
            <p className="text-[9px] text-slate-500 leading-relaxed italic">
               Auto-detected from your store URL and brand guide.
            </p>
         </div>

         {/* DECISION AUTONOMY */}
         <div className="space-y-4">
            <div className="flex justify-between items-center">
               <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Decision Autonomy</label>
               <span className="text-xs font-bold text-indigo-400">{data.autonomy}%</span>
            </div>
            <input 
               type="range" 
               min="0" 
               max="100" 
               value={data.autonomy}
               onChange={(e) => onChange('autonomy', parseInt(e.target.value))}
               className="w-full h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
            />
            <p className="text-[9px] text-slate-500 leading-relaxed italic">
               Controls the agent's threshold for seeking human approval before execution.
            </p>
         </div>
      </div>

      {/* CORE IDENTITY */}
      <div className="space-y-3">
         <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block">Core Identity Prompt</label>
         <textarea 
            value={data.identityDescription}
            onChange={(e) => onChange('identityDescription', e.target.value)}
            rows={4}
            placeholder="Describe the soul of your store for the agents..."
            className="w-full bg-[hsl(var(--bg-input))] border border-[hsl(var(--border-panel))] rounded-2xl px-5 py-4 text-sm text-slate-300 outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all resize-none placeholder:text-slate-700"
         />
         <div className="flex items-center gap-2 px-1">
            <Sparkles className="w-3 h-3 text-indigo-400" />
            <span className="text-[9px] font-bold text-slate-600 uppercase tracking-widest">This context influences every generated word</span>
         </div>
      </div>

      {/* DIVIDER */}
      <div className="border-t border-white/5 pt-8">
        <h3 className="text-lg font-bold text-white mb-6 flex items-center gap-2">
          <Upload className="w-4 h-4 text-indigo-400" />
          Advanced Intelligence
        </h3>
      </div>

      {/* BRAND GUIDE UPLOAD */}
      <div className="p-6 bg-slate-950/40 border border-slate-800/60 rounded-2xl space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <FileText className="w-5 h-5 text-purple-400" />
            <div>
              <p className="text-sm font-bold text-white">Brand Guide</p>
              <p className="text-[10px] text-slate-500">Upload a .md file with your brand voice, tone, and guidelines</p>
            </div>
          </div>
          {brandGuideStatus === 'success' && <CheckCircle className="w-5 h-5 text-emerald-500" />}
          {brandGuideStatus === 'error' && <AlertCircle className="w-5 h-5 text-pink-500" />}
        </div>
        <input ref={brandGuideRef} type="file" accept=".md" className="hidden" onChange={handleBrandGuideUpload} />
        <button 
          onClick={() => brandGuideRef.current?.click()}
          disabled={brandGuideStatus === 'uploading'}
          className="w-full p-4 border-2 border-dashed border-slate-700 rounded-xl text-slate-500 hover:border-purple-500/50 hover:text-purple-400 transition-all text-sm font-medium"
        >
          {brandGuideStatus === 'uploading' ? 'Uploading...' : 'Click to upload brand guide (.md)'}
        </button>
      </div>

      {/* FLOOR PRICING UPLOAD */}
      <div className="p-6 bg-slate-950/40 border border-slate-800/60 rounded-2xl space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <DollarSign className="w-5 h-5 text-emerald-400" />
            <div>
              <p className="text-sm font-bold text-white">Floor Pricing</p>
              <p className="text-[10px] text-slate-500">Upload CSV with cost prices and margin thresholds per product</p>
            </div>
          </div>
          <button onClick={downloadTemplate} className="text-[10px] font-bold text-slate-500 hover:text-white uppercase tracking-widest flex items-center gap-1">
            <Download className="w-3 h-3" /> Template
          </button>
        </div>
        <input ref={floorPricingRef} type="file" accept=".csv" className="hidden" onChange={handleFloorPricingUpload} />
        <button 
          onClick={() => floorPricingRef.current?.click()}
          disabled={floorPricingStatus === 'uploading'}
          className="w-full p-4 border-2 border-dashed border-slate-700 rounded-xl text-slate-500 hover:border-emerald-500/50 hover:text-emerald-400 transition-all text-sm font-medium"
        >
          {floorPricingStatus === 'uploading' ? 'Processing...' : 'Click to upload floor pricing (.csv)'}
        </button>
        {floorPricingResult && (
          <div className={`p-3 rounded-lg text-xs ${floorPricingResult.status === 'SUCCESS' ? 'bg-emerald-500/10 text-emerald-400' : floorPricingResult.status === 'PARTIAL' ? 'bg-amber-500/10 text-amber-400' : 'bg-pink-500/10 text-pink-400'}`}>
            {floorPricingResult.records_created > 0 && <p>✓ {floorPricingResult.records_created} products imported</p>}
            {floorPricingResult.total_errors > 0 && <p>⚠ {floorPricingResult.total_errors} errors</p>}
          </div>
        )}
      </div>
    </div>
  );
}

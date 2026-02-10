import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/router';
import { useMerchant } from '@/lib/context/MerchantContext';
import { Package, DollarSign, AlertTriangle, ArrowRight, Loader2, Scan } from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8081';

// Helper for currency formatting
const formatCurrency = (amount: number, currency: string = 'USD') => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
};

interface DeadStockProduct {
  title: string;
  price: number;
  inventory: number;
  stuck_value: number;
  days_since_last_sale: number;
  velocity_score: number;
  severity: string;
  image_url?: string;
}

interface RunningTotal {
  dead_stock_count: number;
  total_stuck_value: number;
  products_scanned: number;
  total_products: number;
}

export default function ScanPage() {
  const router = useRouter();
  const { merchantId, setMerchantId } = useMerchant();
  
  // Scanning immediately starts - OAuth already completed
  const [status, setStatus] = useState<'starting' | 'scanning' | 'complete' | 'error'>('starting');
  const [products, setProducts] = useState<DeadStockProduct[]>([]);
  const [runningTotal, setRunningTotal] = useState<RunningTotal>({
    dead_stock_count: 0,
    total_stuck_value: 0,
    products_scanned: 0,
    total_products: 0
  });
  const [summary, setSummary] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  
  const feedRef = useRef<HTMLDivElement>(null);
  const scanStarted = useRef(false);

  // Check for session/cookie on mount
  useEffect(() => {
    const verifySession = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/auth/me`, {
          credentials: 'include', // Send HttpOnly cookie
        });
        
        if (res.ok) {
          const merchant = await res.json();
          if (merchant.id !== merchantId) {
            setMerchantId(merchant.id);
          }
        } else {
          // If unauthorized, redirect to install or show error
          console.error("Session verification failed");
          // Optional: router.push('/install');
        }
      } catch (err) {
        console.error("Auth check error:", err);
      }
    };
    
    if (!merchantId && router.isReady) {
      verifySession();
    }
  }, [router.isReady, merchantId, setMerchantId]);

  // Start scan when merchant ID is available
  useEffect(() => {
    if (merchantId && !scanStarted.current) {
      scanStarted.current = true;
      startScan();
    }
  }, [merchantId]);

  const startScan = async () => {
    if (!merchantId) return;
    
    setStatus('starting');
    
    try {
      // Start scan and get session ID
      const response = await fetch(`${API_BASE}/api/scan/quick-start?merchant_id=${merchantId}`, {
        method: 'POST',
        credentials: 'include'
      });
      
      if (!response.ok) {
        throw new Error('Failed to start scan');
      }
      
      const data = await response.json();
      const sessionId = data.session_id;
      
      // Connect to SSE stream
      const eventSource = new EventSource(`${API_BASE}/api/scan/stream/${sessionId}`);
      
      eventSource.addEventListener('connected', () => {
        setStatus('scanning');
      });
      
      eventSource.addEventListener('scan_progress', (e) => {
        const data = JSON.parse(e.data);
        setRunningTotal(prev => ({
          ...prev,
          products_scanned: data.products_scanned,
          total_products: data.total_products
        }));
        // Update status to scanning when we get first progress
        if (status === 'starting') {
          setStatus('scanning');
        }
      });
      
      eventSource.addEventListener('dead_stock_found', (e) => {
        const data = JSON.parse(e.data);
        setProducts(prev => [data.product, ...prev]);
        setRunningTotal(data.running_total);
        setStatus('scanning');
        
        // Auto-scroll to top
        if (feedRef.current) {
          feedRef.current.scrollTop = 0;
        }
      });
      
      eventSource.addEventListener('quick_scan_complete', (e) => {
        const data = JSON.parse(e.data);
        setSummary(data.summary);
        setStatus('complete');
        eventSource.close();
      });
      
      eventSource.addEventListener('error', (e: any) => {
        const data = e.data ? JSON.parse(e.data) : { error: 'Connection lost' };
        setError(data.error);
        setStatus('error');
        eventSource.close();
      });
      
      eventSource.onerror = () => {
        if (status !== 'complete') {
          setError('Scan interrupted. Please refresh.');
          setStatus('error');
        }
        eventSource.close();
      };
      
    } catch (err: any) {
      setError(err.message);
      setStatus('error');
    }
  };

  const continueToDashboard = () => {
    router.push('/');
  };

  return (
    <div className="min-h-screen bg-[#0B0E14] text-white">
      {/* Header */}
      <div className="sticky top-0 z-20 bg-[#0B0E14]/90 backdrop-blur-xl border-b border-slate-800/50 px-8 py-6">
        <div className="max-w-4xl mx-auto">
          <RunningTotalDisplay 
            total={runningTotal.total_stuck_value} 
            count={runningTotal.dead_stock_count}
            scanned={runningTotal.products_scanned}
            totalProducts={runningTotal.total_products}
            isScanning={status === 'scanning' || status === 'starting'}
          />
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-4xl mx-auto px-8 py-8">
        {status === 'starting' ? (
          <div className="flex flex-col items-center justify-center py-20">
            <div className="relative">
              <Scan className="w-16 h-16 text-indigo-500 animate-pulse" />
              <div className="absolute inset-0 animate-ping">
                <Scan className="w-16 h-16 text-indigo-500 opacity-20" />
              </div>
            </div>
            <p className="text-slate-300 text-xl font-bold mt-6">Scanning Your Inventory</p>
            <p className="text-slate-500 mt-2">Analyzing products for dead stock...</p>
          </div>
        ) : status === 'error' ? (
          <div className="flex flex-col items-center justify-center py-20">
            <AlertTriangle className="w-12 h-12 text-red-500 mb-4" />
            <p className="text-red-400 text-lg mb-4">{error}</p>
            <button 
              onClick={() => {
                scanStarted.current = false;
                startScan();
              }}
              className="px-6 py-3 bg-indigo-600 rounded-xl hover:bg-indigo-500 transition-colors"
            >
              Try Again
            </button>
          </div>
        ) : (
          <>
            {/* Product Feed */}
            <div ref={feedRef} className="space-y-4">
              {products.map((product, i) => (
                <DeadStockCard 
                  key={i} 
                  product={product} 
                  isNew={i === 0 && status === 'scanning'} 
                />
              ))}
              
              {products.length === 0 && status === 'scanning' && (
                <div className="text-center py-12">
                  <Package className="w-12 h-12 text-slate-600 mx-auto mb-4 animate-pulse" />
                  <p className="text-slate-500">Analyzing products...</p>
                  <p className="text-slate-600 text-sm mt-2">Dead stock products will appear here</p>
                </div>
              )}
            </div>

            {/* Scan Complete Modal */}
            {status === 'complete' && summary && (
              <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
                <div className="bg-slate-900 border border-slate-700 rounded-3xl p-8 max-w-lg w-full">
                  <div className="text-center">
                    <div className="w-16 h-16 rounded-full bg-emerald-500/20 flex items-center justify-center mx-auto mb-6">
                      <DollarSign className="w-8 h-8 text-emerald-400" />
                    </div>
                    
                    <h2 className="text-2xl font-bold mb-2">Quick Scan Complete</h2>
                    
                    <p className="text-4xl font-black text-indigo-400 mb-2">
                      {formatCurrency(summary.total_stuck_value)}
                    </p>
                    <p className="text-slate-400 mb-6">
                      stuck in {summary.dead_stock_count} dead products
                    </p>
                    
                    {summary.remaining_products > 0 && (
                      <p className="text-sm text-slate-500 mb-6 bg-slate-800/50 rounded-xl p-4">
                        You have <span className="text-white font-bold">{summary.remaining_products}</span> more products to scan.
                        This could reveal even more stuck capital.
                      </p>
                    )}
                    
                    <button
                      onClick={continueToDashboard}
                      className="w-full py-4 bg-indigo-600 hover:bg-indigo-500 rounded-xl font-bold text-lg flex items-center justify-center gap-2 transition-colors"
                    >
                      Continue to Dashboard
                      <ArrowRight className="w-5 h-5" />
                    </button>
                    
                    <p className="text-xs text-slate-600 mt-4">
                      Full scan will continue in the background
                    </p>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}


function RunningTotalDisplay({ 
  total, 
  count, 
  scanned, 
  totalProducts, 
  isScanning 
}: { 
  total: number; 
  count: number; 
  scanned: number;
  totalProducts: number;
  isScanning: boolean;
}) {
  const [displayTotal, setDisplayTotal] = useState(0);
  
  // Animate counter
  useEffect(() => {
    const duration = 500;
    const start = displayTotal;
    const end = total;
    const startTime = Date.now();
    
    const animate = () => {
      const now = Date.now();
      const progress = Math.min((now - startTime) / duration, 1);
      const easeOut = 1 - Math.pow(1 - progress, 3);
      setDisplayTotal(Math.floor(start + (end - start) * easeOut));
      
      if (progress < 1) {
        requestAnimationFrame(animate);
      }
    };
    
    animate();
  }, [total]);

  return (
    <div className="text-center">
      <div className="flex items-center justify-center gap-2 mb-2">
        <DollarSign className="w-6 h-6 text-pink-500" />
        <span className="text-sm font-bold text-slate-400 uppercase tracking-widest">
          Stuck Capital Found
        </span>
        {isScanning && (
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
        )}
      </div>
      
      <p className="text-5xl font-black text-white mb-2">
        {formatCurrency(displayTotal)}
      </p>
      
      <p className="text-sm text-slate-500">
        {count} dead products found
        {isScanning && scanned > 0 && ` • Scanning ${scanned}/${totalProducts}...`}
      </p>
    </div>
  );
}


function DeadStockCard({ product, isNew }: { product: DeadStockProduct; isNew: boolean }) {
  const severityColors: Record<string, string> = {
    critical: 'border-red-500/50 bg-red-500/5',
    high: 'border-orange-500/50 bg-orange-500/5',
    moderate: 'border-yellow-500/50 bg-yellow-500/5',
    low: 'border-slate-500/50 bg-slate-500/5'
  };

  return (
    <div 
      className={`
        p-5 rounded-2xl border transition-all duration-300
        ${severityColors[product.severity] || severityColors.low}
        ${isNew ? 'ring-2 ring-indigo-500 ring-opacity-50 animate-pulse' : ''}
      `}
    >
      <div className="flex gap-4">
        {product.image_url && (
          <img 
            src={product.image_url} 
            alt={product.title}
            className="w-16 h-16 rounded-xl object-cover bg-slate-800"
          />
        )}
        
        <div className="flex-1">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="font-bold text-white">{product.title}</h3>
              <p className="text-sm text-slate-400">
                {formatCurrency(product.price)} × {product.inventory} units
              </p>
            </div>
            
            <div className="text-right">
              <p className="text-lg font-bold text-pink-400">
                {formatCurrency(product.stuck_value)}
              </p>
              <p className="text-xs text-slate-500">stuck</p>
            </div>
          </div>
          
          <div className="flex gap-4 mt-3 text-xs">
            <span className="text-slate-500">
              Last sold: <span className="text-slate-300">{product.days_since_last_sale} days ago</span>
            </span>
            <span className={`
              px-2 py-0.5 rounded-full font-bold uppercase tracking-wide
              ${product.severity === 'critical' ? 'bg-red-500/20 text-red-400' : ''}
              ${product.severity === 'high' ? 'bg-orange-500/20 text-orange-400' : ''}
              ${product.severity === 'moderate' ? 'bg-yellow-500/20 text-yellow-400' : ''}
              ${product.severity === 'low' ? 'bg-slate-500/20 text-slate-400' : ''}
            `}>
              {product.severity}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

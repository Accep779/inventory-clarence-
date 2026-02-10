import React, { useState } from 'react';
import { useRouter } from 'next/router';
import { Zap, DollarSign, TrendingUp, Clock, ArrowRight, Store, ShoppingBag } from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8081';

export default function LandingPage() {
  const router = useRouter();
  const [storeUrl, setStoreUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleConnect = async () => {
    if (!storeUrl) {
      setError('Please enter your store URL');
      return;
    }

    setIsLoading(true);
    setError('');

    // Clean up store URL
    let shop = storeUrl.trim().toLowerCase();
    if (!shop.includes('.myshopify.com')) {
      shop = `${shop}.myshopify.com`;
    }
    shop = shop.replace('https://', '').replace('http://', '').replace('/', '');

    // Start OAuth flow
    window.location.href = `${API_BASE}/api/auth/shopify?shop=${shop}`;
  };

  return (
    <div className="min-h-screen bg-[#0B0E14] text-white overflow-hidden">
      {/* Hero Section */}
      <div className="relative">
        {/* Background gradient */}
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-900/20 via-transparent to-pink-900/20" />
        
        {/* Header */}
        <header className="relative z-10 px-8 py-6 flex items-center justify-between max-w-7xl mx-auto">
          <div className="flex items-center gap-2">
            <Zap className="w-8 h-8 text-indigo-500" />
            <span className="text-2xl font-black">Cephly</span>
          </div>
          <button 
            onClick={() => document.getElementById('signup')?.scrollIntoView({ behavior: 'smooth' })}
            className="px-6 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-full font-bold transition-colors"
          >
            Get Started
          </button>
        </header>

        {/* Hero Content */}
        <div className="relative z-10 px-8 pt-20 pb-32 max-w-7xl mx-auto text-center">
          <h1 className="text-5xl md:text-7xl font-black mb-6 leading-tight">
            Find Your
            <span className="bg-gradient-to-r from-indigo-400 to-pink-500 text-transparent bg-clip-text"> Dead Stock </span>
            <br />in 60 Seconds
          </h1>
          
          <p className="text-xl text-slate-400 max-w-2xl mx-auto mb-12">
            We'll show you <span className="text-white font-bold">EXACTLY</span> which products aren't selling 
            and how much money is stuck in your inventory.
          </p>

          {/* Stats Preview */}
          <div className="flex flex-wrap justify-center gap-8 mb-16">
            <div className="bg-slate-800/50 backdrop-blur-sm rounded-2xl p-6 border border-slate-700/50">
              <DollarSign className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
              <p className="text-3xl font-black">$47K</p>
              <p className="text-sm text-slate-400">Avg. Stuck Capital</p>
            </div>
            <div className="bg-slate-800/50 backdrop-blur-sm rounded-2xl p-6 border border-slate-700/50">
              <ShoppingBag className="w-8 h-8 text-orange-400 mx-auto mb-2" />
              <p className="text-3xl font-black">23%</p>
              <p className="text-sm text-slate-400">Avg. Dead Stock</p>
            </div>
            <div className="bg-slate-800/50 backdrop-blur-sm rounded-2xl p-6 border border-slate-700/50">
              <Clock className="w-8 h-8 text-indigo-400 mx-auto mb-2" />
              <p className="text-3xl font-black">60s</p>
              <p className="text-sm text-slate-400">Scan Time</p>
            </div>
          </div>
        </div>
      </div>

      {/* Sign Up Section */}
      <div id="signup" className="relative bg-slate-900/50 py-20 px-8">
        <div className="max-w-xl mx-auto">
          <div className="bg-slate-800/80 backdrop-blur-xl rounded-3xl p-8 border border-slate-700/50 shadow-2xl">
            <div className="text-center mb-8">
              <Store className="w-12 h-12 text-indigo-500 mx-auto mb-4" />
              <h2 className="text-2xl font-bold mb-2">Connect Your Shopify Store</h2>
              <p className="text-slate-400">Enter your store URL to start scanning</p>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Store URL
                </label>
                <div className="flex">
                  <input
                    type="text"
                    value={storeUrl}
                    onChange={(e) => {
                      setStoreUrl(e.target.value);
                      setError('');
                    }}
                    placeholder="your-store"
                    className="flex-1 px-4 py-3 bg-slate-900/50 border border-slate-600 rounded-l-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
                    onKeyDown={(e) => e.key === 'Enter' && handleConnect()}
                  />
                  <span className="px-4 py-3 bg-slate-700 text-slate-400 border border-l-0 border-slate-600 rounded-r-xl">
                    .myshopify.com
                  </span>
                </div>
                {error && (
                  <p className="text-red-400 text-sm mt-2">{error}</p>
                )}
              </div>

              <button
                onClick={handleConnect}
                disabled={isLoading}
                className="w-full py-4 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-800 rounded-xl font-bold text-lg flex items-center justify-center gap-2 transition-colors"
              >
                {isLoading ? (
                  <>
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Connecting...
                  </>
                ) : (
                  <>
                    Scan My Inventory
                    <ArrowRight className="w-5 h-5" />
                  </>
                )}
              </button>

              <p className="text-xs text-slate-500 text-center">
                Read-only access. We never modify your store data.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* How It Works */}
      <div className="py-20 px-8 max-w-5xl mx-auto">
        <h2 className="text-3xl font-bold text-center mb-16">How It Works</h2>
        
        <div className="grid md:grid-cols-3 gap-8">
          <div className="text-center">
            <div className="w-16 h-16 rounded-2xl bg-indigo-500/20 flex items-center justify-center mx-auto mb-4">
              <span className="text-2xl font-black text-indigo-400">1</span>
            </div>
            <h3 className="text-xl font-bold mb-2">Connect Store</h3>
            <p className="text-slate-400">One-click Shopify OAuth. No passwords shared.</p>
          </div>
          
          <div className="text-center">
            <div className="w-16 h-16 rounded-2xl bg-pink-500/20 flex items-center justify-center mx-auto mb-4">
              <span className="text-2xl font-black text-pink-400">2</span>
            </div>
            <h3 className="text-xl font-bold mb-2">Watch Live Scan</h3>
            <p className="text-slate-400">See dead products appear in real-time with stuck value.</p>
          </div>
          
          <div className="text-center">
            <div className="w-16 h-16 rounded-2xl bg-emerald-500/20 flex items-center justify-center mx-auto mb-4">
              <span className="text-2xl font-black text-emerald-400">3</span>
            </div>
            <h3 className="text-xl font-bold mb-2">Clear Inventory</h3>
            <p className="text-slate-400">AI-powered campaigns to liquidate dead stock profitably.</p>
          </div>
        </div>
      </div>

      {/* CTA Footer */}
      <div className="py-20 px-8 bg-gradient-to-t from-indigo-900/20 to-transparent">
        <div className="text-center max-w-2xl mx-auto">
          <h2 className="text-3xl font-bold mb-4">Stop Losing Money to Dead Stock</h2>
          <p className="text-slate-400 mb-8">
            The average Shopify store has $47,000 tied up in products that aren't selling.
            Find out how much you're losing.
          </p>
          <button
            onClick={() => document.getElementById('signup')?.scrollIntoView({ behavior: 'smooth' })}
            className="px-8 py-4 bg-indigo-600 hover:bg-indigo-500 rounded-xl font-bold text-lg inline-flex items-center gap-2 transition-colors"
          >
            Scan My Store Now
            <ArrowRight className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Footer */}
      <footer className="py-8 px-8 border-t border-slate-800">
        <div className="max-w-7xl mx-auto flex items-center justify-between text-sm text-slate-500">
          <div className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-indigo-500" />
            <span>Cephly</span>
          </div>
          <p>© 2026 Cephly. Inventory intelligence for Shopify.</p>
        </div>
      </footer>
    </div>
  );
}

import React, { useState } from 'react';
import Head from 'next/head';
import { Store, Globe, ArrowRight, CheckCircle2, ShoppingBag, Key } from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8081';

const PLATFORMS = [
  { id: 'shopify', name: 'Shopify', icon: ShoppingBag, disabled: false },
  { id: 'woocommerce', name: 'WooCommerce', icon: Store, disabled: false },
  { id: 'bigcommerce', name: 'BigCommerce', icon: Globe, disabled: false },
];

export default function InstallPage() {
  const [platform, setPlatform] = useState('shopify');
  const [shopDomain, setShopDomain] = useState('');
  const [consumerKey, setConsumerKey] = useState('');
  const [consumerSecret, setConsumerSecret] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    if (!shopDomain) {
      setError('Please enter your store URL');
      setLoading(false);
      return;
    }

    if (platform === 'woocommerce' && (!consumerKey || !consumerSecret)) {
      setError('Please enter your Consumer Key and Secret');
      setLoading(false);
      return;
    }

    try {
      // Clean domain input
      let cleanDomain = shopDomain.replace(/\/$/, '');
      if (platform === 'shopify') {
        cleanDomain = cleanDomain.replace(/^https?:\/\//, '');
        if (!cleanDomain.includes('.')) {
          cleanDomain += '.myshopify.com';
        }
      } else {
        // For Woo/BigCommerce ensure protocol
        if (!cleanDomain.startsWith('http')) {
          cleanDomain = `https://${cleanDomain}`;
        }
      }

      // Redirect to Backend Auth
      let authUrl = `${API_BASE}/api/auth/install?platform=${platform}&shop=${encodeURIComponent(cleanDomain)}`;

      // Append credentials for basic auth platforms (Woo)
      // NOTE: Sending secrets in URL query params is generally discouraged but 
      // for this simple install redirection flow it works. Ideally pass via POST or store in session first.
      // Given constraints of existing router accepting GET params for install, keeping it simple.
      if (platform === 'woocommerce') {
        authUrl += `&consumer_key=${encodeURIComponent(consumerKey)}&consumer_secret=${encodeURIComponent(consumerSecret)}`;
      }

      window.location.href = authUrl;

    } catch (err) {
      setError('Failed to initiate connection. Please try again.');
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0B0E14] text-white flex flex-col items-center justify-center p-4">
      <Head>
        <title>Connect Your Store | Cephly</title>
      </Head>

      <div className="w-full max-w-md">
        {/* Logo/Header */}
        <div className="text-center mb-10">
          <div className="w-16 h-16 bg-indigo-600 rounded-2xl mx-auto flex items-center justify-center shadow-lg shadow-indigo-500/20 mb-6">
            <Store className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight mb-2">Connect Your Store</h1>
          <p className="text-slate-400">Select your platform to activate Cephly AI</p>
        </div>

        {/* Card */}
        <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-3xl p-8 shadow-2xl">
          <form onSubmit={handleConnect} className="space-y-6">

            {/* Platform Selector */}
            <div className="space-y-3">
              <label className="text-xs font-bold text-slate-500 uppercase tracking-widest">Platform</label>
              <div className="grid grid-cols-1 gap-3">
                {PLATFORMS.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    disabled={p.disabled}
                    onClick={() => {
                      setPlatform(p.id);
                      setError('');
                    }}
                    className={`
                      flex items-center justify-between p-4 rounded-xl border transition-all text-left
                      ${platform === p.id
                        ? 'bg-indigo-600/10 border-indigo-500 ring-1 ring-indigo-500 text-white'
                        : 'bg-slate-800/50 border-slate-700 text-slate-300 hover:border-slate-600'}
                      ${p.disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
                    `}
                  >
                    <div className="flex items-center gap-3">
                      <p.icon className={`w-5 h-5 ${platform === p.id ? 'text-indigo-400' : 'text-slate-500'}`} />
                      <span className="font-bold">{p.name}</span>
                    </div>
                    {platform === p.id && (
                      <CheckCircle2 className="w-5 h-5 text-indigo-400" />
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* Shop Domain Input */}
            <div className="space-y-3">
              <label className="text-xs font-bold text-slate-500 uppercase tracking-widest">
                {platform === 'shopify' ? 'Shopify Domain' : 'Store URL'}
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={shopDomain}
                  onChange={(e) => setShopDomain(e.target.value)}
                  placeholder={platform === 'shopify' ? 'your-store.myshopify.com' : 'https://store.com'}
                  className="w-full bg-slate-950/50 border border-slate-700 rounded-xl px-4 py-3 text-white placeholder:text-slate-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all font-medium"
                />
              </div>
              {platform === 'shopify' && (
                <p className="text-xs text-slate-500 pl-1">
                  Enter your <span className="text-slate-400 font-mono">.myshopify.com</span> domain
                </p>
              )}
            </div>

            {/* WooCommerce Credentials */}
            {platform === 'woocommerce' && (
              <>
                <div className="space-y-3 animate-in fade-in slide-in-from-top-4 duration-300">
                  <label className="text-xs font-bold text-slate-500 uppercase tracking-widest">
                    Consumer Key
                  </label>
                  <div className="relative">
                    <Key className="absolute left-3 top-3.5 w-5 h-5 text-slate-500" />
                    <input
                      type="text"
                      value={consumerKey}
                      onChange={(e) => setConsumerKey(e.target.value)}
                      placeholder="ck_xxxxxxxxxxxxxxxx"
                      className="w-full bg-slate-950/50 border border-slate-700 rounded-xl pl-10 pr-4 py-3 text-white placeholder:text-slate-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all font-medium font-mono text-sm"
                    />
                  </div>
                </div>

                <div className="space-y-3 animate-in fade-in slide-in-from-top-4 duration-300 delay-75">
                  <label className="text-xs font-bold text-slate-500 uppercase tracking-widest">
                    Consumer Secret
                  </label>
                  <div className="relative">
                    <Key className="absolute left-3 top-3.5 w-5 h-5 text-slate-500" />
                    <input
                      type="password"
                      value={consumerSecret}
                      onChange={(e) => setConsumerSecret(e.target.value)}
                      placeholder="cs_xxxxxxxxxxxxxxxx"
                      className="w-full bg-slate-950/50 border border-slate-700 rounded-xl pl-10 pr-4 py-3 text-white placeholder:text-slate-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all font-medium font-mono text-sm"
                    />
                  </div>
                  <p className="text-xs text-slate-500 pl-1">
                    Found in WooCommerce Settings &gt; Advanced &gt; REST API
                  </p>
                </div>
              </>
            )}

            {error && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-400 text-center">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-4 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-70 disabled:cursor-wait rounded-xl font-bold text-lg flex items-center justify-center gap-2 transition-all shadow-lg shadow-indigo-600/20 hover:shadow-indigo-600/40 active:scale-[0.98]"
            >
              {loading ? (
                <>Connecting...</>
              ) : (
                <>
                  Connect Store
                  <ArrowRight className="w-5 h-5" />
                </>
              )}
            </button>
          </form>
        </div>

        {/* Footer */}
        <p className="text-center text-slate-600 text-sm mt-8">
          By connecting, you agree to Cephly's Terms of Service
        </p>
      </div>
    </div>
  );
}

import React, { ReactNode } from 'react';
import Head from 'next/head';
import { motion } from 'framer-motion';
import { 
  LayoutDashboard, 
  Package, 
  Megaphone, 
  Settings, 
  BarChart3, 
  Inbox,
  Sparkles,
  Search,
  Bell,
  User,
  ChevronLeft,
  ChevronRight,
  Sun,
  Moon,
  Activity
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useTheme } from '@/lib/context/ThemeContext';
import { useLayout } from '@/lib/context/LayoutContext';
import AgentThoughtWidget from './AgentThoughtWidget';

interface LayoutProps {
  children: ReactNode;
  title?: string;
}

const navItems = [
  { icon: LayoutDashboard, label: 'Dashboard', href: '/' },
  { icon: Inbox, label: 'Inbox', href: '/inbox' },
  { icon: User, label: 'Customers', href: '/customers' },
  { icon: Package, label: 'Inventory Hub', href: '/inventory' },
  { icon: Megaphone, label: 'Campaign Center', href: '/campaigns' },
  { icon: BarChart3, label: 'Analytics', href: '/analytics' },
  { icon: Settings, label: 'Settings', href: '/settings' },
];

export function AppShell({ children, title = 'Cephly' }: LayoutProps) {
  const router = useRouter();
  const [isCollapsed, setIsCollapsed] = React.useState(false);
  const { theme, setTheme, toggleTheme } = useTheme();
  const { isAgentStreamOpen, setAgentStreamOpen, toggleAgentStream } = useLayout();

  return (
    <div className="h-screen bg-[hsl(var(--bg-app))] text-slate-100 flex overflow-hidden transition-colors duration-500">
      <Head>
        <title>{title} | Premium Retail OS</title>
      </Head>

      {/* SIDEBAR */}
      <aside 
        className={`relative transition-all duration-300 border-r border-[hsl(var(--border-panel))] bg-[hsl(var(--bg-app))]/80 backdrop-blur-xl flex flex-col z-20 ${
          isCollapsed ? 'w-20' : 'w-64'
        }`}
      >
        {/* Toggle Button */}
        <button 
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="absolute -right-3 top-10 w-6 h-6 bg-[hsl(var(--bg-app))] border border-[hsl(var(--border-panel))] rounded-full flex items-center justify-center hover:bg-slate-800 transition-colors z-50 text-slate-400"
        >
          {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>

        <div className={`p-8 flex items-center gap-3 transition-opacity duration-300 ${isCollapsed ? 'opacity-0 invisible h-0 overflow-hidden p-0' : 'opacity-100'}`}>
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <span className="text-xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">
            Cephly
          </span>
        </div>

        {isCollapsed && (
          <div className="p-6 flex justify-center">
            <div className="w-8 h-8 rounded-lg bg-indigo-500 flex items-center justify-center">
               <Sparkles className="w-5 h-5 text-white" />
            </div>
          </div>
        )}

        <nav className={`flex-1 px-4 space-y-1 mt-4 ${isCollapsed ? 'flex flex-col items-center' : ''}`}>
          {navItems.map((item) => {
            const isActive = router.pathname === item.href;
            return (
              <Link 
                key={item.label} 
                href={item.href}
                className={`flex items-center rounded-xl transition-all duration-200 group ${
                  isCollapsed ? 'p-3 justify-center' : 'gap-3 px-4 py-3'
                } ${
                  isActive 
                    ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 shadow-[0_0_15px_-5px_rgba(99,102,241,0.2)]' 
                    : 'text-slate-400 hover:text-white hover:bg-[hsl(var(--bg-panel))] border border-transparent'
                }`}
              >
                <item.icon className={`w-5 h-5 transition-colors ${isActive ? 'text-indigo-400' : 'group-hover:text-white'}`} />
                {!isCollapsed && <span className="font-medium">{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        {!isCollapsed && (
          <div className="p-4 mt-auto">
            <div className="bg-[hsl(var(--bg-panel))] border border-[hsl(var(--border-panel))] rounded-2xl p-4 text-center">
               <div className="flex items-center justify-center gap-2 mb-2">
                  <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">System Online</span>
               </div>
               <p className="text-[10px] text-slate-400 leading-relaxed">
                  Agent precision: <span className="text-white font-bold">98.4%</span>
               </p>
            </div>
          </div>
        )}
      </aside>

      {/* MAIN CONTENT */}
      <main className="flex-1 flex flex-col relative overflow-hidden backdrop-blur-3xl">
        {/* TOP BAR */}
        <header className="h-20 border-b border-[hsl(var(--border-panel))] px-8 flex items-center justify-between bg-[hsl(var(--bg-app))]/50 backdrop-blur-md sticky top-0 z-10">
           <div className="flex items-center gap-4 bg-[hsl(var(--bg-input))] border border-[hsl(var(--border-panel))] rounded-full px-4 py-2 w-96 transition-all focus-within:ring-2 focus-within:ring-indigo-500/50 focus-within:border-indigo-500/50">
              <Search className="w-4 h-4 text-slate-500" />
              <input 
                placeholder="Search inventory, campaigns, commands..." 
                className="bg-transparent border-none outline-none text-sm text-slate-200 placeholder:text-slate-600 w-full"
              />
           </div>

           <div className="flex items-center gap-4">
              {/* THEME TOGGLE (Circular) */}
              <button 
                onClick={toggleTheme}
                className="p-2.5 rounded-full hover:bg-[hsl(var(--bg-panel))] text-slate-400 hover:text-white transition-all"
                title={`Switch to ${theme === 'glass' ? 'Void' : 'Glass'} theme`}
              >
                 {theme === 'glass' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
              </button>

              <button className="p-2.5 rounded-full hover:bg-[hsl(var(--bg-panel))] text-slate-400 hover:text-white relative">
                <Bell className="w-5 h-5" />
              </button>

              <div className="h-8 w-[1px] bg-slate-800 mx-2" />
              <div className="flex items-center gap-3 pl-2 group cursor-pointer">
                 <div className="text-right hidden sm:block">
                    <p className="text-sm font-semibold text-white group-hover:text-indigo-400 transition-colors">Alexander Gray</p>
                    <p className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Store Owner</p>
                 </div>
                 <div className="w-10 h-10 rounded-xl bg-slate-800 border border-slate-700/50 flex items-center justify-center overflow-hidden">
                    <User className="w-6 h-6 text-slate-400" />
                 </div>
              </div>
           </div>
        </header>

        {/* PAGE BODY */}
        <div className={`${title === 'Inbox' ? 'p-0' : 'p-8'} overflow-y-auto custom-scrollbar flex-1 flex flex-col`}>
           <motion.div
             initial={{ opacity: 0, y: 10 }}
             animate={{ opacity: 1, y: 0 }}
             transition={{ duration: 0.4 }}
           >
             {children}
           </motion.div>
        </div>

        {/* GLOBAL AGENT STREAM */}
        <AgentThoughtWidget isOpen={isAgentStreamOpen} onClose={() => setAgentStreamOpen(false)} />

        {/* FLOATING AGENT WIDGET TRIGGER (FAB) */}
        {!isAgentStreamOpen && (
           <button
             onClick={() => setAgentStreamOpen(true)}
             className="fixed bottom-8 right-8 z-50 p-4 rounded-full bg-indigo-600 hover:bg-indigo-500 text-white shadow-2xl shadow-indigo-600/40 hover:scale-110 active:scale-95 transition-all duration-300 group border border-indigo-400/20"
             title="Open Neural Stream"
           >
              <div className="absolute inset-0 rounded-full bg-indigo-400/20 animate-ping opacity-0 group-hover:opacity-75" />
              <Activity className="w-6 h-6 relative z-10" />
           </button>
        )}
      </main>
    </div>
  );
}


import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertCircle, RefreshCcw } from 'lucide-react';

interface Props {
  children?: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
    // Optional: Window reload to fully clear state
    // window.location.reload(); 
  };

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="w-full h-full min-h-[400px] flex flex-col items-center justify-center p-8 text-center bg-slate-950/50 backdrop-blur-sm rounded-3xl border border-red-500/10">
          <div className="w-16 h-16 bg-red-500/10 rounded-full flex items-center justify-center mb-6">
             <AlertCircle className="w-8 h-8 text-red-500" />
          </div>
          
          <h2 className="text-xl font-black text-white mb-2">Neural Link Interrupted</h2>
          <p className="text-sm text-slate-400 max-w-md mb-8 leading-relaxed">
            The standard UI encountered a rendering anomaly. The core agent systems are still operational.
          </p>

          <div className="bg-black/40 rounded-xl p-4 mb-8 w-full max-w-md overflow-hidden text-left border border-white/5">
             <p className="text-[10px] font-mono text-red-400 break-all">
                {this.state.error?.toString()}
             </p>
          </div>

          <button 
            onClick={this.handleReset}
            className="px-6 py-3 bg-white text-black rounded-xl text-xs font-black uppercase tracking-widest hover:bg-slate-200 transition-colors flex items-center gap-2"
          >
            <RefreshCcw className="w-3 h-3" />
            Re-sync Interface
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

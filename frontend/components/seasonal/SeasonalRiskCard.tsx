'use client';

import React, { useEffect, useState } from 'react';

interface SeasonalRisk {
  product_id: string;
  title: string;
  season: string;
  days_remaining: number;
  risk_level: 'critical' | 'high' | 'moderate' | 'low';
  velocity_decline: number;
  confidence: number;
  reasoning: string;
}

interface SeasonalRiskCardProps {
  risk: SeasonalRisk;
  onCreateProposal?: (productId: string) => void;
}

const riskColors = {
  critical: { bg: 'bg-red-500/20', border: 'border-red-500', text: 'text-red-400' },
  high: { bg: 'bg-orange-500/20', border: 'border-orange-500', text: 'text-orange-400' },
  moderate: { bg: 'bg-yellow-500/20', border: 'border-yellow-500', text: 'text-yellow-400' },
  low: { bg: 'bg-green-500/20', border: 'border-green-500', text: 'text-green-400' },
};

const seasonIcons: Record<string, string> = {
  spring: '🌸',
  summer: '☀️',
  fall: '🍂',
  winter: '❄️',
  holiday: '🎄',
  back_to_school: '📚',
};

export function SeasonalRiskCard({ risk, onCreateProposal }: SeasonalRiskCardProps) {
  const colors = riskColors[risk.risk_level];
  const icon = seasonIcons[risk.season] || '📦';
  
  const [countdown, setCountdown] = useState(risk.days_remaining);
  
  // Countdown timer
  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown((prev) => Math.max(0, prev - 1 / 86400)); // Decrement by seconds
    }, 1000);
    
    return () => clearInterval(timer);
  }, []);
  
  const formatDays = (days: number) => {
    if (days < 1) return 'Less than 1 day';
    if (days === 1) return '1 day';
    return `${Math.floor(days)} days`;
  };

  return (
    <div
      className={`relative overflow-hidden rounded-xl border ${colors.border} ${colors.bg} p-5 transition-all hover:scale-[1.02] hover:shadow-lg`}
    >
      {/* Risk Badge */}
      <div className={`absolute top-3 right-3 px-2 py-1 rounded-full text-xs font-bold uppercase ${colors.text} ${colors.bg}`}>
        {risk.risk_level}
      </div>
      
      {/* Season Icon & Title */}
      <div className="flex items-start gap-3 mb-4">
        <span className="text-3xl">{icon}</span>
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-white truncate">{risk.title}</h3>
          <p className="text-sm text-gray-400 capitalize">{risk.season} Season</p>
        </div>
      </div>
      
      {/* Countdown */}
      <div className="mb-4">
        <div className="text-sm text-gray-400 mb-1">Season ends in</div>
        <div className={`text-2xl font-bold ${risk.days_remaining <= 7 ? 'text-red-400 animate-pulse' : 'text-white'}`}>
          {formatDays(countdown)}
        </div>
      </div>
      
      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-gray-800/50 rounded-lg p-2">
          <div className="text-xs text-gray-400">Velocity Decline</div>
          <div className={`font-bold ${risk.velocity_decline > 0.5 ? 'text-red-400' : 'text-yellow-400'}`}>
            {(risk.velocity_decline * 100).toFixed(0)}%
          </div>
        </div>
        <div className="bg-gray-800/50 rounded-lg p-2">
          <div className="text-xs text-gray-400">Confidence</div>
          <div className="font-bold text-blue-400">
            {(risk.confidence * 100).toFixed(0)}%
          </div>
        </div>
      </div>
      
      {/* Reasoning */}
      <p className="text-sm text-gray-400 mb-4 line-clamp-2">
        {risk.reasoning}
      </p>
      
      {/* Action Button */}
      {onCreateProposal && (
        <button
          onClick={() => onCreateProposal(risk.product_id)}
          className="w-full py-2 px-4 bg-indigo-600 hover:bg-indigo-700 rounded-lg text-white font-medium transition-colors"
        >
          Create Clearance Proposal
        </button>
      )}
    </div>
  );
}

// Export list component for multiple risks
interface SeasonalRiskListProps {
  risks: SeasonalRisk[];
  onCreateProposal?: (productId: string) => void;
  isLoading?: boolean;
}

export function SeasonalRiskList({ risks, onCreateProposal, isLoading }: SeasonalRiskListProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500" />
        <span className="ml-3 text-gray-400">Scanning for seasonal risks...</span>
      </div>
    );
  }
  
  if (risks.length === 0) {
    return (
      <div className="text-center py-12 text-gray-400">
        <span className="text-4xl block mb-3">✨</span>
        <p>No seasonal risks detected. Your inventory is well-positioned!</p>
      </div>
    );
  }
  
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {risks.map((risk) => (
        <SeasonalRiskCard
          key={risk.product_id}
          risk={risk}
          onCreateProposal={onCreateProposal}
        />
      ))}
    </div>
  );
}

export default SeasonalRiskCard;

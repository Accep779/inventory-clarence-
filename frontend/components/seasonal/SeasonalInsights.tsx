'use client';

import React from 'react';

interface SeasonInsight {
  season: string;
  total_campaigns: number;
  success_rate: number;
  avg_revenue: number;
  top_strategy: string;
}

interface SeasonalInsightsProps {
  insights: SeasonInsight[];
  recommendations: string[];
}

const seasonColors: Record<string, string> = {
  spring: '#10b981',
  summer: '#f59e0b',
  fall: '#ef4444',
  winter: '#3b82f6',
  holiday: '#8b5cf6',
  back_to_school: '#ec4899',
};

export function SeasonalInsights({ insights, recommendations }: SeasonalInsightsProps) {
  const maxCampaigns = Math.max(...insights.map(i => i.total_campaigns), 1);
  
  return (
    <div className="space-y-6">
      {/* Season Performance Bars */}
      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
        <h3 className="text-lg font-semibold text-white mb-4">
          📊 Seasonal Performance
        </h3>
        
        {insights.length === 0 ? (
          <p className="text-gray-400 text-center py-8">
            No seasonal campaign data yet. Start clearing seasonal inventory to build insights.
          </p>
        ) : (
          <div className="space-y-4">
            {insights.map((insight) => (
              <div key={insight.season} className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="capitalize font-medium text-white">
                    {insight.season}
                  </span>
                  <span className="text-sm text-gray-400">
                    {insight.total_campaigns} campaigns • {(insight.success_rate * 100).toFixed(0)}% success
                  </span>
                </div>
                
                {/* Success rate bar */}
                <div className="h-3 bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${insight.success_rate * 100}%`,
                      backgroundColor: seasonColors[insight.season] || '#6366f1'
                    }}
                  />
                </div>
                
                <div className="flex justify-between text-xs text-gray-500">
                  <span>Top strategy: {insight.top_strategy}</span>
                  <span>Avg revenue: ${insight.avg_revenue.toFixed(2)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      
      {/* Recommendations */}
      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
        <h3 className="text-lg font-semibold text-white mb-4">
          💡 AI Recommendations
        </h3>
        
        {recommendations.length === 0 ? (
          <p className="text-gray-400">No recommendations at this time.</p>
        ) : (
          <ul className="space-y-3">
            {recommendations.map((rec, index) => (
              <li
                key={index}
                className="flex items-start gap-2 p-3 bg-gray-800/50 rounded-lg"
              >
                <span className="text-lg">{rec.startsWith('⚠️') ? '⚠️' : rec.startsWith('✅') ? '✅' : '💡'}</span>
                <span className="text-gray-300">
                  {rec.replace(/^[⚠️✅💡]\s*/, '')}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default SeasonalInsights;

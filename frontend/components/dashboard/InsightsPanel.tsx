import React from 'react';
import { motion } from 'framer-motion';
import { 
  TrendingUp, 
  TrendingDown, 
  Minus, 
  AlertTriangle, 
  DollarSign, 
  Target,
  Sparkles,
  ArrowUpRight,
  ArrowDownRight,
  BarChart3,
  Package
} from 'lucide-react';
import { usePredictiveInsights } from '@/lib/hooks/useDashboard';
import { StatCardSkeleton, InsightCardSkeleton } from '@/components/ui/SkeletonLoader';

interface InsightsPanelProps {
  merchantId: string;
}

export function InsightsPanel({ merchantId }: InsightsPanelProps) {
  const { data, isLoading, error } = usePredictiveInsights(merchantId);

  if (isLoading) {
    return (
      <div className="bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-default))] rounded-xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <Sparkles className="w-5 h-5 text-[hsl(var(--accent-primary))]" />
          <h3 className="text-lg font-semibold text-[hsl(var(--text-primary))]">
            AI Predictive Insights
          </h3>
        </div>
        <div className="space-y-4">
          <InsightCardSkeleton />
          <InsightCardSkeleton />
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-default))] rounded-xl p-6">
        <div className="text-center py-8">
          <AlertTriangle className="w-10 h-10 text-amber-400 mx-auto mb-3" />
          <p className="text-sm text-[hsl(var(--text-secondary))]">
            Unable to load predictive insights. Please try again later.
          </p>
        </div>
      </div>
    );
  }

  const { forecast_revenue_30d, confidence, at_risk_inventory, trend_direction, trend_percentage } = data;

  return (
    <div className="bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-default))] rounded-xl p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-[hsl(var(--accent-primary)/0.1)]">
            <Sparkles className="w-4 h-4 text-[hsl(var(--accent-primary))]" />
          </div>
          <h3 className="text-lg font-semibold text-[hsl(var(--text-primary))]">
            AI Predictive Insights
          </h3>
          <span className="text-xs text-[hsl(var(--text-tertiary))]">
            (Next 30 days)
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-[hsl(var(--text-tertiary))]">Confidence:</span>
          <span className="text-xs font-bold text-emerald-400 bg-emerald-400/10 px-2 py-1 rounded-full">
            {confidence}%
          </span>
        </div>
      </div>

      {/* Revenue Forecast Card */}
      <div className="mb-6 p-4 rounded-xl bg-gradient-to-r from-[hsl(var(--accent-primary)/0.1)] to-[hsl(var(--accent-secondary)/0.05)] border border-[hsl(var(--accent-primary)/0.2)]">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-[hsl(var(--accent-primary))]" />
            <span className="text-sm font-medium text-[hsl(var(--text-primary))]">
              Revenue Forecast
            </span>
          </div>
          <TrendIndicator direction={trend_direction} percentage={trend_percentage} />
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-bold text-[hsl(var(--text-primary))]">
            ${forecast_revenue_30d.toLocaleString()}
          </span>
          <span className="text-sm text-[hsl(var(--text-tertiary))]">
            predicted revenue
          </span>
        </div>
      </div>

      {/* At-Risk Inventory Section */}
      <div className="mb-4">
        <div className="flex items-center gap-2 mb-3">
          <AlertTriangle className="w-4 h-4 text-amber-400" />
          <h4 className="text-sm font-semibold text-[hsl(var(--text-primary))]">
            At-Risk Inventory
          </h4>
          <span className="text-xs text-[hsl(var(--text-tertiary))]">
            ({at_risk_inventory.length} items need attention)
          </span>
        </div>

        {at_risk_inventory.length === 0 ? (
          <div className="p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/10 text-center">
            <p className="text-sm text-emerald-400">
              ✅ No at-risk inventory detected
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {at_risk_inventory.slice(0, 3).map((item, idx) => (
              <AtRiskItemCard key={item.product_id} item={item} index={idx} />
            ))}
            {at_risk_inventory.length > 3 && (
              <button className="w-full text-center py-2 text-xs text-[hsl(var(--accent-primary))] hover:underline">
                +{at_risk_inventory.length - 3} more items
              </button>
            )}
          </div>
        )}
      </div>

      {/* Pricing Recommendations */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <DollarSign className="w-4 h-4 text-emerald-400" />
          <h4 className="text-sm font-semibold text-[hsl(var(--text-primary))]">
            Optimal Pricing Recommendations
          </h4>
        </div>

        <div className="grid grid-cols-2 gap-3">
          {at_risk_inventory.slice(0, 2).map((item) => (
            <PricingRecommendationCard key={item.product_id} item={item} />
          ))}
        </div>
      </div>
    </div>
  );
}

function TrendIndicator({ direction, percentage }: { direction: string; percentage: number }) {
  const isPositive = direction === 'up';
  const isStable = direction === 'stable';

  return (
    <div className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs font-bold ${
      isPositive 
        ? 'bg-emerald-400/10 text-emerald-400' 
        : isStable 
          ? 'bg-slate-400/10 text-slate-400'
          : 'bg-rose-400/10 text-rose-400'
    }`}>
      {isPositive ? (
        <ArrowUpRight className="w-3 h-3" />
      ) : isStable ? (
        <Minus className="w-3 h-3" />
      ) : (
        <ArrowDownRight className="w-3 h-3" />
      )}
      {percentage}%
    </div>
  );
}

function AtRiskItemCard({ item, index }: { item: any; index: number }) {
  const riskLevel = item.days_to_stockout < 7 ? 'high' : item.days_to_stockout < 14 ? 'medium' : 'low';
  const riskColors = {
    high: 'border-rose-500/30 bg-rose-500/5',
    medium: 'border-amber-500/30 bg-amber-500/5',
    low: 'border-yellow-500/30 bg-yellow-500/5',
  };
  const riskTextColors = {
    high: 'text-rose-400',
    medium: 'text-amber-400',
    low: 'text-yellow-400',
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.1 }}
      className={`p-3 rounded-lg border ${riskColors[riskLevel]} flex items-center justify-between`}
    >
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-[hsl(var(--bg-tertiary))] flex items-center justify-center shrink-0">
          <Package className="w-4 h-4 text-[hsl(var(--text-tertiary))]" />
        </div>
        <div>
          <p className="text-sm font-medium text-[hsl(var(--text-primary))] line-clamp-1">
            {item.name}
          </p>
          <p className="text-xs text-[hsl(var(--text-tertiary))]">
            Stockout in {item.days_to_stockout} days
          </p>
        </div>
      </div>
      <div className="text-right">
        <span className={`text-xs font-bold ${riskTextColors[riskLevel]}`}>
          {item.confidence}% risk
        </span>
      </div>
    </motion.div>
  );
}

function PricingRecommendationCard({ item }: { item: any }) {
  const priceChange = ((item.suggested_price - item.current_price) / item.current_price * 100).toFixed(1);
  const isIncrease = parseFloat(priceChange) > 0;

  return (
    <div className="p-3 rounded-lg bg-[hsl(var(--bg-tertiary))] border border-[hsl(var(--border-subtle))]">
      <p className="text-xs text-[hsl(var(--text-tertiary))] mb-1 line-clamp-1">
        {item.name}
      </p>
      <div className="flex items-baseline gap-2">
        <span className="text-lg font-bold text-[hsl(var(--text-primary))]">
          ${item.suggested_price.toFixed(2)}
        </span>
        <span className={`text-xs font-medium ${isIncrease ? 'text-emerald-400' : 'text-rose-400'}`}>
          {isIncrease ? '+' : ''}{priceChange}%
        </span>
      </div>
      <div className="flex items-center gap-1 mt-1">
        <Target className="w-3 h-3 text-[hsl(var(--accent-primary))]" />
        <span className="text-xs text-[hsl(var(--accent-primary))]">
          {item.price_probability}% success rate
        </span>
      </div>
    </div>
  );
}

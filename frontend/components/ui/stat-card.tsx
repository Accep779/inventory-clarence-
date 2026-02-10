import React from 'react';
import { LucideIcon, TrendingUp, TrendingDown } from 'lucide-react';
import { cva, type VariantProps } from 'class-variance-authority';

const statCardVariants = cva(
  "relative overflow-hidden rounded-xl border p-6 transition-all duration-300",
  {
    variants: {
      variant: {
        default: "bg-[hsl(var(--bg-secondary))] border-[hsl(var(--border-default))] hover:border-[hsl(var(--border-strong))]",
        gradient: "border-transparent bg-gradient-to-br from-[hsl(var(--accent-primary)/0.2)] to-[hsl(var(--accent-secondary)/0.1)]",
        elevated: "bg-[hsl(var(--bg-secondary))] border-[hsl(var(--border-default))] shadow-lg hover:shadow-xl hover:-translate-y-1",
        minimal: "bg-transparent border-[hsl(var(--border-subtle))]",
      },
      size: {
        default: "p-6",
        sm: "p-4",
        lg: "p-8",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

interface StatCardProps extends VariantProps<typeof statCardVariants> {
  title: string;
  value: string | number;
  change?: string;
  changeType?: 'positive' | 'negative' | 'neutral';
  icon: LucideIcon;
  iconColor?: string;
  subtitle?: string;
  className?: string;
  sparkline?: number[];
}

export function StatCard({
  title,
  value,
  change,
  changeType = 'neutral',
  icon: Icon,
  iconColor = "hsl(var(--accent-primary))",
  subtitle,
  variant,
  size,
  className,
}: StatCardProps) {
  const changeColor = {
    positive: "text-emerald-400",
    negative: "text-rose-400",
    neutral: "text-slate-400",
  }[changeType];

  const ChangeIcon = changeType === 'positive' ? TrendingUp : changeType === 'negative' ? TrendingDown : null;

  return (
    <div className={statCardVariants({ variant, size, className })}>
      {/* Background Glow Effect */}
      <div
        className="absolute -top-20 -right-20 w-40 h-40 rounded-full blur-3xl opacity-30"
        style={{ background: `radial-gradient(circle, ${iconColor} 0%, transparent 70%)` }}
      />

      <div className="relative z-10">
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div>
            <p className="text-sm font-medium text-[hsl(var(--text-tertiary))]">{title}</p>
            {subtitle && (
              <p className="text-xs text-[hsl(var(--text-tertiary))] mt-0.5">{subtitle}</p>
            )}
          </div>
          <div
            className="p-2.5 rounded-lg"
            style={{ backgroundColor: `${iconColor}20` }}
          >
            <Icon className="w-5 h-5" style={{ color: iconColor }} />
          </div>
        </div>

        {/* Value */}
        <div className="space-y-2">
          <h3 className="text-3xl font-bold tracking-tight text-[hsl(var(--text-primary))]">
            {value}
          </h3>

          {/* Change Indicator */}
          {change && (
            <div className="flex items-center gap-1.5">
              {ChangeIcon && (
                <ChangeIcon className={`w-4 h-4 ${changeColor}`} />
              )}
              <span className={`text-sm font-semibold ${changeColor}`}>
                {change}
              </span>
              <span className="text-xs text-[hsl(var(--text-tertiary))]">vs last month</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Mini stat card for compact layouts
export function MiniStatCard({
  title,
  value,
  icon: Icon,
  trend,
}: {
  title: string;
  value: string;
  icon: LucideIcon;
  trend?: 'up' | 'down' | 'neutral';
}) {
  return (
    <div className="flex items-center gap-4 p-4 rounded-lg bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-default))]">
      <div className="p-2.5 rounded-lg bg-[hsl(var(--accent-primary)/0.15)]">
        <Icon className="w-5 h-5 text-[hsl(var(--accent-primary))]" />
      </div>
      <div>
        <p className="text-xs font-medium text-[hsl(var(--text-tertiary))] uppercase tracking-wide">{title}</p>
        <p className="text-lg font-bold text-[hsl(var(--text-primary))]">{value}</p>
      </div>
    </div>
  );
}

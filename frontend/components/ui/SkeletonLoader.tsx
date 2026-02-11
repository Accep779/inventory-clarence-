import React from 'react';
import { motion } from 'framer-motion';

interface SkeletonProps {
  className?: string;
  variant?: 'text' | 'circular' | 'rectangular' | 'rounded';
  width?: string | number;
  height?: string | number;
  animated?: boolean;
}

export function Skeleton({
  className = '',
  variant = 'text',
  width,
  height,
  animated = true,
}: SkeletonProps) {
  const baseStyles = 'bg-[hsl(var(--bg-tertiary))]';
  
  const variantStyles = {
    text: 'rounded',
    circular: 'rounded-full',
    rectangular: 'rounded-none',
    rounded: 'rounded-xl',
  };

  const sizeStyles = {
    text: { height: '1em', width: width || '100%' },
    circular: { height: height || '40px', width: width || '40px' },
    rectangular: { height: height || '100px', width: width || '100%' },
    rounded: { height: height || '100px', width: width || '100%' },
  };

  return (
    <motion.div
      className={`${baseStyles} ${variantStyles[variant]} ${className}`}
      style={sizeStyles[variant]}
      initial={false}
      animate={animated ? { opacity: [0.5, 0.8, 0.5] } : {}}
      transition={{
        duration: 1.5,
        repeat: Infinity,
        ease: 'easeInOut',
      }}
    />
  );
}

// Stat card skeleton
export function StatCardSkeleton() {
  return (
    <div className="relative overflow-hidden rounded-xl border border-[hsl(var(--border-default))] bg-[hsl(var(--bg-secondary))] p-6">
      <div className="flex items-start justify-between mb-4">
        <div className="space-y-2 flex-1">
          <Skeleton variant="text" width="60%" height="0.875rem" />
        </div>
        <Skeleton variant="circular" width="40px" height="40px" />
      </div>
      <div className="space-y-2">
        <Skeleton variant="text" width="50%" height="2rem" />
        <Skeleton variant="text" width="40%" height="1rem" />
      </div>
    </div>
  );
}

// Chart card skeleton
export function ChartCardSkeleton({ title = true }: { title?: boolean }) {
  return (
    <div className="rounded-xl border border-[hsl(var(--border-default))] bg-[hsl(var(--bg-secondary))] p-6">
      {title && (
        <div className="mb-4">
          <Skeleton variant="text" width="40%" height="1.25rem" />
          <Skeleton variant="text" width="30%" height="0.875rem" className="mt-1" />
        </div>
      )}
      <Skeleton variant="rounded" height="200px" />
    </div>
  );
}

// Activity item skeleton
export function ActivityItemSkeleton() {
  return (
    <div className="flex items-start gap-4 p-4 rounded-lg bg-[hsl(var(--bg-tertiary)/0.5)] border border-[hsl(var(--border-subtle))]">
      <Skeleton variant="circular" width="32px" height="32px" />
      <div className="flex-1 space-y-2">
        <div className="flex items-center gap-2">
          <Skeleton variant="text" width="80px" height="0.875rem" />
          <Skeleton variant="text" width="60px" height="0.75rem" />
        </div>
        <Skeleton variant="text" width="90%" height="0.875rem" />
      </div>
    </div>
  );
}

// Proposal card skeleton
export function ProposalCardSkeleton() {
  return (
    <div className="p-4 rounded-xl border border-[hsl(var(--border-subtle))] bg-[hsl(var(--bg-secondary))]">
      <div className="flex justify-between items-start mb-2">
        <Skeleton variant="text" width="70%" height="1rem" />
        <Skeleton variant="text" width="50px" height="0.75rem" />
      </div>
      <div className="flex items-center gap-2 mb-3">
        <Skeleton variant="text" width="60px" height="1.25rem" className="rounded-full" />
        <Skeleton variant="text" width="80px" height="0.75rem" />
      </div>
      <Skeleton variant="text" width="100%" height="0.875rem" />
      <Skeleton variant="text" width="80%" height="0.875rem" className="mt-1" />
    </div>
  );
}

// Insight card skeleton
export function InsightCardSkeleton() {
  return (
    <div className="p-4 rounded-xl border border-[hsl(var(--accent-primary)/0.2)] bg-gradient-to-r from-[hsl(var(--accent-primary)/0.05)] to-transparent">
      <div className="flex items-start gap-3">
        <Skeleton variant="circular" width="32px" height="32px" />
        <div className="flex-1 space-y-2">
          <Skeleton variant="text" width="60%" height="1rem" />
          <Skeleton variant="text" width="100%" height="0.875rem" />
          <Skeleton variant="text" width="80%" height="0.875rem" />
          <div className="flex gap-2 mt-3">
            <Skeleton variant="rounded" width="100px" height="32px" />
            <Skeleton variant="rounded" width="80px" height="32px" />
          </div>
        </div>
      </div>
    </div>
  );
}

// Full dashboard skeleton
export function DashboardSkeleton() {
  return (
    <div className="space-y-8">
      {/* Stats grid skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCardSkeleton />
        <StatCardSkeleton />
        <StatCardSkeleton />
        <StatCardSkeleton />
      </div>

      {/* Charts skeleton */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <ChartCardSkeleton />
        </div>
        <ChartCardSkeleton />
      </div>

      {/* Activity skeleton */}
      <div className="bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-default))] rounded-xl p-6">
        <Skeleton variant="text" width="200px" height="1.25rem" className="mb-6" />
        <div className="space-y-4">
          <ActivityItemSkeleton />
          <ActivityItemSkeleton />
          <ActivityItemSkeleton />
          <ActivityItemSkeleton />
        </div>
      </div>
    </div>
  );
}

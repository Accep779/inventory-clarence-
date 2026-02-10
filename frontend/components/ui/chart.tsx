'use client';

import React from 'react';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';

const defaultColors = [
  'hsl(260, 60%, 55%)',
  'hsl(270, 70%, 45%)',
  'hsl(220, 90%, 60%)',
  'hsl(180, 70%, 45%)',
  'hsl(320, 70%, 50%)',
];

// Area Chart Component
export function AreaChartWidget({
  data,
  dataKey,
  xAxisKey,
  color = defaultColors[0],
  showGrid = true,
  height = 200,
}: {
  data: any[];
  dataKey: string;
  xAxisKey: string;
  color?: string;
  showGrid?: boolean;
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data}>
        {showGrid && (
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="hsl(var(--border-default))"
            vertical={false}
          />
        )}
        <XAxis
          dataKey={xAxisKey}
          axisLine={false}
          tickLine={false}
          tick={{ fill: 'hsl(var(--text-tertiary))', fontSize: 12 }}
          dy={10}
        />
        <YAxis
          axisLine={false}
          tickLine={false}
          tick={{ fill: 'hsl(var(--text-tertiary))', fontSize: 12 }}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: 'hsl(var(--bg-secondary))',
            border: '1px solid hsl(var(--border-default))',
            borderRadius: '8px',
            color: 'hsl(var(--text-primary))',
          }}
          itemStyle={{ color: 'hsl(var(--text-primary))' }}
        />
        <Area
          type="monotone"
          dataKey={dataKey}
          stroke={color}
          strokeWidth={2}
          fill={color}
          fillOpacity={0.2}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// Bar Chart Component
export function BarChartWidget({
  data,
  dataKey,
  xAxisKey,
  colors = defaultColors,
  showGrid = true,
  height = 200,
}: {
  data: any[];
  dataKey: string;
  xAxisKey: string;
  colors?: string[];
  showGrid?: boolean;
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data}>
        {showGrid && (
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="hsl(var(--border-default))"
            vertical={false}
          />
        )}
        <XAxis
          dataKey={xAxisKey}
          axisLine={false}
          tickLine={false}
          tick={{ fill: 'hsl(var(--text-tertiary))', fontSize: 12 }}
          dy={10}
        />
        <YAxis
          axisLine={false}
          tickLine={false}
          tick={{ fill: 'hsl(var(--text-tertiary))', fontSize: 12 }}
        />
        <Tooltip
          cursor={{ fill: 'hsl(var(--border-subtle))' }}
          contentStyle={{
            backgroundColor: 'hsl(var(--bg-secondary))',
            border: '1px solid hsl(var(--border-default))',
            borderRadius: '8px',
            color: 'hsl(var(--text-primary))',
          }}
        />
        <Bar dataKey={dataKey} radius={[4, 4, 0, 0]}>
          {data.map((_, index) => (
            <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// Line Chart Component
export function LineChartWidget({
  data,
  dataKey,
  xAxisKey,
  color = defaultColors[0],
  showGrid = true,
  height = 200,
}: {
  data: any[];
  dataKey: string;
  xAxisKey: string;
  color?: string;
  showGrid?: boolean;
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data}>
        {showGrid && (
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="hsl(var(--border-default))"
            vertical={false}
          />
        )}
        <XAxis
          dataKey={xAxisKey}
          axisLine={false}
          tickLine={false}
          tick={{ fill: 'hsl(var(--text-tertiary))', fontSize: 12 }}
          dy={10}
        />
        <YAxis
          axisLine={false}
          tickLine={false}
          tick={{ fill: 'hsl(var(--text-tertiary))', fontSize: 12 }}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: 'hsl(var(--bg-secondary))',
            border: '1px solid hsl(var(--border-default))',
            borderRadius: '8px',
            color: 'hsl(var(--text-primary))',
          }}
          itemStyle={{ color: 'hsl(var(--text-primary))' }}
        />
        <Line
          type="monotone"
          dataKey={dataKey}
          stroke={color}
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 6, fill: color, stroke: 'hsl(var(--bg-secondary))', strokeWidth: 2 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

// Pie Chart Component
export function PieChartWidget({
  data,
  dataKey,
  nameKey,
  colors = defaultColors,
  height = 200,
}: {
  data: any[];
  dataKey: string;
  nameKey: string;
  colors?: string[];
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={60}
          outerRadius={80}
          paddingAngle={5}
          dataKey={dataKey}
        >
          {data.map((_, index) => (
            <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            backgroundColor: 'hsl(var(--bg-secondary))',
            border: '1px solid hsl(var(--border-default))',
            borderRadius: '8px',
            color: 'hsl(var(--text-primary))',
          }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}

// Chart Card with Title
export function ChartCard({
  title,
  subtitle,
  children,
  action,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-default))] rounded-xl p-6">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold text-[hsl(var(--text-primary))]">{title}</h3>
          {subtitle && (
            <p className="text-sm text-[hsl(var(--text-tertiary))] mt-1">{subtitle}</p>
          )}
        </div>
        {action && <div>{action}</div>}
      </div>
      {children}
    </div>
  );
}

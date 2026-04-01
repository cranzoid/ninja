interface MetricCardProps {
  label: string;
  value: string;
  subValue?: string;
  color?: string;
  trend?: 'up' | 'down' | 'flat';
  className?: string;
}

export function MetricCard({
  label,
  value,
  subValue,
  color,
  trend,
  className = '',
}: MetricCardProps) {
  const trendSymbol =
    trend === 'up' ? '▲' : trend === 'down' ? '▼' : undefined;
  const trendColor =
    trend === 'up' ? '#22c55e' : trend === 'down' ? '#ef4444' : undefined;

  return (
    <div
      className={`flex flex-col justify-between p-4 rounded-sm ${className}`}
      style={{
        background: 'rgba(255,255,255,0.03)',
        border: '1px solid rgba(255,255,255,0.06)',
        minHeight: '80px',
      }}
    >
      <div className="text-xs font-semibold uppercase tracking-widest text-white/30">
        {label}
      </div>
      <div className="mt-2">
        <div
          className="font-mono font-bold leading-none"
          style={{
            fontSize: '1.4rem',
            color: color ?? 'rgba(255,255,255,0.9)',
          }}
        >
          {trendSymbol && (
            <span className="text-base mr-1.5" style={{ color: trendColor }}>
              {trendSymbol}
            </span>
          )}
          {value}
        </div>
        {subValue && (
          <div className="text-xs text-white/30 mt-1 font-mono">{subValue}</div>
        )}
      </div>
    </div>
  );
}

type DotStatus = 'healthy' | 'warning' | 'error' | 'inactive';

const STATUS_COLORS: Record<DotStatus, string> = {
  healthy: '#22c55e',
  warning: '#f59e0b',
  error: '#ef4444',
  inactive: 'rgba(255,255,255,0.2)',
};

interface StatusDotProps {
  status: DotStatus;
  pulse?: boolean;
  label?: string;
}

export function StatusDot({ status, pulse = false, label }: StatusDotProps) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className={pulse && status === 'healthy' ? 'pulse-dot' : ''}
        style={{
          display: 'inline-block',
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          background: STATUS_COLORS[status],
          flexShrink: 0,
        }}
      />
      {label && <span className="text-xs text-white/50">{label}</span>}
    </span>
  );
}

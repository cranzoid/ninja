import { safeFloat, formatPct, utilizationBgColor } from '@/lib/utils';

interface RiskMeterProps {
  current: number | string;
  limit: number | string;
  label: string;
  currentLabel?: string;
  limitLabel?: string;
}

export function RiskMeter({
  current,
  limit,
  label,
  currentLabel,
  limitLabel,
}: RiskMeterProps) {
  const c = safeFloat(current);
  const l = safeFloat(limit);
  const pct = l > 0 ? Math.min((c / l) * 100, 105) : 0;
  const utilPct = l > 0 ? (c / l) * 100 : 0;
  const bgColor = utilizationBgColor(utilPct);

  // Limit marker position (at 100% of the bar, or at exactly l/l)
  const limitPos = Math.min(100, (l / (l * 1.05)) * 100);

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs text-white/50">{label}</span>
        <span className="text-xs font-mono text-white/40">
          {currentLabel ?? `${c.toFixed(2)}%`} / {limitLabel ?? `${l.toFixed(2)}%`}
          <span className={`ml-2 ${utilizationBgColor(utilPct).replace('bg-', 'text-')}`}>
            ({formatPct(utilPct, 0)} used)
          </span>
        </span>
      </div>
      <div
        className="relative w-full rounded-full overflow-visible"
        style={{ height: '8px', background: 'rgba(255,255,255,0.06)' }}
      >
        {/* Current fill */}
        <div
          className={`h-full rounded-full transition-all duration-300 ${bgColor}`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
        {/* Limit marker */}
        <div
          className="absolute top-0 bottom-0 w-0.5"
          style={{
            left: `${limitPos}%`,
            background: 'rgba(255,255,255,0.3)',
            height: '12px',
            top: '-2px',
          }}
        />
      </div>
    </div>
  );
}

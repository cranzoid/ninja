import { utilizationBgColor, safeFloat, formatPct } from '@/lib/utils';

interface ProgressBarProps {
  value: number | string;
  max: number | string;
  label?: string;
  showPct?: boolean;
  showValues?: boolean;
  valueLabel?: string;
  maxLabel?: string;
  height?: number;
}

export function ProgressBar({
  value,
  max,
  label,
  showPct = false,
  showValues = false,
  valueLabel,
  maxLabel,
  height = 6,
}: ProgressBarProps) {
  const v = safeFloat(value);
  const m = safeFloat(max);
  const pct = m > 0 ? Math.min((v / m) * 100, 100) : 0;
  const bgColor = utilizationBgColor(pct);

  return (
    <div className="w-full">
      {(label || showPct || showValues) && (
        <div className="flex items-center justify-between mb-1.5">
          {label && (
            <span className="text-xs text-white/50">{label}</span>
          )}
          <div className="flex items-center gap-3 ml-auto">
            {showValues && (
              <span className="text-xs font-mono text-white/40">
                {valueLabel ?? v.toFixed(2)} / {maxLabel ?? m.toFixed(2)}
              </span>
            )}
            {showPct && (
              <span className="text-xs font-mono text-white/50">
                {formatPct(pct, 1)}
              </span>
            )}
          </div>
        </div>
      )}
      <div
        className="w-full rounded-full overflow-hidden"
        style={{ height: `${height}px`, background: 'rgba(255,255,255,0.06)' }}
      >
        <div
          className={`h-full rounded-full transition-all duration-300 ${bgColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

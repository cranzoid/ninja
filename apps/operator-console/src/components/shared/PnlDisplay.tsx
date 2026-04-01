import { formatINR, safeFloat } from '@/lib/utils';

interface PnlDisplayProps {
  value: number | string;
  showSign?: boolean;
  size?: 'sm' | 'md' | 'lg';
  showPct?: boolean;
  pctValue?: number | string;
}

const SIZE_CLASS: Record<'sm' | 'md' | 'lg', string> = {
  sm: 'text-sm',
  md: 'text-base',
  lg: 'text-xl',
};

export function PnlDisplay({
  value,
  showSign = true,
  size = 'md',
  showPct = false,
  pctValue,
}: PnlDisplayProps) {
  const num = safeFloat(value);
  const isPositive = num >= 0;
  const color = isPositive ? 'text-profit' : 'text-loss';
  const sign = showSign ? (isPositive ? '+' : '-') : num < 0 ? '-' : '';

  return (
    <span className={`font-mono font-semibold ${color} ${SIZE_CLASS[size]}`}>
      {sign}
      {formatINR(Math.abs(num))}
      {showPct && pctValue !== undefined && (
        <span className="ml-1 text-xs opacity-70">
          ({isPositive ? '+' : ''}{safeFloat(pctValue).toFixed(2)}%)
        </span>
      )}
    </span>
  );
}

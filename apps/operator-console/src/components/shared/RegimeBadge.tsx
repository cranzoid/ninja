import type { RegimeClass } from '@/lib/types';
import { REGIME_SIZING } from '@/lib/constants';

type BadgeVariant = 'green' | 'amber' | 'purple';

const REGIME_VARIANTS: Record<RegimeClass, BadgeVariant> = {
  green: 'green',
  mixed: 'amber',
  stressed: 'purple',
};

const REGIME_BG: Record<RegimeClass, string> = {
  green: 'rgba(34,197,94,0.12)',
  mixed: 'rgba(245,158,11,0.12)',
  stressed: 'rgba(139,92,246,0.12)',
};

const REGIME_BORDER: Record<RegimeClass, string> = {
  green: 'rgba(34,197,94,0.3)',
  mixed: 'rgba(245,158,11,0.3)',
  stressed: 'rgba(139,92,246,0.3)',
};

const REGIME_TEXT: Record<RegimeClass, string> = {
  green: '#22c55e',
  mixed: '#f59e0b',
  stressed: '#8b5cf6',
};

interface RegimeBadgeProps {
  regime: RegimeClass;
  showMultiplier?: boolean;
  size?: 'sm' | 'md';
}

export function RegimeBadge({ regime, showMultiplier = false, size = 'sm' }: RegimeBadgeProps) {
  const padClass = size === 'md' ? 'px-2.5 py-1 text-xs' : 'px-2 py-0.5 text-2xs';

  return (
    <span
      className={`inline-flex items-center gap-1 font-mono font-semibold tracking-widest uppercase rounded-sm ${padClass}`}
      style={{
        background: REGIME_BG[regime],
        border: `1px solid ${REGIME_BORDER[regime]}`,
        color: REGIME_TEXT[regime],
      }}
    >
      {regime.toUpperCase()}
      {showMultiplier && (
        <span className="opacity-60">{REGIME_SIZING[regime]}</span>
      )}
    </span>
  );
}

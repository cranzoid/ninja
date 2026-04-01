type BadgeVariant = 'green' | 'red' | 'amber' | 'blue' | 'purple' | 'neutral';

const VARIANT_STYLES: Record<BadgeVariant, string> = {
  green: 'text-profit',
  red: 'text-loss',
  amber: 'text-warning',
  blue: 'text-info',
  purple: 'text-regime-stressed',
  neutral: 'text-white/40',
};

const VARIANT_BG: Record<BadgeVariant, string> = {
  green: 'rgba(34,197,94,0.12)',
  red: 'rgba(239,68,68,0.12)',
  amber: 'rgba(245,158,11,0.12)',
  blue: 'rgba(59,130,246,0.12)',
  purple: 'rgba(139,92,246,0.12)',
  neutral: 'rgba(255,255,255,0.06)',
};

const VARIANT_BORDER: Record<BadgeVariant, string> = {
  green: 'rgba(34,197,94,0.25)',
  red: 'rgba(239,68,68,0.25)',
  amber: 'rgba(245,158,11,0.25)',
  blue: 'rgba(59,130,246,0.25)',
  purple: 'rgba(139,92,246,0.25)',
  neutral: 'rgba(255,255,255,0.08)',
};

interface BadgeProps {
  label: string;
  variant: BadgeVariant;
  size?: 'sm' | 'md';
}

export function Badge({ label, variant, size = 'sm' }: BadgeProps) {
  const padClass = size === 'md' ? 'px-2.5 py-1 text-xs' : 'px-2 py-0.5 text-2xs';
  return (
    <span
      className={`inline-flex items-center font-mono font-semibold tracking-widest uppercase rounded-sm ${padClass} ${VARIANT_STYLES[variant]}`}
      style={{
        background: VARIANT_BG[variant],
        border: `1px solid ${VARIANT_BORDER[variant]}`,
      }}
    >
      {label}
    </span>
  );
}

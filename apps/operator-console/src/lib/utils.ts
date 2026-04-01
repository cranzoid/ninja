import type { RegimeClass, Mode } from './types';

/** Format a number as INR: ₹50,000.00 */
export function formatINR(amount: number | string): string {
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (isNaN(num)) return '₹—';
  return (
    '₹' +
    Math.abs(num).toLocaleString('en-IN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  );
}

/** Format a number as INR with sign: +₹50,000 / -₹50,000 */
export function formatINRSigned(amount: number | string): string {
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (isNaN(num)) return '₹—';
  const sign = num >= 0 ? '+' : '-';
  return (
    sign +
    '₹' +
    Math.abs(num).toLocaleString('en-IN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  );
}

/** Format a percentage: 4.25% */
export function formatPct(value: number | string, decimals = 2): string {
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(num)) return '—%';
  return num.toFixed(decimals) + '%';
}

/** Format a date string (ISO) to: 27 Mar 2026 */
export function formatDate(date: string | null | undefined): string {
  if (!date) return '—';
  try {
    const d = new Date(date);
    return d.toLocaleDateString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      timeZone: 'Asia/Kolkata',
    });
  } catch {
    return date;
  }
}

/** Format a datetime string (ISO) to: 27 Mar 2026, 14:30 IST */
export function formatDateTime(date: string | null | undefined): string {
  if (!date) return '—';
  try {
    const d = new Date(date);
    return d.toLocaleString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
      timeZone: 'Asia/Kolkata',
    });
  } catch {
    return date;
  }
}

/** Format a time only: 14:30 */
export function formatTime(date: string | null | undefined): string {
  if (!date) return '—';
  try {
    const d = new Date(date);
    return d.toLocaleTimeString('en-IN', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
      timeZone: 'Asia/Kolkata',
    });
  } catch {
    return date;
  }
}

/** P&L Tailwind color class */
export function pnlColor(value: number | string): string {
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(num)) return 'text-white/50';
  return num >= 0 ? 'text-profit' : 'text-loss';
}

/** Regime color class */
export function regimeColor(regime: RegimeClass | string): string {
  switch (regime) {
    case 'green':
      return 'text-regime-green';
    case 'mixed':
      return 'text-regime-mixed';
    case 'stressed':
      return 'text-regime-stressed';
    default:
      return 'text-white/50';
  }
}

/** Risk utilization Tailwind color class (green < 60%, amber 60-85%, red > 85%) */
export function utilizationColor(pct: number | string): string {
  const num = typeof pct === 'string' ? parseFloat(pct) : pct;
  if (isNaN(num)) return 'text-white/50';
  if (num < 60) return 'text-profit';
  if (num < 85) return 'text-warning';
  return 'text-loss';
}

/** Utilization background color for progress bars */
export function utilizationBgColor(pct: number | string): string {
  const num = typeof pct === 'string' ? parseFloat(pct) : pct;
  if (isNaN(num)) return 'bg-white/20';
  if (num < 60) return 'bg-profit';
  if (num < 85) return 'bg-warning';
  return 'bg-loss';
}

/** Mode display label */
export function modeLabel(mode: Mode): string {
  switch (mode) {
    case 'paper':
      return 'PAPER';
    case 'shadow-live':
      return 'SHADOW-LIVE';
    case 'live':
      return 'LIVE';
    default:
      return mode.toUpperCase();
  }
}

/** Mode badge variant */
export function modeVariant(mode: Mode): 'blue' | 'amber' | 'red' {
  switch (mode) {
    case 'paper':
      return 'blue';
    case 'shadow-live':
      return 'amber';
    case 'live':
      return 'red';
  }
}

/** Regime display label */
export function regimeLabel(regime: RegimeClass): string {
  return regime.toUpperCase();
}

/** Truncate order ID for display */
export function shortId(id: string): string {
  return id.length > 8 ? id.slice(0, 8).toUpperCase() : id.toUpperCase();
}

/** Parse float safely */
export function safeFloat(val: string | number | null | undefined): number {
  if (val === null || val === undefined) return 0;
  const n = typeof val === 'number' ? val : parseFloat(String(val));
  return isNaN(n) ? 0 : n;
}

/** Distance to stop color */
export function distanceToStopColor(pct: string | number): string {
  const n = safeFloat(pct);
  if (n < 1) return 'text-loss';
  if (n < 2) return 'text-warning';
  return 'text-white/70';
}

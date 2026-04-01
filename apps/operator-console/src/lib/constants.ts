import type { RegimeClass, Mode, PortfolioLayer, OrderStatus } from './types';

export const REGIME_COLORS: Record<RegimeClass, string> = {
  green: '#22c55e',
  mixed: '#f59e0b',
  stressed: '#8b5cf6',
};

export const REGIME_SIZING: Record<RegimeClass, string> = {
  green: '1.0×',
  mixed: '0.5×',
  stressed: '0.0×',
};

export const MODE_COLORS: Record<Mode, string> = {
  paper: '#3b82f6',
  'shadow-live': '#f59e0b',
  live: '#ef4444',
};

export const LAYER_COLORS: Record<PortfolioLayer, string> = {
  core: '#3b82f6',
  swing: '#f59e0b',
};

export const ORDER_STATUS_COLORS: Record<OrderStatus, string> = {
  pending: '#f59e0b',
  submitted: '#3b82f6',
  filled: '#22c55e',
  partially_filled: '#8b5cf6',
  cancelled: '#6b7280',
  rejected: '#ef4444',
  expired: '#6b7280',
};

export const NAV_ITEMS = [
  { label: 'Dashboard', icon: '◉', href: '/dashboard' },
  { label: "Today's Plan", icon: '▤', href: '/plan' },
  { label: 'Positions', icon: '▦', href: '/positions' },
  { label: 'Trades', icon: '⇄', href: '/trades' },
  { label: 'Risk Center', icon: '⚠', href: '/risk' },
  { label: 'Bot Runs', icon: '⚙', href: '/runs' },
  { label: 'Config', icon: '⚡', href: '/config' },
  { label: 'Alerts', icon: '◎', href: '/alerts' },
  { label: 'Commands', icon: '⌘', href: '/commands' },
  { label: 'Compliance', icon: '✓', href: '/compliance' },
  { label: 'Shadow', icon: '◐', href: '/shadow' },
  { label: 'Live', icon: '●', href: '/live' },
  { label: 'Simulation', icon: '▶', href: '/simulation' },
] as const;

export const POLL_INTERVAL_DASHBOARD = 30_000; // 30s
export const POLL_INTERVAL_POSITIONS = 60_000; // 60s
export const POLL_INTERVAL_ALERTS = 30_000; // 30s

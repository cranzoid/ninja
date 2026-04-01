'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { NAV_ITEMS } from '@/lib/constants';
import { useDashboard } from '@/hooks/useDashboard';
import { RegimeBadge } from '@/components/shared/RegimeBadge';
import { Badge } from '@/components/ui/Badge';
import { StatusDot } from '@/components/ui/StatusDot';
import { formatDateTime, modeLabel, modeVariant, safeFloat, formatINR } from '@/lib/utils';

export function Sidebar() {
  const pathname = usePathname();
  const { data } = useDashboard();

  const mode = data?.mode ?? 'paper';
  const regime = data?.regime ?? null;
  const health = data?.system_health ?? null;
  const alertsCount = data?.alerts_count_today ?? 0;

  return (
    <aside
      className="flex-shrink-0 flex flex-col h-screen overflow-hidden"
      style={{
        width: '240px',
        background: '#0d0d14',
        borderRight: '1px solid rgba(255,255,255,0.06)',
      }}
    >
      {/* Brand */}
      <div className="px-5 pt-5 pb-4" style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div className="text-xs font-semibold tracking-widest text-white/40 uppercase">
          Indian Equities
        </div>
        <div className="text-2xs font-mono text-white/20 tracking-widest uppercase mt-0.5">
          Trading Platform
        </div>
        <div className="flex items-center gap-2 mt-3">
          <Badge label={modeLabel(mode)} variant={modeVariant(mode)} />
          {regime && (
            <RegimeBadge regime={regime.regime_class} showMultiplier />
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-2">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(item.href + '/');
          return (
            <Link
              key={item.href}
              href={item.href}
              className={[
                'flex items-center gap-3 px-5 py-2.5 text-sm transition-colors relative',
                isActive
                  ? 'text-white bg-white/5'
                  : 'text-white/50 hover:text-white/80 hover:bg-white/[0.03]',
              ].join(' ')}
              style={
                isActive
                  ? { borderLeft: '2px solid #3b82f6', paddingLeft: '18px' }
                  : { borderLeft: '2px solid transparent', paddingLeft: '18px' }
              }
            >
              <span className="text-base w-4 text-center flex-shrink-0 font-mono">
                {item.icon}
              </span>
              <span className="flex-1">{item.label}</span>
              {item.label === 'Alerts' && alertsCount > 0 && (
                <span
                  className="text-2xs font-mono px-1.5 py-0.5 rounded-full text-white"
                  style={{ background: '#ef4444', minWidth: '18px', textAlign: 'center' }}
                >
                  {alertsCount > 99 ? '99+' : alertsCount}
                </span>
              )}
              {item.label === 'Live' && (
                <span
                  className="w-2 h-2 rounded-full flex-shrink-0"
                  style={{ background: '#ef4444' }}
                />
              )}
            </Link>
          );
        })}
      </nav>

      {/* Footer — system health */}
      <div
        className="px-5 py-4"
        style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}
      >
        <div className="flex items-center gap-2 mb-2">
          <StatusDot
            status={
              health?.broker_healthy && health?.ledger_healthy
                ? 'healthy'
                : health?.broker_healthy || health?.ledger_healthy
                ? 'warning'
                : 'error'
            }
            pulse={health?.broker_healthy && health?.ledger_healthy}
          />
          <span className="text-xs text-white/40">System Health</span>
        </div>
        {health?.last_run_time && (
          <div className="text-2xs font-mono text-white/25 leading-tight">
            Last run: {formatDateTime(health.last_run_time)}
          </div>
        )}
        {data && (
          <div className="text-2xs font-mono text-white/25 mt-1">
            Equity: {formatINR(safeFloat(data.portfolio_equity))}
          </div>
        )}
      </div>
    </aside>
  );
}

'use client';

import { PageWrapper } from '@/components/layout/PageWrapper';
import { Card } from '@/components/ui/Card';
import { MetricCard } from '@/components/ui/MetricCard';
import { StatusDot } from '@/components/ui/StatusDot';
import { Badge } from '@/components/ui/Badge';
import { RegimeBadge } from '@/components/shared/RegimeBadge';
import { PnlDisplay } from '@/components/shared/PnlDisplay';
import { SymbolLink } from '@/components/shared/SymbolLink';
import { SkeletonCard } from '@/components/ui/SkeletonLoader';
import { useDashboard } from '@/hooks/useDashboard';
import { useApi, usePaginatedApi } from '@/hooks/useApi';
import type { PositionDetail, AuditEvent } from '@/lib/types';
import {
  formatINR,
  formatINRSigned,
  formatDateTime,
  formatPct,
  utilizationColor,
  safeFloat,
  modeLabel,
  modeVariant,
} from '@/lib/utils';

function ErrorCard({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div
      className="p-4 rounded-sm text-sm text-loss/80"
      style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)' }}
    >
      <div className="mb-2">{message}</div>
      <button
        onClick={onRetry}
        className="text-xs text-white/40 hover:text-white/70 underline transition-colors"
      >
        Retry
      </button>
    </div>
  );
}

export default function DashboardPage() {
  const { data, loading, error, refetch } = useDashboard();

  // Top positions
  const { data: posData } = usePaginatedApi<PositionDetail>(
    '/api/positions?sort_by=pnl&sort_order=desc&page_size=5',
  );

  // Today's alerts
  const { data: alertsData } = useApi<AuditEvent[]>('/api/alerts/today');

  if (loading && !data) {
    return (
      <PageWrapper title="Dashboard">
        <div className="grid grid-cols-4 gap-4 mb-4">
          {[1, 2, 3, 4].map((i) => <SkeletonCard key={i} lines={2} />)}
        </div>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <SkeletonCard lines={5} />
          <SkeletonCard lines={5} />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <SkeletonCard lines={5} />
          <SkeletonCard lines={5} />
        </div>
      </PageWrapper>
    );
  }

  if (error && !data) {
    return (
      <PageWrapper title="Dashboard">
        <ErrorCard message={`Failed to load dashboard: ${error}`} onRetry={refetch} />
      </PageWrapper>
    );
  }

  const equity = safeFloat(data?.portfolio_equity);
  const pnl = safeFloat(data?.todays_pnl);
  const openRisk = safeFloat(data?.open_risk_pct);
  const totalPositions = data?.total_positions ?? 0;
  const regime = data?.regime;
  const health = data?.system_health;
  const lastRun = data?.last_eod_run;

  const topPositions = posData?.data ?? [];
  const recentAlerts = (alertsData ?? []).slice(0, 5);

  return (
    <PageWrapper title="Dashboard" dashboardData={data}>
      {/* Row 1: Key Metrics */}
      <div className="grid grid-cols-4 gap-4 mb-4">
        <MetricCard
          label="Portfolio Equity"
          value={formatINR(equity)}
          subValue={`Cash: ${formatINR(safeFloat(data?.portfolio_cash))}`}
        />
        <MetricCard
          label="Today's P&L"
          value={formatINRSigned(pnl)}
          color={pnl >= 0 ? '#22c55e' : '#ef4444'}
          trend={pnl > 0 ? 'up' : pnl < 0 ? 'down' : 'flat'}
          subValue={`Unrealized: ${formatINRSigned(safeFloat(data?.total_unrealized_pnl))}`}
        />
        <MetricCard
          label="Open Risk"
          value={formatPct(openRisk)}
          color={
            openRisk < 2 ? '#22c55e' : openRisk < 3.5 ? '#f59e0b' : '#ef4444'
          }
          subValue={`Limit: 4.00%`}
        />
        <MetricCard
          label="Positions"
          value={String(totalPositions)}
          subValue={`${data?.pending_orders ?? 0} pending orders`}
        />
      </div>

      {/* Row 2: Status + Activity */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        {/* System Status */}
        <Card title="System Status">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-white/40">Mode</span>
              {data && <Badge label={modeLabel(data.mode)} variant={modeVariant(data.mode)} size="md" />}
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-white/40">Regime</span>
              {regime && <RegimeBadge regime={regime.regime_class} showMultiplier size="md" />}
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-white/40">Live Ready</span>
              <Badge label="Not Ready" variant="red" size="md" />
            </div>
            {regime && (
              <div className="text-xs text-white/30 italic leading-relaxed border-t border-white/5 pt-2">
                {regime.rationale}
              </div>
            )}
            <div
              className="pt-2 space-y-2"
              style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}
            >
              <div className="flex items-center justify-between">
                <StatusDot
                  status={health?.data_feed_fresh ? 'healthy' : 'error'}
                  label="Data Feed"
                />
                <span className="text-xs text-white/25 font-mono">
                  {health?.data_feed_fresh ? 'FRESH' : 'STALE'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <StatusDot
                  status={health?.broker_healthy ? 'healthy' : 'error'}
                  label="Broker"
                />
                <span className="text-xs text-white/25 font-mono">
                  {health?.broker_healthy ? 'OK' : 'DEGRADED'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <StatusDot
                  status={health?.ledger_healthy ? 'healthy' : 'error'}
                  label="Audit Ledger"
                />
                <span className="text-xs text-white/25 font-mono">
                  {health?.ledger_healthy ? 'OK' : 'ERROR'}
                </span>
              </div>
              {health?.last_run_time && (
                <div className="flex items-center justify-between">
                  <span className="text-xs text-white/30">Last EOD Run</span>
                  <span className="text-xs font-mono text-white/25">
                    {formatDateTime(health.last_run_time)}
                  </span>
                </div>
              )}
            </div>
          </div>
        </Card>

        {/* Today's Activity */}
        <Card title="Today's Activity">
          {lastRun ? (
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-xs text-white/40">Trading Date</span>
                <span className="text-xs font-mono text-white/60">{lastRun.trading_date}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-xs text-white/40">Candidates Scanned</span>
                <span className="text-xs font-mono text-white/60">{lastRun.candidates_scanned}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-xs text-white/40">Entries Approved</span>
                <span className="text-xs font-mono text-profit">{lastRun.entries_approved}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-xs text-white/40">Entries Rejected</span>
                <span className="text-xs font-mono text-white/50">{lastRun.entries_rejected}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-xs text-white/40">Exits Triggered</span>
                <span className="text-xs font-mono text-warning">{lastRun.exits_triggered}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-xs text-white/40">Orders Filled</span>
                <span className="text-xs font-mono text-info">{lastRun.orders_filled}</span>
              </div>
              <div
                className="flex justify-between pt-2"
                style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}
              >
                <span className="text-xs text-white/40">Reconciliation</span>
                <span
                  className={`text-xs font-mono ${lastRun.reconciliation.is_clean ? 'text-profit' : 'text-loss'}`}
                >
                  {lastRun.reconciliation.is_clean ? 'CLEAN' : 'ISSUES'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-xs text-white/40">Alerts Today</span>
                <span className="text-xs font-mono text-warning">
                  {data?.alerts_count_today ?? 0}
                </span>
              </div>
            </div>
          ) : (
            <div className="text-sm text-white/25 py-4 text-center">
              No EOD runs completed yet. Run EOD from Today's Plan.
            </div>
          )}
        </Card>
      </div>

      {/* Row 3: Top Positions + Recent Alerts */}
      <div className="grid grid-cols-2 gap-4">
        {/* Top Positions */}
        <Card title="Top Positions" subtitle="By P&L">
          {topPositions.length === 0 ? (
            <div className="text-sm text-white/25 py-4 text-center">
              No open positions. Run a simulation to generate data.
            </div>
          ) : (
            <table className="w-full" style={{ borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Symbol', 'Layer', 'P&L', 'Risk %'].map((h) => (
                    <th
                      key={h}
                      className="pb-2 text-2xs font-semibold uppercase tracking-widest text-white/30 text-left last:text-right"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {topPositions.map((p) => (
                  <tr
                    key={p.symbol}
                    style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}
                  >
                    <td className="py-2 pr-3">
                      <SymbolLink symbol={p.symbol} />
                    </td>
                    <td className="py-2 pr-3">
                      <span
                        className="text-2xs font-mono uppercase"
                        style={{
                          color: p.layer === 'core' ? '#3b82f6' : '#f59e0b',
                        }}
                      >
                        {p.layer}
                      </span>
                    </td>
                    <td className="py-2 pr-3">
                      <PnlDisplay value={p.unrealized_pnl} size="sm" />
                    </td>
                    <td className="py-2 text-right">
                      <span
                        className={`text-sm font-mono ${utilizationColor(safeFloat(p.risk_pct_of_equity) * 25)}`}
                      >
                        {formatPct(p.risk_pct_of_equity)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        {/* Recent Alerts */}
        <Card title="Recent Alerts" subtitle="Today">
          {recentAlerts.length === 0 ? (
            <div className="text-sm text-white/25 py-4 text-center">
              No alerts today.
            </div>
          ) : (
            <div className="space-y-2">
              {recentAlerts.map((a) => (
                <div
                  key={a.event_id}
                  className="flex items-start gap-3 py-2"
                  style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}
                >
                  <span className="text-2xs font-mono text-white/25 whitespace-nowrap mt-0.5">
                    {formatDateTime(a.timestamp).split(',')[1]?.trim() ?? ''}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-mono text-info">
                      {a.event_type}
                    </div>
                    {a.related_symbol && (
                      <div className="text-xs text-white/40">{a.related_symbol}</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </PageWrapper>
  );
}

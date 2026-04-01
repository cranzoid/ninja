'use client';

import { PageWrapper } from '@/components/layout/PageWrapper';
import { Card } from '@/components/ui/Card';
import { MetricCard } from '@/components/ui/MetricCard';
import { Badge } from '@/components/ui/Badge';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { RiskMeter } from '@/components/shared/RiskMeter';
import { SymbolLink } from '@/components/shared/SymbolLink';
import { SkeletonCard } from '@/components/ui/SkeletonLoader';
import { useApi } from '@/hooks/useApi';
import type { RiskCenterData } from '@/lib/types';
import { formatINR, formatPct, safeFloat } from '@/lib/utils';

export default function RiskPage() {
  const { data, loading, error, refetch } = useApi<RiskCenterData>(
    '/api/risk/current',
    { refreshInterval: 60_000 },
  );

  if (loading && !data) {
    return (
      <PageWrapper title="Risk Center">
        <div className="grid grid-cols-4 gap-4 mb-4">
          {[1, 2, 3, 4].map((i) => <SkeletonCard key={i} lines={2} />)}
        </div>
        <SkeletonCard lines={6} />
      </PageWrapper>
    );
  }

  if (error) {
    return (
      <PageWrapper title="Risk Center">
        <div
          className="p-4 rounded-sm text-sm text-loss/80"
          style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)' }}
        >
          {error}{' '}
          <button onClick={refetch} className="underline text-white/40 hover:text-white/60">Retry</button>
        </div>
      </PageWrapper>
    );
  }

  const pr = data?.portfolio_risk;
  const limits = data?.risk_limits;
  const lu = data?.limit_utilization;
  const breakdown = data?.position_risk_breakdown ?? [];
  const sectorUtil = Object.values(lu?.sector_utilization ?? {});

  const aggRiskPct = safeFloat(lu?.aggregate_risk_utilization_pct);

  return (
    <PageWrapper title="Risk Center">
      {/* Row 1: Overview metrics */}
      <div className="grid grid-cols-4 gap-4 mb-4">
        <MetricCard
          label="Aggregate Open Risk"
          value={formatPct(pr?.open_risk_pct ?? 0)}
          subValue={`Limit: ${formatPct(limits?.aggregate_open_risk_pct ?? 4)}`}
          color={aggRiskPct < 60 ? '#22c55e' : aggRiskPct < 85 ? '#f59e0b' : '#ef4444'}
        />
        <MetricCard
          label="Largest Position"
          value={formatPct(pr?.largest_position_pct ?? 0)}
          subValue="% of equity"
        />
        <MetricCard
          label="Positions"
          value={String(pr?.position_count ?? 0)}
          subValue="open positions"
        />
        <MetricCard
          label="Sectors Exposed"
          value={String(Object.keys(pr?.sector_exposure ?? {}).length)}
          subValue={lu?.worst_sector ? `Worst: ${lu.worst_sector}` : 'No exposure'}
        />
      </div>

      {/* Row 2: Limit utilization */}
      <Card title="Limit Utilization" className="mb-4">
        <div className="space-y-4">
          {lu && (
            <RiskMeter
              current={lu.aggregate_risk_used_pct}
              limit={lu.aggregate_risk_limit_pct}
              label="Aggregate Open Risk"
              currentLabel={`${safeFloat(lu.aggregate_risk_used_pct).toFixed(2)}%`}
              limitLabel={`${safeFloat(lu.aggregate_risk_limit_pct).toFixed(2)}%`}
            />
          )}
          {limits && (
            <>
              <ProgressBar
                value={0}
                max={safeFloat(limits.core_position_cap_pct)}
                label="Core Position Cap"
                showValues
                valueLabel="—"
                maxLabel={`${limits.core_position_cap_pct}%`}
              />
              <ProgressBar
                value={0}
                max={safeFloat(limits.swing_position_cap_pct)}
                label="Swing Position Cap"
                showValues
                valueLabel="—"
                maxLabel={`${limits.swing_position_cap_pct}%`}
              />
            </>
          )}
        </div>

        {/* Sector breakdown table */}
        {sectorUtil.length > 0 && (
          <div className="mt-4 pt-4" style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
            <div className="text-xs font-semibold uppercase tracking-widest text-white/30 mb-3">
              Sector Breakdown
            </div>
            <table className="w-full" style={{ borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Sector', 'Exposure %', 'Limit %', 'Utilization %'].map((h) => (
                    <th
                      key={h}
                      className="pb-2 text-2xs font-semibold uppercase tracking-widest text-white/25 text-left last:text-right"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sectorUtil.map((s) => (
                  <tr
                    key={s.sector}
                    style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}
                  >
                    <td className="py-2 text-sm text-white/60">{s.sector}</td>
                    <td className="py-2 font-mono text-sm text-white/60">
                      {formatPct(s.exposure_pct)}
                    </td>
                    <td className="py-2 font-mono text-sm text-white/40">
                      {formatPct(s.limit_pct)}
                    </td>
                    <td className="py-2 font-mono text-sm text-right">
                      <span
                        className={
                          safeFloat(s.utilization_pct) < 60
                            ? 'text-profit'
                            : safeFloat(s.utilization_pct) < 85
                            ? 'text-warning'
                            : 'text-loss'
                        }
                      >
                        {formatPct(s.utilization_pct)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Row 3: Position risk breakdown */}
      <Card title="Position Risk Breakdown">
        {breakdown.length === 0 ? (
          <div className="text-sm text-white/25 py-4 text-center">
            No open positions.
          </div>
        ) : (
          <table className="w-full" style={{ borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.02)' }}>
                {['Symbol', 'Layer', 'Risk ₹', 'Risk %', 'Position %', 'Sector'].map((h, i) => (
                  <th
                    key={h}
                    className={`px-4 py-2.5 text-2xs font-semibold uppercase tracking-widest text-white/30 ${i > 1 ? 'text-right' : 'text-left'}`}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {breakdown.map((row, idx) => {
                const riskPct = safeFloat(row.risk_pct);
                const overCap = riskPct > safeFloat(limits?.swing_risk_per_trade_pct ?? 0.5);
                return (
                  <tr
                    key={row.symbol}
                    style={{
                      borderBottom: '1px solid rgba(255,255,255,0.04)',
                      background: overCap
                        ? 'rgba(239,68,68,0.06)'
                        : idx % 2 === 1
                        ? 'rgba(255,255,255,0.015)'
                        : undefined,
                    }}
                  >
                    <td className="px-4 py-2.5">
                      <SymbolLink symbol={row.symbol} />
                    </td>
                    <td className="px-4 py-2.5">
                      <Badge
                        label={row.layer.toUpperCase()}
                        variant={row.layer === 'core' ? 'blue' : 'amber'}
                      />
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-sm text-loss">
                      {formatINR(safeFloat(row.risk_amount))}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-sm text-loss">
                      {formatPct(row.risk_pct)}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-sm text-white/60">
                      {formatPct(row.position_pct)}
                    </td>
                    <td className="px-4 py-2.5 text-right text-sm text-white/40">
                      {row.sector}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>
    </PageWrapper>
  );
}

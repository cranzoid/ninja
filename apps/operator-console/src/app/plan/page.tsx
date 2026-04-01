'use client';

import { useState } from 'react';
import { PageWrapper } from '@/components/layout/PageWrapper';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { RegimeBadge } from '@/components/shared/RegimeBadge';
import { SymbolLink } from '@/components/shared/SymbolLink';
import { SkeletonCard } from '@/components/ui/SkeletonLoader';
import { useApi } from '@/hooks/useApi';
import { postApi } from '@/lib/api';
import type { TodaysPlan, EODRunReport } from '@/lib/types';
import {
  formatDate,
  formatDateTime,
  formatINR,
  formatPct,
  distanceToStopColor,
  safeFloat,
} from '@/lib/utils';

export default function PlanPage() {
  const { data, loading, error, refetch } = useApi<TodaysPlan>('/api/plan/today', {
    refreshInterval: 60_000,
  });

  const [runLoading, setRunLoading] = useState(false);
  const [runResult, setRunResult] = useState<EODRunReport | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  const handleRunEOD = async () => {
    setRunLoading(true);
    setRunError(null);
    try {
      const today = new Date().toISOString().split('T')[0];
      const res = await postApi<EODRunReport>('/api/plan/run-eod', { trading_date: today });
      if (res.success && res.data) {
        setRunResult(res.data);
        refetch();
      } else {
        setRunError(res.error ?? 'EOD run failed');
      }
    } catch (e) {
      setRunError(e instanceof Error ? e.message : 'EOD run failed');
    } finally {
      setRunLoading(false);
    }
  };

  if (loading && !data) {
    return (
      <PageWrapper title="Today's Plan">
        <SkeletonCard lines={3} />
      </PageWrapper>
    );
  }

  const regime = data?.regime;

  return (
    <PageWrapper title="Today's Plan">
      {/* Row 1: Regime Card */}
      {regime && (
        <Card title="Market Regime" className="mb-4">
          <div className="flex items-start gap-6">
            <div className="flex-shrink-0">
              <RegimeBadge regime={regime.regime_class} showMultiplier size="md" />
            </div>
            <div className="grid grid-cols-4 gap-4 flex-1 text-xs">
              <div>
                <div className="text-white/30 mb-1">NIFTY50 Trend</div>
                <div className="font-mono text-white/70 uppercase">{regime.nifty50_trend}</div>
              </div>
              <div>
                <div className="text-white/30 mb-1">Breadth &gt;50DMA</div>
                <div className="font-mono text-white/70">{formatPct(regime.breadth_above_50dma_pct)}</div>
              </div>
              <div>
                <div className="text-white/30 mb-1">VIX</div>
                <div className="font-mono text-white/70">
                  {regime.vix_level ?? '—'} ({regime.vix_state})
                </div>
              </div>
              <div>
                <div className="text-white/30 mb-1">Sizing Multiplier</div>
                <div className="font-mono text-white/70">{regime.sizing_multiplier}×</div>
              </div>
              <div>
                <div className="text-white/30 mb-1">Breadth &gt;200DMA</div>
                <div className="font-mono text-white/70">{formatPct(regime.breadth_above_200dma_pct)}</div>
              </div>
              <div>
                <div className="text-white/30 mb-1">Gap Freq (5d)</div>
                <div className="font-mono text-white/70">{regime.gap_frequency_5d}</div>
              </div>
              <div>
                <div className="text-white/30 mb-1">Correlation</div>
                <div className="font-mono text-white/70 capitalize">{regime.correlation_state}</div>
              </div>
              <div>
                <div className="text-white/30 mb-1">Sector Conc.</div>
                <div className="font-mono text-white/70">{safeFloat(regime.sector_concentration_score).toFixed(2)}</div>
              </div>
            </div>
          </div>
          {regime.rationale && (
            <div className="mt-3 pt-3 text-xs text-white/30 italic" style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
              {regime.rationale}
            </div>
          )}
        </Card>
      )}

      {/* Row 2: Pending Orders + Exit Watchlist */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        <Card
          title="Pending Orders"
          subtitle={`${(data?.pending_entries?.length ?? 0) + (data?.pending_exits?.length ?? 0)} orders`}
        >
          {(!data?.pending_entries?.length && !data?.pending_exits?.length) ? (
            <div className="text-sm text-white/25 py-2">No pending orders.</div>
          ) : (
            <table className="w-full text-xs" style={{ borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Symbol', 'Side', 'Qty', 'Type', 'Status'].map((h) => (
                    <th key={h} className="pb-2 text-left text-2xs font-semibold uppercase tracking-widest text-white/25">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...(data?.pending_entries ?? []), ...(data?.pending_exits ?? [])].map((o) => (
                  <tr key={o.order_id} style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
                    <td className="py-1.5"><SymbolLink symbol={o.intent.symbol} /></td>
                    <td className="py-1.5">
                      <Badge
                        label={o.intent.side.toUpperCase()}
                        variant={o.intent.side === 'buy' ? 'green' : 'red'}
                      />
                    </td>
                    <td className="py-1.5 font-mono text-white/60">{o.intent.quantity}</td>
                    <td className="py-1.5 font-mono text-white/40 uppercase">{o.intent.order_type}</td>
                    <td className="py-1.5 font-mono text-info uppercase">{o.current_status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        <Card title="Exit Watchlist" subtitle="Approaching triggers">
          {!data?.exit_watchlist?.length ? (
            <div className="text-sm text-white/25 py-2">No positions approaching exit triggers.</div>
          ) : (
            <table className="w-full text-xs" style={{ borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Symbol', 'Layer', 'Dist Stop', 'Dist 2R', 'Days <200'].map((h) => (
                    <th key={h} className="pb-2 text-left text-2xs font-semibold uppercase tracking-widest text-white/25">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.exit_watchlist.map((w) => (
                  <tr key={w.symbol} style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
                    <td className="py-1.5"><SymbolLink symbol={w.symbol} /></td>
                    <td className="py-1.5">
                      <Badge label={w.layer.toUpperCase()} variant={w.layer === 'core' ? 'blue' : 'amber'} />
                    </td>
                    <td className={`py-1.5 font-mono ${distanceToStopColor(w.distance_to_stop_pct)}`}>
                      {formatPct(w.distance_to_stop_pct)}
                    </td>
                    <td className="py-1.5 font-mono text-info">
                      {w.distance_to_2r_pct !== null ? formatPct(w.distance_to_2r_pct ?? 0) : '—'}
                    </td>
                    <td className="py-1.5 font-mono text-white/40">{w.days_below_200dma}d</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>

      {/* Row 3: Candidate Preview */}
      <Card title="Candidate Preview" subtitle="Latest scan results" className="mb-4">
        {!data?.candidate_preview?.length ? (
          <div className="text-sm text-white/25 py-2">
            No candidates from latest scan. Run EOD to generate.
          </div>
        ) : (
          <table className="w-full text-xs" style={{ borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Symbol', 'Close', 'Entry Est', 'Stop', 'Volume Ratio', 'Passes'].map((h) => (
                  <th key={h} className="pb-2 text-left text-2xs font-semibold uppercase tracking-widest text-white/25">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.candidate_preview.map((c) => (
                <tr key={c.symbol} style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
                  <td className="py-1.5"><SymbolLink symbol={c.symbol} /></td>
                  <td className="py-1.5 font-mono text-white/60">{formatINR(safeFloat(c.close))}</td>
                  <td className="py-1.5 font-mono text-white/60">{formatINR(safeFloat(c.entry_price))}</td>
                  <td className="py-1.5 font-mono text-loss">{formatINR(safeFloat(c.stop_price))}</td>
                  <td className="py-1.5 font-mono text-white/60">{safeFloat(c.volume_ratio).toFixed(2)}×</td>
                  <td className="py-1.5">
                    <Badge label={c.passes_all ? 'YES' : 'NO'} variant={c.passes_all ? 'green' : 'red'} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {/* Row 4: Blocked Symbols */}
      {(data?.blocked_symbols?.length ?? 0) > 0 && (
        <Card title="Blocked Symbols" className="mb-4">
          <div className="flex flex-wrap gap-2">
            {data?.blocked_symbols.map((b) => (
              <div
                key={b.symbol}
                className="flex items-center gap-2 px-3 py-1.5 rounded-sm"
                style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.15)' }}
              >
                <span className="font-mono text-sm text-loss/80">{b.symbol}</span>
                <span className="text-2xs text-white/30">
                  {b.blocker_categories.join(', ')}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Row 5: Run EOD Button */}
      <Card title="Run EOD Workflow">
        <div className="flex items-start gap-4">
          <div className="flex-1 text-sm text-white/50">
            Manually trigger the end-of-day workflow for today. This runs data
            ingest, candidate scanning, rule engine, order generation, and
            reconciliation.
          </div>
          <div className="flex-shrink-0">
            <Button
              variant="primary"
              size="md"
              loading={runLoading}
              onClick={handleRunEOD}
              disabled={runLoading}
            >
              {runLoading ? 'Running…' : '▶ Run EOD Now'}
            </Button>
          </div>
        </div>

        {runError && (
          <div
            className="mt-3 p-3 rounded-sm text-sm text-loss/80"
            style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)' }}
          >
            {runError}
          </div>
        )}

        {runResult && (
          <div
            className="mt-3 p-3 rounded-sm text-sm"
            style={{ background: 'rgba(34,197,94,0.06)', border: '1px solid rgba(34,197,94,0.2)' }}
          >
            <div className="flex items-center gap-2 mb-2">
              <span className="text-profit font-semibold">EOD Complete</span>
              <Badge
                label={runResult.is_successful ? 'SUCCESS' : 'ERRORS'}
                variant={runResult.is_successful ? 'green' : 'red'}
              />
            </div>
            <div className="grid grid-cols-4 gap-3 text-xs text-white/50">
              <div>Candidates: <span className="text-white/70 font-mono">{runResult.candidates_scanned}</span></div>
              <div>Entries: <span className="text-profit font-mono">{runResult.entries_approved}</span></div>
              <div>Exits: <span className="text-warning font-mono">{runResult.exits_triggered}</span></div>
              <div>Filled: <span className="text-info font-mono">{runResult.orders_filled}</span></div>
            </div>
            {runResult.errors.length > 0 && (
              <div className="mt-2 text-xs text-loss/70">
                Errors: {runResult.errors.join('; ')}
              </div>
            )}
          </div>
        )}
      </Card>
    </PageWrapper>
  );
}

'use client';

import { useState } from 'react';
import { PageWrapper } from '@/components/layout/PageWrapper';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { MetricCard } from '@/components/ui/MetricCard';
import { SkeletonCard } from '@/components/ui/SkeletonLoader';
import { RegimeBadge } from '@/components/shared/RegimeBadge';
import { usePaginatedApi } from '@/hooks/useApi';
import { postApi } from '@/lib/api';
import type { SimulationSummary } from '@/lib/types';
import { formatINR, formatPct, formatDate, safeFloat } from '@/lib/utils';

function SimResultCard({ sim }: { sim: SimulationSummary }) {
  const returnPct = safeFloat(sim.total_return_pct);
  const drawdownPct = safeFloat(sim.max_drawdown_pct);
  const winRate =
    sim.total_trades > 0
      ? ((sim.winning_trades / sim.total_trades) * 100).toFixed(1)
      : '0.0';

  return (
    <Card title="Simulation Results" className="mb-4">
      <div className="grid grid-cols-4 gap-4 mb-4">
        <MetricCard
          label="Total Return"
          value={`${returnPct >= 0 ? '+' : ''}${formatPct(returnPct)}`}
          color={returnPct >= 0 ? '#22c55e' : '#ef4444'}
          trend={returnPct > 0 ? 'up' : returnPct < 0 ? 'down' : 'flat'}
        />
        <MetricCard
          label="Max Drawdown"
          value={`-${formatPct(Math.abs(drawdownPct))}`}
          color="#ef4444"
        />
        <MetricCard
          label="Win Rate"
          value={`${winRate}%`}
          subValue={`${sim.winning_trades}W / ${sim.losing_trades}L`}
          color={parseFloat(winRate) > 50 ? '#22c55e' : '#f59e0b'}
        />
        <MetricCard
          label="Total Trades"
          value={String(sim.total_trades)}
          subValue={`${sim.trading_days_run} trading days`}
        />
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="space-y-2 text-xs">
          <div className="flex justify-between">
            <span className="text-white/40">Period</span>
            <span className="font-mono text-white/60">
              {formatDate(sim.start_date)} → {formatDate(sim.end_date)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-white/40">Initial Equity</span>
            <span className="font-mono text-white/60">{formatINR(safeFloat(sim.initial_equity))}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-white/40">Final Equity</span>
            <span className={`font-mono ${safeFloat(sim.final_equity) >= safeFloat(sim.initial_equity) ? 'text-profit' : 'text-loss'}`}>
              {formatINR(safeFloat(sim.final_equity))}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-white/40">Reconciliations Clean</span>
            <Badge
              label={sim.all_reconciliations_clean ? 'ALL CLEAN' : 'ISSUES'}
              variant={sim.all_reconciliations_clean ? 'green' : 'red'}
            />
          </div>
        </div>
        {sim.errors_encountered.length > 0 && (
          <div>
            <div className="text-xs text-loss/60 font-semibold mb-2">Errors Encountered:</div>
            {sim.errors_encountered.map((e, i) => (
              <div key={i} className="text-xs text-loss/50 mb-1">{e}</div>
            ))}
          </div>
        )}
      </div>

      {/* Daily reports mini-table */}
      {sim.daily_reports.length > 0 && (
        <div>
          <div
            className="text-xs font-semibold uppercase tracking-widest text-white/30 mb-2"
            style={{ borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '12px' }}
          >
            Daily Reports ({sim.daily_reports.length})
          </div>
          <div className="max-h-48 overflow-y-auto">
            <table className="w-full text-xs" style={{ borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Date', 'Regime', 'Entries', 'Exits', 'Filled', 'Status'].map((h) => (
                    <th key={h} className="pb-1 text-left text-2xs font-semibold uppercase tracking-widest text-white/25">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sim.daily_reports.map((r) => (
                  <tr key={r.run_id} style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
                    <td className="py-1 font-mono text-white/50">{formatDate(r.trading_date)}</td>
                    <td className="py-1"><RegimeBadge regime={r.regime.regime_class} /></td>
                    <td className="py-1 font-mono text-profit">{r.entries_approved}</td>
                    <td className="py-1 font-mono text-warning">{r.exits_triggered}</td>
                    <td className="py-1 font-mono text-info">{r.orders_filled}</td>
                    <td className="py-1">
                      <Badge label={r.is_successful ? 'OK' : 'ERR'} variant={r.is_successful ? 'green' : 'red'} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Card>
  );
}

export default function SimulationPage() {
  const [startDate, setStartDate] = useState('2026-01-01');
  const [endDate, setEndDate] = useState('2026-03-27');
  const [initialEquity, setInitialEquity] = useState('500000');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<SimulationSummary | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  const { data: histData, loading: histLoading, refetch: histRefetch } = usePaginatedApi<SimulationSummary>(
    '/api/simulation/history?page=1&page_size=5',
  );

  const histSims = histData?.data ?? [];

  const errors: Record<string, string> = {};
  if (!startDate) errors.start = 'Start date required';
  if (!endDate) errors.end = 'End date required';
  if (startDate && endDate && startDate >= endDate) errors.end = 'End must be after start';
  const eq = parseFloat(initialEquity);
  if (isNaN(eq) || eq <= 0) errors.equity = 'Valid initial equity required';

  const handleRun = async () => {
    if (Object.keys(errors).length > 0) return;
    setRunning(true);
    setRunError(null);
    setResult(null);
    try {
      const res = await postApi<SimulationSummary>('/api/simulation/run', {
        start_date: startDate,
        end_date: endDate,
        initial_equity: parseFloat(initialEquity),
      });
      if (res.success && res.data) {
        setResult(res.data);
        histRefetch();
      } else {
        setRunError(res.error ?? 'Simulation failed');
      }
    } catch (e) {
      setRunError(e instanceof Error ? e.message : 'Simulation error');
    } finally {
      setRunning(false);
    }
  };

  return (
    <PageWrapper title="Simulation">
      {/* Run Form */}
      <Card title="Run Simulation" className="mb-4">
        <div className="grid grid-cols-4 gap-4 mb-4">
          <Input
            label="Start Date"
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            error={errors.start}
          />
          <Input
            label="End Date"
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            error={errors.end}
          />
          <Input
            label="Initial Equity (₹)"
            type="number"
            value={initialEquity}
            onChange={(e) => setInitialEquity(e.target.value)}
            error={errors.equity}
          />
          <div className="flex items-end">
            <Button
              variant="primary"
              size="md"
              className="w-full justify-center"
              loading={running}
              disabled={Object.keys(errors).length > 0 || running}
              onClick={handleRun}
            >
              {running ? 'Running…' : '▶ Run Simulation'}
            </Button>
          </div>
        </div>
        {running && (
          <div className="text-sm text-white/40 text-center py-2">
            Running simulation — this may take a moment for longer date ranges…
          </div>
        )}
        {runError && (
          <div
            className="p-3 rounded-sm text-sm text-loss/80"
            style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)' }}
          >
            {runError}
          </div>
        )}
      </Card>

      {/* Latest result */}
      {result && <SimResultCard sim={result} />}

      {/* History */}
      <Card title="Recent Simulations">
        {histLoading ? (
          <SkeletonCard lines={3} />
        ) : histSims.length === 0 ? (
          <div className="text-sm text-white/25 py-2">No simulations run yet.</div>
        ) : (
          <table className="w-full text-xs" style={{ borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Period', 'Days', 'Trades', 'Return', 'Drawdown', 'Win Rate', 'Clean'].map((h) => (
                  <th key={h} className="pb-2 text-left text-2xs font-semibold uppercase tracking-widest text-white/25">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {histSims.map((s) => {
                const ret = safeFloat(s.total_return_pct);
                const wr = s.total_trades > 0
                  ? ((s.winning_trades / s.total_trades) * 100).toFixed(1)
                  : '0.0';
                return (
                  <tr key={s.simulation_id} style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
                    <td className="py-1.5 font-mono text-white/50">
                      {formatDate(s.start_date)} → {formatDate(s.end_date)}
                    </td>
                    <td className="py-1.5 font-mono text-white/60">{s.trading_days_run}</td>
                    <td className="py-1.5 font-mono text-white/60">{s.total_trades}</td>
                    <td className={`py-1.5 font-mono ${ret >= 0 ? 'text-profit' : 'text-loss'}`}>
                      {ret >= 0 ? '+' : ''}{formatPct(ret)}
                    </td>
                    <td className="py-1.5 font-mono text-loss">
                      -{formatPct(Math.abs(safeFloat(s.max_drawdown_pct)))}
                    </td>
                    <td className="py-1.5 font-mono text-white/60">{wr}%</td>
                    <td className="py-1.5">
                      <Badge
                        label={s.all_reconciliations_clean ? 'YES' : 'NO'}
                        variant={s.all_reconciliations_clean ? 'green' : 'red'}
                      />
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

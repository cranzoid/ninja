'use client';

import { useState } from 'react';
import { PageWrapper } from '@/components/layout/PageWrapper';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { SkeletonCard } from '@/components/ui/SkeletonLoader';
import { useApi } from '@/hooks/useApi';
import { fetchApi } from '@/lib/api';
import type { ShadowRunReport, PaginatedResponse } from '@/lib/types';
import { formatDateTime } from '@/lib/utils';

function formatIST(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' });
  } catch {
    return dateStr;
  }
}

function todayIST(): string {
  const now = new Date();
  const ist = new Date(now.getTime() + (5.5 * 60 * 60 * 1000));
  return ist.toISOString().split('T')[0];
}

export default function ShadowPage() {
  const [tradingDate, setTradingDate] = useState(todayIST());
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<ShadowRunReport | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  const { data: runsData, loading: runsLoading, refetch: refetchRuns } = useApi<PaginatedResponse<ShadowRunReport>>(
    '/api/shadow/runs',
    { refreshInterval: 60_000 },
  );

  const handleRun = async () => {
    setRunning(true);
    setRunError(null);
    setResult(null);
    try {
      const json = await fetchApi<ShadowRunReport>('/api/shadow/run-eod', {
        method: 'POST',
        body: JSON.stringify({ trading_date: tradingDate }),
      });
      if (json.success && json.data) {
        setResult(json.data);
        refetchRuns();
      } else {
        setRunError(json.error ?? 'Unknown error');
      }
    } catch (e) {
      setRunError(String(e));
    } finally {
      setRunning(false);
    }
  };

  return (
    <PageWrapper title="Shadow Live">
      {/* Run form */}
      <Card title="Run Shadow EOD">
        <div className="flex items-end gap-4">
          <div className="flex-1">
            <label className="block text-xs text-white/40 mb-1 font-mono uppercase tracking-wider">
              Trading Date (IST)
            </label>
            <Input
              type="date"
              value={tradingDate}
              onChange={(e) => setTradingDate(e.target.value)}
            />
          </div>
          <Button
            variant="primary"
            size="sm"
            onClick={handleRun}
            disabled={running}
          >
            {running ? 'Running...' : 'Run Shadow EOD'}
          </Button>
        </div>

        {runError && (
          <div
            className="mt-3 p-3 rounded-sm text-sm text-loss/70"
            style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)' }}
          >
            {runError}
          </div>
        )}
      </Card>

      {/* Latest result */}
      {result && (
        <Card title="Shadow Run Result" className="mt-4">
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div>
              <div className="text-xs text-white/30 font-mono uppercase">Candidates Scanned</div>
              <div className="text-xl font-mono text-white/80">{result.candidates_scanned}</div>
            </div>
            <div>
              <div className="text-xs text-white/30 font-mono uppercase">Intents Generated</div>
              <div className="text-xl font-mono text-white/80">{result.intents_generated.length}</div>
            </div>
            <div>
              <div className="text-xs text-white/30 font-mono uppercase">Orders Dry-Run</div>
              <div className="text-xl font-mono text-white/80">{result.orders_dry_run.length}</div>
            </div>
            <div>
              <div className="text-xs text-white/30 font-mono uppercase">Blockers Triggered</div>
              <div className="text-xl font-mono text-white/80">{result.blockers_triggered.length}</div>
            </div>
            <div>
              <div className="text-xs text-white/30 font-mono uppercase">Audit Events</div>
              <div className="text-xl font-mono text-white/80">{result.audit_events_count}</div>
            </div>
            <div>
              <div className="text-xs text-white/30 font-mono uppercase">Regime</div>
              <div className="text-xl font-mono text-white/80">{result.regime_state}</div>
            </div>
          </div>

          {result.errors.length > 0 && (
            <div
              className="p-3 rounded-sm"
              style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)' }}
            >
              <div className="text-xs font-mono text-loss/70 font-semibold mb-1">Errors</div>
              {result.errors.map((err, i) => (
                <div key={i} className="text-xs text-white/40 font-mono">{err}</div>
              ))}
            </div>
          )}

          <div className="text-xs text-white/20 font-mono mt-3">
            Completed: {formatIST(result.completed_at)}
          </div>
        </Card>
      )}

      {/* Past runs */}
      <Card title="Past Shadow Runs" className="mt-4">
        {runsLoading && !runsData ? (
          <SkeletonCard lines={4} />
        ) : (runsData as PaginatedResponse<ShadowRunReport> | undefined)?.data?.length === 0 ? (
          <div className="text-sm text-white/25 py-4 text-center">No past shadow runs.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="text-left text-white/30 uppercase tracking-wider">
                  <th className="pb-2">Date</th>
                  <th className="pb-2">Regime</th>
                  <th className="pb-2">Candidates</th>
                  <th className="pb-2">Intents</th>
                  <th className="pb-2">Errors</th>
                  <th className="pb-2">Completed</th>
                </tr>
              </thead>
              <tbody>
                {((runsData as PaginatedResponse<ShadowRunReport> | undefined)?.data ?? []).map((run, i) => (
                  <tr
                    key={i}
                    className="text-white/50"
                    style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}
                  >
                    <td className="py-2">{run.trading_date}</td>
                    <td className="py-2">
                      <Badge label={run.regime_state} variant="neutral" />
                    </td>
                    <td className="py-2">{run.candidates_scanned}</td>
                    <td className="py-2">{run.intents_generated.length}</td>
                    <td className="py-2">
                      {run.errors.length > 0 ? (
                        <span className="text-loss">{run.errors.length}</span>
                      ) : (
                        <span className="text-profit">0</span>
                      )}
                    </td>
                    <td className="py-2">{formatIST(run.completed_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </PageWrapper>
  );
}

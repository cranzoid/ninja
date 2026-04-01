'use client';

import { useState } from 'react';
import { PageWrapper } from '@/components/layout/PageWrapper';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Pagination } from '@/components/ui/Table';
import { SkeletonTable } from '@/components/ui/SkeletonLoader';
import { RegimeBadge } from '@/components/shared/RegimeBadge';
import { usePaginatedApi } from '@/hooks/useApi';
import type { EODRunReport } from '@/lib/types';
import { formatDate, formatDateTime, formatPct, safeFloat } from '@/lib/utils';

export default function RunsPage() {
  const [page, setPage] = useState(1);
  const [expandedRun, setExpandedRun] = useState<string | null>(null);

  const { data, loading, error } = usePaginatedApi<EODRunReport>(
    `/api/runs?page=${page}&page_size=20`,
  );

  const runs = data?.data ?? [];
  const total = data?.total ?? 0;

  if (loading && !data) {
    return (
      <PageWrapper title="Bot Runs">
        <SkeletonTable rows={10} cols={8} />
      </PageWrapper>
    );
  }

  return (
    <PageWrapper title="Bot Runs">
      {error && (
        <div
          className="mb-4 p-3 rounded-sm text-sm text-loss/70"
          style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)' }}
        >
          {error}
        </div>
      )}

      {runs.length === 0 ? (
        <div
          className="p-8 text-center rounded-sm"
          style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}
        >
          <div className="text-white/25 text-sm">
            No bot runs yet. Run EOD from Today's Plan to get started.
          </div>
        </div>
      ) : (
        <>
          <div className="rounded-sm overflow-hidden" style={{ border: '1px solid rgba(255,255,255,0.06)' }}>
            <table className="w-full console-table" style={{ borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.02)' }}>
                  {['Date', 'Regime', 'Candidates', 'Entries', 'Exits', 'Filled', 'Risk %', 'Recon', 'Status'].map((h) => (
                    <th key={h} className="px-4 py-2.5 text-left text-2xs font-semibold uppercase tracking-widest text-white/30">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {runs.map((run, idx) => {
                  const isExpanded = expandedRun === run.run_id;
                  return (
                    <>
                      <tr
                        key={run.run_id}
                        className="cursor-pointer transition-colors"
                        style={{
                          borderBottom: '1px solid rgba(255,255,255,0.04)',
                          background: idx % 2 === 1 ? 'rgba(255,255,255,0.015)' : undefined,
                        }}
                        onClick={() => setExpandedRun(isExpanded ? null : run.run_id)}
                      >
                        <td className="px-4 py-2.5 font-mono text-sm text-white/70">{formatDate(run.trading_date)}</td>
                        <td className="px-4 py-2.5">
                          <RegimeBadge regime={run.regime.regime_class} />
                        </td>
                        <td className="px-4 py-2.5 font-mono text-sm text-white/60">{run.candidates_scanned}</td>
                        <td className="px-4 py-2.5 font-mono text-sm text-profit">{run.entries_approved}</td>
                        <td className="px-4 py-2.5 font-mono text-sm text-warning">{run.exits_triggered}</td>
                        <td className="px-4 py-2.5 font-mono text-sm text-info">{run.orders_filled}</td>
                        <td className="px-4 py-2.5 font-mono text-sm text-white/60">{formatPct(run.portfolio_risk.open_risk_pct)}</td>
                        <td className="px-4 py-2.5">
                          <Badge
                            label={run.reconciliation.is_clean ? 'CLEAN' : 'ISSUES'}
                            variant={run.reconciliation.is_clean ? 'green' : 'red'}
                          />
                        </td>
                        <td className="px-4 py-2.5">
                          <Badge
                            label={run.is_successful ? 'OK' : 'ERRORS'}
                            variant={run.is_successful ? 'green' : 'red'}
                          />
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr key={`${run.run_id}-exp`}>
                          <td
                            colSpan={9}
                            className="px-4 py-4"
                            style={{ background: 'rgba(255,255,255,0.02)', borderBottom: '1px solid rgba(255,255,255,0.06)' }}
                          >
                            <div className="grid grid-cols-3 gap-6 text-xs">
                              <div className="space-y-1.5">
                                <div className="text-white/30 uppercase tracking-wider font-semibold mb-2">Timing</div>
                                <div className="flex justify-between">
                                  <span className="text-white/40">Started</span>
                                  <span className="font-mono text-white/60">{formatDateTime(run.started_at)}</span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-white/40">Completed</span>
                                  <span className="font-mono text-white/60">{formatDateTime(run.completed_at)}</span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-white/40">Mode</span>
                                  <span className="font-mono text-white/60 uppercase">{run.mode}</span>
                                </div>
                              </div>
                              <div className="space-y-1.5">
                                <div className="text-white/30 uppercase tracking-wider font-semibold mb-2">Candidates</div>
                                <div className="flex justify-between">
                                  <span className="text-white/40">Swing Passing</span>
                                  <span className="font-mono text-profit">{run.swing_candidates_passing}</span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-white/40">Core Passing</span>
                                  <span className="font-mono text-info">{run.core_candidates_passing}</span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-white/40">Entries Rejected</span>
                                  <span className="font-mono text-white/50">{run.entries_rejected}</span>
                                </div>
                              </div>
                              <div className="space-y-1.5">
                                <div className="text-white/30 uppercase tracking-wider font-semibold mb-2">Risk</div>
                                <div className="flex justify-between">
                                  <span className="text-white/40">Open Risk</span>
                                  <span className="font-mono text-white/60">{formatPct(run.portfolio_risk.open_risk_pct)}</span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-white/40">Positions</span>
                                  <span className="font-mono text-white/60">{run.portfolio_risk.position_count}</span>
                                </div>
                                {run.errors.length > 0 && (
                                  <div className="mt-2">
                                    <div className="text-loss/60 font-semibold mb-1">Errors:</div>
                                    {run.errors.map((e, i) => (
                                      <div key={i} className="text-loss/50 text-xs">{e}</div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  );
                })}
              </tbody>
            </table>
          </div>
          <Pagination page={page} total={total} pageSize={20} onPage={setPage} />
        </>
      )}
    </PageWrapper>
  );
}

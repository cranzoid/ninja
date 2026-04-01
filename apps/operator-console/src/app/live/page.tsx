'use client';

import { useState } from 'react';
import { PageWrapper } from '@/components/layout/PageWrapper';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { SkeletonCard } from '@/components/ui/SkeletonLoader';
import { useApi } from '@/hooks/useApi';
import type { LiveRunReport, PaginatedResponse, APIResponse } from '@/lib/types';
import { formatDateTime } from '@/lib/utils';

function todayIST(): string {
  const now = new Date();
  const ist = new Date(now.getTime() + 5.5 * 60 * 60 * 1000);
  return ist.toISOString().split('T')[0];
}

export default function LivePage() {
  const [tradingDate, setTradingDate] = useState(todayIST());
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<LiveRunReport | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const [reviewDate, setReviewDate] = useState<string | null>(null);
  const [reviewNotes, setReviewNotes] = useState('');
  const [reviewing, setReviewing] = useState(false);

  const {
    data: runsData,
    loading: runsLoading,
    refetch: refetchRuns,
  } = useApi<PaginatedResponse<LiveRunReport>>('/api/live/runs', {
    refreshInterval: 60_000,
  });

  const handleRunConfirmed = async () => {
    setShowConfirm(false);
    setRunning(true);
    setRunError(null);
    setResult(null);
    try {
      const res = await fetch('/api/live/run-eod', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trading_date: tradingDate }),
      });
      const json: APIResponse<LiveRunReport> = await res.json();
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

  const handleReview = async () => {
    if (!reviewDate || !reviewNotes.trim()) return;
    setReviewing(true);
    try {
      const res = await fetch(`/api/live/runs/${reviewDate}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes: reviewNotes }),
      });
      const json: APIResponse<LiveRunReport> = await res.json();
      if (json.success) {
        refetchRuns();
        setReviewDate(null);
        setReviewNotes('');
      }
    } catch (e) {
      // silently fail
    } finally {
      setReviewing(false);
    }
  };

  const runs = runsData?.data ?? [];
  const hasUnresolvedAnomalies = runs.length > 0 && runs[0].anomalies.length > 0 && !runs[0].reviewed_by_operator;

  return (
    <PageWrapper title="Live Trading">
      {hasUnresolvedAnomalies && (
        <div
          className="p-3 rounded-sm text-sm mb-4"
          style={{
            background: 'rgba(245,158,11,0.08)',
            border: '1px solid rgba(245,158,11,0.2)',
            color: '#f59e0b',
          }}
        >
          Unresolved anomalies from last session — next session blocked until reviewed.
        </div>
      )}

      {/* Run form */}
      <Card title="Run Live EOD">
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
            variant="danger"
            size="sm"
            onClick={() => setShowConfirm(true)}
            disabled={running}
            style={{
              background: 'rgba(239,68,68,0.15)',
              border: '1px solid rgba(239,68,68,0.3)',
              color: '#ef4444',
            }}
          >
            {running ? 'Running...' : 'Run Live EOD'}
          </Button>
        </div>

        {runError && (
          <div
            className="mt-4 p-3 rounded-sm text-sm"
            style={{
              background: 'rgba(239,68,68,0.06)',
              border: '1px solid rgba(239,68,68,0.15)',
              color: '#ef4444',
            }}
          >
            {runError}
          </div>
        )}
      </Card>

      {/* Confirmation Modal */}
      <Modal
        open={showConfirm}
        title="Confirm Live EOD Run"
        onClose={() => setShowConfirm(false)}
      >
        <div className="text-sm text-white/70 mb-4">
          This will submit real orders to Zerodha. Capital at risk: &#8377;50,000. Confirm?
        </div>
        <div className="flex gap-3 justify-end">
          <Button variant="outline" size="sm" onClick={() => setShowConfirm(false)}>
            Cancel
          </Button>
          <Button
            variant="danger"
            size="sm"
            onClick={handleRunConfirmed}
            style={{
              background: '#ef4444',
              color: 'white',
            }}
          >
            Confirm &amp; Run
          </Button>
        </div>
      </Modal>

      {/* Latest result */}
      {result && (
        <Card title="Latest Run Result" className="mt-4">
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <div className="text-white/40 text-xs font-mono uppercase">Orders Submitted</div>
              <div className="text-white font-mono text-lg">{result.orders_submitted.length}</div>
            </div>
            <div>
              <div className="text-white/40 text-xs font-mono uppercase">Orders Filled</div>
              <div className="text-white font-mono text-lg">{result.orders_filled.length}</div>
            </div>
            <div>
              <div className="text-white/40 text-xs font-mono uppercase">Orders Cancelled</div>
              <div className="text-white font-mono text-lg">{result.orders_cancelled.length}</div>
            </div>
          </div>

          {result.anomalies.length > 0 && (
            <div className="mt-4">
              <div className="text-xs text-white/40 font-mono uppercase mb-2">Anomalies</div>
              <ul className="space-y-1">
                {result.anomalies.map((a, i) => (
                  <li key={i} className="text-sm text-amber-400 font-mono">
                    {a}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {!result.reviewed_by_operator && (
            <div className="mt-4 flex items-end gap-3">
              <div className="flex-1">
                <label className="block text-xs text-white/40 mb-1 font-mono uppercase">
                  Review Notes
                </label>
                <Input
                  value={reviewNotes}
                  onChange={(e) => setReviewNotes(e.target.value)}
                  placeholder="Required notes for review..."
                />
              </div>
              <Button
                variant="primary"
                size="sm"
                disabled={!reviewNotes.trim()}
                onClick={() => {
                  setReviewDate(result.trading_date);
                  handleReview();
                }}
              >
                Mark Reviewed
              </Button>
            </div>
          )}
        </Card>
      )}

      {/* Past runs table */}
      <Card title="Past Live Runs" className="mt-4">
        {runsLoading ? (
          <SkeletonCard lines={4} />
        ) : runs.length === 0 ? (
          <div className="text-sm text-white/40">No live runs yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-white/40 text-xs font-mono uppercase border-b border-white/5">
                  <th className="text-left py-2 px-3">Date</th>
                  <th className="text-right py-2 px-3">Submitted</th>
                  <th className="text-right py-2 px-3">Filled</th>
                  <th className="text-right py-2 px-3">Anomalies</th>
                  <th className="text-center py-2 px-3">Reviewed</th>
                  <th className="text-right py-2 px-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr
                    key={run.trading_date}
                    className="border-b border-white/5 hover:bg-white/[0.02]"
                  >
                    <td className="py-2 px-3 font-mono">{run.trading_date}</td>
                    <td className="py-2 px-3 text-right font-mono">
                      {run.orders_submitted.length}
                    </td>
                    <td className="py-2 px-3 text-right font-mono">
                      {run.orders_filled.length}
                    </td>
                    <td className="py-2 px-3 text-right font-mono">
                      <span
                        style={{
                          color: run.anomalies.length > 0 ? '#f59e0b' : '#22c55e',
                        }}
                      >
                        {run.anomalies.length}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-center">
                      <Badge
                        label={run.reviewed_by_operator ? 'Yes' : 'No'}
                        variant={run.reviewed_by_operator ? 'green' : 'amber'}
                      />
                    </td>
                    <td className="py-2 px-3 text-right">
                      {!run.reviewed_by_operator && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setReviewDate(run.trading_date);
                            setReviewNotes('');
                          }}
                        >
                          Review
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Review modal */}
      <Modal
        open={!!reviewDate && !reviewing}
        title={`Review Run: ${reviewDate ?? ''}`}
        onClose={() => setReviewDate(null)}
      >
        <div className="mb-4">
          <label className="block text-xs text-white/40 mb-1 font-mono uppercase">
            Review Notes (required)
          </label>
          <Input
            value={reviewNotes}
            onChange={(e) => setReviewNotes(e.target.value)}
            placeholder="Describe your review findings..."
          />
        </div>
        <div className="flex gap-3 justify-end">
          <Button variant="outline" size="sm" onClick={() => setReviewDate(null)}>
            Cancel
          </Button>
          <Button
            variant="primary"
            size="sm"
            disabled={!reviewNotes.trim()}
            onClick={handleReview}
          >
            Submit Review
          </Button>
        </div>
      </Modal>
    </PageWrapper>
  );
}

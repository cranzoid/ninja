'use client';

import { useState } from 'react';
import { PageWrapper } from '@/components/layout/PageWrapper';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Modal } from '@/components/ui/Modal';
import { useApi } from '@/hooks/useApi';
import { postApi, fetchApi } from '@/lib/api';
import type { CommandResult, OverrideAction, AuditEvent } from '@/lib/types';
import type { PaginatedResponse } from '@/lib/types';
import { formatDateTime, shortId } from '@/lib/utils';

const COMMAND_OPTIONS: { value: OverrideAction; label: string }[] = [
  { value: 'cancel_entry', label: 'Cancel Entry' },
  { value: 'reduce_size', label: 'Reduce Size' },
  { value: 'tighten_stop', label: 'Tighten Stop' },
  { value: 'close_position', label: 'Close Position' },
  { value: 'freeze_symbol', label: 'Freeze Symbol' },
];

function FrozenSymbols({ onRefetch }: { onRefetch: () => void }) {
  const { data, loading, refetch } = useApi<string[]>('/api/commands/frozen-symbols', {
    refreshInterval: 30_000,
  });
  const [unfreezeSymbol, setUnfreezeSymbol] = useState<string | null>(null);
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleUnfreeze = async () => {
    if (!unfreezeSymbol || !reason.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetchApi<string>(`/api/commands/unfreeze/${unfreezeSymbol}`, {
        method: 'POST',
        body: JSON.stringify({ reason }),
      });
      if (res.success) {
        setUnfreezeSymbol(null);
        setReason('');
        refetch();
        onRefetch();
      } else {
        setError(res.error ?? 'Failed');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error');
    } finally {
      setSubmitting(false);
    }
  };

  const frozen = data ?? [];

  return (
    <>
      <Card title="Frozen Symbols" subtitle="Blocked from new entries">
        {loading ? (
          <div className="text-sm text-white/30">Loading…</div>
        ) : frozen.length === 0 ? (
          <div className="text-sm text-white/25 py-2">No symbols are currently frozen.</div>
        ) : (
          <div className="space-y-2">
            {frozen.map((sym) => (
              <div
                key={sym}
                className="flex items-center justify-between py-2 px-3 rounded-sm"
                style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.12)' }}
              >
                <span className="font-mono text-sm text-loss/80">{sym}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setUnfreezeSymbol(sym)}
                >
                  Unfreeze
                </Button>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Modal
        open={!!unfreezeSymbol}
        onClose={() => { setUnfreezeSymbol(null); setReason(''); setError(null); }}
        title={`Unfreeze ${unfreezeSymbol}`}
        size="sm"
      >
        <div className="space-y-4">
          <p className="text-sm text-white/50">
            This will allow new entries for <span className="font-mono text-white/80">{unfreezeSymbol}</span>.
            Provide a reason for the audit trail.
          </p>
          <Input
            label="Reason"
            placeholder="Reason for unfreezing…"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          {error && <div className="text-xs text-loss">{error}</div>}
          <div className="flex gap-2 justify-end">
            <Button variant="ghost" size="sm" onClick={() => setUnfreezeSymbol(null)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              loading={submitting}
              disabled={!reason.trim()}
              onClick={handleUnfreeze}
            >
              Confirm Unfreeze
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}

export default function CommandsPage() {
  const [commandType, setCommandType] = useState<OverrideAction>('cancel_entry');
  const [symbol, setSymbol] = useState('');
  const [newQty, setNewQty] = useState('');
  const [newStop, setNewStop] = useState('');
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<CommandResult | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [historyKey, setHistoryKey] = useState(0);

  // Validation
  const errors: Record<string, string> = {};
  if (!symbol.trim()) errors.symbol = 'Symbol is required';
  if (!reason.trim()) errors.reason = 'Reason is required';
  if (commandType === 'reduce_size' && (!newQty || isNaN(parseInt(newQty, 10)))) {
    errors.newQty = 'Valid quantity required';
  }
  if (commandType === 'tighten_stop' && (!newStop || isNaN(parseFloat(newStop)))) {
    errors.newStop = 'Valid stop price required';
  }

  const handleSubmit = async () => {
    if (Object.keys(errors).length > 0) return;
    setSubmitting(true);
    setResult(null);
    setSubmitError(null);

    const params: Record<string, unknown> = {};
    if (commandType === 'reduce_size') params.new_quantity = parseInt(newQty, 10);
    if (commandType === 'tighten_stop') params.new_stop = parseFloat(newStop);

    try {
      const res = await postApi<CommandResult>('/api/commands/execute', {
        command_type: commandType,
        symbol: symbol.toUpperCase().trim(),
        parameters: params,
        reason: reason.trim(),
      });
      if (res.success && res.data) {
        setResult(res.data);
        setHistoryKey((k) => k + 1);
        // Reset form
        setSymbol('');
        setReason('');
        setNewQty('');
        setNewStop('');
      } else {
        setSubmitError(res.error ?? 'Command failed');
      }
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : 'Error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <PageWrapper title="Command Center">
      <div className="grid grid-cols-2 gap-4 mb-4">
        {/* Frozen Symbols */}
        <FrozenSymbols onRefetch={() => setHistoryKey((k) => k + 1)} />

        {/* Execute Command */}
        <Card
          title="Execute Command"
          subtitle="Risk-reducing overrides only (§11.4)"
        >
          <div className="space-y-4">
            <Select
              label="Command Type"
              options={COMMAND_OPTIONS}
              value={commandType}
              onChange={(e) => {
                setCommandType(e.target.value as OverrideAction);
                setNewQty('');
                setNewStop('');
              }}
            />
            <Input
              label="Symbol"
              placeholder="e.g. RELIANCE"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              error={errors.symbol}
            />
            {commandType === 'reduce_size' && (
              <Input
                label="New Quantity"
                type="number"
                placeholder="e.g. 5"
                value={newQty}
                onChange={(e) => setNewQty(e.target.value)}
                error={errors.newQty}
              />
            )}
            {commandType === 'tighten_stop' && (
              <Input
                label="New Stop Price (₹)"
                type="number"
                step="0.05"
                placeholder="e.g. 2450.00"
                value={newStop}
                onChange={(e) => setNewStop(e.target.value)}
                error={errors.newStop}
              />
            )}
            <div className="flex flex-col gap-1">
              <label className="text-xs font-semibold uppercase tracking-wider text-white/40">
                Reason (required)
              </label>
              <textarea
                rows={3}
                placeholder="Explain why this override is necessary…"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="w-full rounded-sm px-3 py-2 text-sm text-white/80 bg-white/[0.04] border border-white/10 focus:border-white/25 focus:outline-none transition-colors placeholder:text-white/25 resize-none"
              />
              {errors.reason && (
                <span className="text-xs text-loss">{errors.reason}</span>
              )}
            </div>

            <Button
              variant="danger"
              size="md"
              className="w-full justify-center"
              loading={submitting}
              disabled={Object.keys(errors).length > 0 || submitting}
              onClick={handleSubmit}
            >
              ⚡ Execute Command
            </Button>

            {submitError && (
              <div
                className="p-3 rounded-sm text-sm text-loss/80"
                style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)' }}
              >
                {submitError}
              </div>
            )}

            {result && (
              <div
                className="p-3 rounded-sm text-sm"
                style={{
                  background:
                    result.status === 'executed'
                      ? 'rgba(34,197,94,0.06)'
                      : 'rgba(239,68,68,0.06)',
                  border:
                    result.status === 'executed'
                      ? '1px solid rgba(34,197,94,0.2)'
                      : '1px solid rgba(239,68,68,0.2)',
                }}
              >
                <div className="flex items-center gap-2 mb-1">
                  <Badge
                    label={result.status.toUpperCase()}
                    variant={result.status === 'executed' ? 'green' : 'red'}
                  />
                  <span className="text-xs font-mono text-white/40">
                    {shortId(result.command_id)}
                  </span>
                </div>
                <div className="text-xs text-white/60">{result.message}</div>
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* Command History */}
      <CommandHistory key={historyKey} />
    </PageWrapper>
  );
}

function CommandHistory() {
  const { data, loading } = useApi<{ data: AuditEvent[]; total: number }>(
    '/api/commands/history?page=1&page_size=20',
  ) as { data: { data: AuditEvent[]; total: number } | null; loading: boolean };

  const events = (data as unknown as { data: AuditEvent[] } | null)?.data ?? [];

  return (
    <Card title="Command History" subtitle="Recent override events">
      {loading ? (
        <div className="text-sm text-white/30">Loading…</div>
      ) : events.length === 0 ? (
        <div className="text-sm text-white/25 py-2">No commands executed yet.</div>
      ) : (
        <table className="w-full" style={{ borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Time', 'Command', 'Symbol', 'Status', 'Reason'].map((h) => (
                <th
                  key={h}
                  className="pb-2 text-left text-2xs font-semibold uppercase tracking-widest text-white/25"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {events.map((e) => {
              const p = e.payload as {
                command_type?: string;
                status?: string;
                reason?: string;
              };
              return (
                <tr
                  key={e.event_id}
                  style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}
                >
                  <td className="py-2 text-xs font-mono text-white/30">
                    {formatDateTime(e.timestamp)}
                  </td>
                  <td className="py-2 text-xs font-mono text-info">
                    {p.command_type ?? e.event_type}
                  </td>
                  <td className="py-2 text-xs font-mono text-white/60">
                    {e.related_symbol ?? '—'}
                  </td>
                  <td className="py-2">
                    <Badge
                      label={(p.status ?? 'executed').toUpperCase()}
                      variant={p.status === 'rejected' ? 'red' : 'green'}
                    />
                  </td>
                  <td className="py-2 text-xs text-white/40 max-w-xs truncate">
                    {String(p.reason ?? '—')}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </Card>
  );
}

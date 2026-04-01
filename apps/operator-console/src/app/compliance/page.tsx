'use client';

import { PageWrapper } from '@/components/layout/PageWrapper';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { StatusDot } from '@/components/ui/StatusDot';
import { Button } from '@/components/ui/Button';
import { SkeletonCard } from '@/components/ui/SkeletonLoader';
import { useApi } from '@/hooks/useApi';
import type { ComplianceReport, ComplianceResult, ComplianceCheckStatus } from '@/lib/types';
import { formatDateTime, modeLabel } from '@/lib/utils';
import { useState } from 'react';

const STATUS_VARIANTS: Record<ComplianceCheckStatus, 'green' | 'red' | 'neutral' | 'amber'> = {
  pass: 'green',
  fail: 'red',
  skipped: 'neutral',
  warning: 'amber',
};

const STATUS_DOT: Record<ComplianceCheckStatus, 'healthy' | 'error' | 'inactive' | 'warning'> = {
  pass: 'healthy',
  fail: 'error',
  skipped: 'inactive',
  warning: 'warning',
};

function CheckRow({ check }: { check: ComplianceResult }) {
  return (
    <div
      className="flex items-start gap-4 py-3"
      style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}
    >
      <StatusDot status={STATUS_DOT[check.status]} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-sm font-mono text-white/70">{check.check_name}</span>
          <Badge label={check.status.toUpperCase()} variant={STATUS_VARIANTS[check.status]} />
        </div>
        <div
          className={`text-xs ${check.status === 'skipped' ? 'text-white/25 italic' : 'text-white/40'}`}
        >
          {check.message}
        </div>
      </div>
      <div className="text-2xs font-mono text-white/20 whitespace-nowrap">
        {formatDateTime(check.checked_at)}
      </div>
    </div>
  );
}

export default function CompliancePage() {
  const { data, loading, error, refetch } = useApi<ComplianceReport>(
    '/api/compliance/status',
    { refreshInterval: 60_000 },
  );
  const [running, setRunning] = useState(false);

  const handleRunCheck = async () => {
    setRunning(true);
    try {
      await fetch('/api/compliance/run', { method: 'POST' });
      refetch();
    } finally {
      setRunning(false);
    }
  };

  if (loading && !data) {
    return (
      <PageWrapper title="Compliance">
        <SkeletonCard lines={6} />
      </PageWrapper>
    );
  }

  const allBlockingPassed = data?.all_blocking_passed ?? false;

  return (
    <PageWrapper title="Compliance">
      {/* Big status indicator */}
      <div
        className="rounded-sm p-5 mb-4 flex items-center gap-4"
        style={{
          background: allBlockingPassed ? 'rgba(34,197,94,0.06)' : 'rgba(239,68,68,0.06)',
          border: allBlockingPassed
            ? '1px solid rgba(34,197,94,0.2)'
            : '1px solid rgba(239,68,68,0.2)',
        }}
      >
        <div
          className="text-3xl flex-shrink-0"
          style={{ color: allBlockingPassed ? '#22c55e' : '#ef4444' }}
        >
          {allBlockingPassed ? '✓' : '✗'}
        </div>
        <div className="flex-1">
          <div
            className="text-lg font-semibold font-mono"
            style={{ color: allBlockingPassed ? '#22c55e' : '#ef4444' }}
          >
            {allBlockingPassed ? 'ALL BLOCKING CHECKS PASSED — READY TO ARM' : 'BLOCKING CHECKS FAILED — LIVE ARMING PREVENTED'}
          </div>
          <div className="text-sm text-white/40 mt-0.5">
            Mode: <span className="font-mono text-white/60">{data ? modeLabel(data.mode) : '—'}</span>
          </div>
        </div>
        <Button variant="ghost" size="sm" onClick={handleRunCheck} disabled={running}>
          {running ? '...' : '↻ Run Compliance Check'}
        </Button>
      </div>

      {error && (
        <div
          className="mb-4 p-3 rounded-sm text-sm text-loss/70"
          style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)' }}
        >
          {error}
        </div>
      )}

      {/* Checks */}
      <Card title="Compliance Checks">
        {(data?.results ?? []).length === 0 ? (
          <div className="text-sm text-white/25 py-4 text-center">No checks available.</div>
        ) : (
          <div>
            {data?.results.map((check) => (
              <CheckRow key={check.check_name} check={check} />
            ))}
          </div>
        )}
      </Card>

      {/* Summary */}
      <div className="mt-4 grid grid-cols-4 gap-4 text-xs text-white/40">
        <div
          className="p-3 rounded-sm"
          style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}
        >
          <div className="font-semibold uppercase tracking-wider text-white/25 mb-1">Passed</div>
          <div className="font-mono text-profit text-xl">
            {data?.results.filter((c) => c.status === 'pass').length ?? 0}
          </div>
        </div>
        <div
          className="p-3 rounded-sm"
          style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}
        >
          <div className="font-semibold uppercase tracking-wider text-white/25 mb-1">Failed</div>
          <div className="font-mono text-loss text-xl">
            {data?.results.filter((c) => c.status === 'fail').length ?? 0}
          </div>
        </div>
        <div
          className="p-3 rounded-sm"
          style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}
        >
          <div className="font-semibold uppercase tracking-wider text-white/25 mb-1">Warning</div>
          <div className="font-mono text-xl" style={{ color: '#f59e0b' }}>
            {data?.results.filter((c) => c.status === 'warning').length ?? 0}
          </div>
        </div>
        <div
          className="p-3 rounded-sm"
          style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}
        >
          <div className="font-semibold uppercase tracking-wider text-white/25 mb-1">Skipped</div>
          <div className="font-mono text-white/40 text-xl">
            {data?.results.filter((c) => c.status === 'skipped').length ?? 0}
          </div>
        </div>
      </div>
    </PageWrapper>
  );
}

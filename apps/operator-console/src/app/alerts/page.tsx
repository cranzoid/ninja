'use client';

import { useState } from 'react';
import { PageWrapper } from '@/components/layout/PageWrapper';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { StatusDot } from '@/components/ui/StatusDot';
import { Pagination } from '@/components/ui/Table';
import { SkeletonTable } from '@/components/ui/SkeletonLoader';
import { usePaginatedApi } from '@/hooks/useApi';
import { fetchApi } from '@/lib/api';
import type { AuditEvent } from '@/lib/types';
import { formatDateTime } from '@/lib/utils';
import { POLL_INTERVAL_ALERTS } from '@/lib/constants';

export default function AlertsPage() {
  const [page, setPage] = useState(1);
  const [acknowledged, setAcknowledged] = useState<Set<string>>(new Set());
  const [ackLoading, setAckLoading] = useState<string | null>(null);

  const { data, loading, error, refetch } = usePaginatedApi<AuditEvent>(
    `/api/alerts?page=${page}&page_size=50`,
    { refreshInterval: POLL_INTERVAL_ALERTS },
  );

  const events = data?.data ?? [];
  const total = data?.total ?? 0;

  const handleAck = async (eventId: string) => {
    setAckLoading(eventId);
    try {
      const res = await fetchApi<string>(`/api/alerts/${eventId}/acknowledge`, {
        method: 'POST',
        body: JSON.stringify({}),
      });
      if (res.success) {
        setAcknowledged((prev) => new Set([...prev, eventId]));
      }
    } finally {
      setAckLoading(null);
    }
  };

  return (
    <PageWrapper title="Alerts">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <StatusDot
            status={events.some((e) => !acknowledged.has(e.event_id)) ? 'warning' : 'healthy'}
            pulse
          />
          <span className="text-sm text-white/50">
            {total} total alert{total !== 1 ? 's' : ''}
          </span>
        </div>
        <Button variant="ghost" size="sm" onClick={refetch}>
          ↻ Refresh
        </Button>
      </div>

      {loading && !data ? (
        <SkeletonTable rows={10} cols={5} />
      ) : error ? (
        <div
          className="p-4 rounded-sm text-sm text-loss/80"
          style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)' }}
        >
          {error}
        </div>
      ) : events.length === 0 ? (
        <div
          className="p-8 text-center rounded-sm text-sm text-white/25"
          style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}
        >
          No alerts. System is running cleanly.
        </div>
      ) : (
        <>
          <div className="rounded-sm overflow-hidden" style={{ border: '1px solid rgba(255,255,255,0.06)' }}>
            <table className="w-full console-table" style={{ borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.02)' }}>
                  {['', 'Timestamp', 'Event Type', 'Symbol', 'Source', 'Mode', ''].map((h, i) => (
                    <th
                      key={i}
                      className="px-4 py-2.5 text-left text-2xs font-semibold uppercase tracking-widest text-white/30"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {events.map((e, idx) => {
                  const isAcknowledged = acknowledged.has(e.event_id);
                  return (
                    <tr
                      key={e.event_id}
                      style={{
                        borderBottom: '1px solid rgba(255,255,255,0.04)',
                        background: isAcknowledged
                          ? 'transparent'
                          : idx % 2 === 1
                          ? 'rgba(245,158,11,0.03)'
                          : 'rgba(245,158,11,0.015)',
                        opacity: isAcknowledged ? 0.45 : 1,
                      }}
                    >
                      <td className="px-4 py-2.5 w-8">
                        {!isAcknowledged && (
                          <span
                            className="inline-block w-2 h-2 rounded-full pulse-dot"
                            style={{ background: '#f59e0b' }}
                          />
                        )}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-xs text-white/40">
                        {formatDateTime(e.timestamp)}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-xs text-info">
                        {e.event_type}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-xs text-white/60">
                        {e.related_symbol ?? '—'}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-xs text-white/30">
                        {e.source_service}
                      </td>
                      <td className="px-4 py-2.5">
                        <Badge label={e.mode.toUpperCase()} variant="neutral" />
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        {!isAcknowledged && (
                          <Button
                            variant="ghost"
                            size="sm"
                            loading={ackLoading === e.event_id}
                            onClick={() => handleAck(e.event_id)}
                          >
                            Ack
                          </Button>
                        )}
                        {isAcknowledged && (
                          <span className="text-2xs text-white/20 font-mono">ACK'd</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <Pagination page={page} total={total} pageSize={50} onPage={setPage} />
        </>
      )}
    </PageWrapper>
  );
}

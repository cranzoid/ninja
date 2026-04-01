'use client';

import { useState } from 'react';
import { PageWrapper } from '@/components/layout/PageWrapper';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Pagination } from '@/components/ui/Table';
import { SkeletonTable } from '@/components/ui/SkeletonLoader';
import { SymbolLink } from '@/components/shared/SymbolLink';
import { usePaginatedApi } from '@/hooks/useApi';
import type { OrderRecord, OrderStatus, AuditEvent } from '@/lib/types';
import type { PaginatedResponse } from '@/lib/types';
import { formatINR, formatDateTime, shortId, safeFloat } from '@/lib/utils';
import { ORDER_STATUS_COLORS } from '@/lib/constants';

const STATUS_OPTS = [
  { value: 'all', label: 'All Statuses' },
  { value: 'filled', label: 'Filled' },
  { value: 'cancelled', label: 'Cancelled' },
];

function OrderTransitionTimeline({ order }: { order: OrderRecord }) {
  return (
    <div className="flex items-center gap-2 flex-wrap text-xs">
      {order.transitions.map((t, i) => (
        <span key={i} className="flex items-center gap-2">
          {i > 0 && <span className="text-white/20">→</span>}
          <span className="font-mono" style={{ color: ORDER_STATUS_COLORS[t.to_status as OrderStatus] }}>
            {t.to_status.toUpperCase()}
          </span>
          <span className="text-white/25">{formatDateTime(t.timestamp)}</span>
          {t.fill_price && (
            <span className="text-profit">@ {formatINR(safeFloat(t.fill_price))}</span>
          )}
        </span>
      ))}
    </div>
  );
}

export default function TradesPage() {
  const [activeTab, setActiveTab] = useState<'orders' | 'audit'>('orders');
  const [statusFilter, setStatusFilter] = useState('all');
  const [symbolFilter, setSymbolFilter] = useState('');
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Audit tab
  const [auditPage, setAuditPage] = useState(1);

  const params = new URLSearchParams({
    page: String(page),
    page_size: '20',
  });
  if (statusFilter !== 'all') params.set('status', statusFilter);
  if (symbolFilter.trim()) params.set('symbol', symbolFilter.trim().toUpperCase());

  const { data, loading, error } = usePaginatedApi<OrderRecord>(
    `/api/trades?${params.toString()}`,
    { enabled: activeTab === 'orders' },
  );

  const { data: auditData, loading: auditLoading } = usePaginatedApi<AuditEvent>(
    `/api/audit?page=${auditPage}&page_size=20`,
    { enabled: activeTab === 'audit' },
  );

  const orders = data?.data ?? [];
  const total = data?.total ?? 0;
  const auditEvents = auditData?.data ?? [];
  const auditTotal = auditData?.total ?? 0;

  return (
    <PageWrapper title="Trades & Audit">
      {/* Tabs */}
      <div className="flex gap-1 mb-4" style={{ borderBottom: '1px solid rgba(255,255,255,0.06)', paddingBottom: '0' }}>
        {(['orders', 'audit'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={[
              'px-4 py-2.5 text-sm font-medium capitalize transition-colors',
              'border-b-2 -mb-px',
              activeTab === tab
                ? 'text-white border-info'
                : 'text-white/40 border-transparent hover:text-white/60',
            ].join(' ')}
          >
            {tab === 'orders' ? 'Orders' : 'Audit Log'}
          </button>
        ))}
      </div>

      {activeTab === 'orders' && (
        <>
          {/* Filter bar */}
          <div className="flex items-center gap-3 mb-4">
            <div className="w-40">
              <Select
                options={STATUS_OPTS}
                value={statusFilter}
                onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
              />
            </div>
            <div className="w-48">
              <Input
                placeholder="Symbol filter…"
                value={symbolFilter}
                onChange={(e) => { setSymbolFilter(e.target.value); setPage(1); }}
              />
            </div>
            <Button variant="ghost" size="sm" onClick={() => { setSymbolFilter(''); setStatusFilter('all'); setPage(1); }}>
              Clear
            </Button>
          </div>

          {loading ? (
            <SkeletonTable rows={8} cols={7} />
          ) : error ? (
            <div className="text-sm text-loss/70 p-4" style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)', borderRadius: '2px' }}>
              {error}
            </div>
          ) : (
            <>
              <div className="rounded-sm overflow-hidden" style={{ border: '1px solid rgba(255,255,255,0.06)' }}>
                <table className="w-full console-table" style={{ borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.02)' }}>
                      {['Order ID', 'Symbol', 'Side', 'Qty', 'Status', 'Fill Price', 'Created', 'Filled At'].map((h) => (
                        <th key={h} className="px-4 py-2.5 text-left text-2xs font-semibold uppercase tracking-widest text-white/30">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {orders.length === 0 ? (
                      <tr>
                        <td colSpan={8} className="px-4 py-8 text-center text-sm text-white/25">
                          No orders found.
                        </td>
                      </tr>
                    ) : (
                      orders.map((o, idx) => {
                        const isExpanded = expandedId === o.order_id;
                        return (
                          <>
                            <tr
                              key={o.order_id}
                              className="cursor-pointer transition-colors"
                              style={{
                                borderBottom: '1px solid rgba(255,255,255,0.04)',
                                background: idx % 2 === 1 ? 'rgba(255,255,255,0.015)' : undefined,
                              }}
                              onClick={() => setExpandedId(isExpanded ? null : o.order_id)}
                            >
                              <td className="px-4 py-2.5 font-mono text-xs text-white/30">{shortId(o.order_id)}</td>
                              <td className="px-4 py-2.5"><SymbolLink symbol={o.intent.symbol} layer={o.intent.layer} /></td>
                              <td className="px-4 py-2.5">
                                <Badge
                                  label={o.intent.side.toUpperCase()}
                                  variant={o.intent.side === 'buy' ? 'green' : 'red'}
                                />
                              </td>
                              <td className="px-4 py-2.5 font-mono text-sm text-white/60">{o.intent.quantity}</td>
                              <td className="px-4 py-2.5">
                                <span
                                  className="font-mono text-xs font-semibold uppercase"
                                  style={{ color: ORDER_STATUS_COLORS[o.current_status as OrderStatus] ?? '#ffffff' }}
                                >
                                  {o.current_status}
                                </span>
                              </td>
                              <td className="px-4 py-2.5 font-mono text-sm text-white/60">
                                {o.fill_price ? formatINR(safeFloat(o.fill_price)) : '—'}
                              </td>
                              <td className="px-4 py-2.5 font-mono text-xs text-white/30">{formatDateTime(o.created_at)}</td>
                              <td className="px-4 py-2.5 font-mono text-xs text-white/30">{o.filled_at ? formatDateTime(o.filled_at) : '—'}</td>
                            </tr>
                            {isExpanded && (
                              <tr key={`${o.order_id}-exp`}>
                                <td colSpan={8} className="px-4 py-3" style={{ background: 'rgba(255,255,255,0.02)', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                                  <div className="text-xs text-white/40 mb-2 uppercase tracking-widest font-semibold">
                                    State Transitions
                                  </div>
                                  <OrderTransitionTimeline order={o} />
                                  <div className="grid grid-cols-4 gap-4 mt-3 text-xs">
                                    <div>
                                      <span className="text-white/30">Stop Price: </span>
                                      <span className="font-mono text-loss">{formatINR(safeFloat(o.intent.stop_price))}</span>
                                    </div>
                                    <div>
                                      <span className="text-white/30">Layer: </span>
                                      <span className="font-mono text-white/60 uppercase">{o.intent.layer}</span>
                                    </div>
                                    <div>
                                      <span className="text-white/30">Filled Qty: </span>
                                      <span className="font-mono text-white/60">{o.filled_qty} / {o.intent.quantity}</span>
                                    </div>
                                    <div>
                                      <span className="text-white/30">Timing: </span>
                                      <span className="font-mono text-white/60 uppercase">{o.intent.execution_timing}</span>
                                    </div>
                                  </div>
                                </td>
                              </tr>
                            )}
                          </>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
              <Pagination page={page} total={total} pageSize={20} onPage={setPage} />
            </>
          )}
        </>
      )}

      {activeTab === 'audit' && (
        <>
          {auditLoading ? (
            <SkeletonTable rows={8} cols={5} />
          ) : (
            <>
              <div className="rounded-sm overflow-hidden" style={{ border: '1px solid rgba(255,255,255,0.06)' }}>
                <table className="w-full console-table" style={{ borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.02)' }}>
                      {['Time', 'Event Type', 'Symbol', 'Source', 'Operator Visible'].map((h) => (
                        <th key={h} className="px-4 py-2.5 text-left text-2xs font-semibold uppercase tracking-widest text-white/30">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {auditEvents.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="px-4 py-8 text-center text-sm text-white/25">No audit events.</td>
                      </tr>
                    ) : auditEvents.map((e, idx) => (
                      <tr
                        key={e.event_id}
                        style={{
                          borderBottom: '1px solid rgba(255,255,255,0.04)',
                          background: idx % 2 === 1 ? 'rgba(255,255,255,0.015)' : undefined,
                        }}
                      >
                        <td className="px-4 py-2.5 font-mono text-xs text-white/30">{formatDateTime(e.timestamp)}</td>
                        <td className="px-4 py-2.5 font-mono text-xs text-info">{e.event_type}</td>
                        <td className="px-4 py-2.5 font-mono text-xs text-white/60">{e.related_symbol ?? '—'}</td>
                        <td className="px-4 py-2.5 font-mono text-xs text-white/30">{e.source_service}</td>
                        <td className="px-4 py-2.5">
                          <Badge label={e.operator_visible ? 'YES' : 'NO'} variant={e.operator_visible ? 'green' : 'neutral'} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination page={auditPage} total={auditTotal} pageSize={20} onPage={setAuditPage} />
            </>
          )}
        </>
      )}
    </PageWrapper>
  );
}

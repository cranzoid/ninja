'use client';

import { useState } from 'react';
import { PageWrapper } from '@/components/layout/PageWrapper';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { SkeletonTable } from '@/components/ui/SkeletonLoader';
import { Pagination } from '@/components/ui/Table';
import { SymbolLink } from '@/components/shared/SymbolLink';
import { PnlDisplay } from '@/components/shared/PnlDisplay';
import { usePositions } from '@/hooks/usePositions';
import type { PositionDetail } from '@/lib/types';
import {
  formatINR,
  formatPct,
  formatDate,
  distanceToStopColor,
  utilizationColor,
  safeFloat,
} from '@/lib/utils';

function PositionExpandedRow({ pos }: { pos: PositionDetail }) {
  return (
    <div className="grid grid-cols-3 gap-6 text-xs">
      <div className="space-y-1.5">
        <div className="text-white/30 uppercase tracking-wider text-2xs font-semibold mb-2">Entry</div>
        <div className="flex justify-between">
          <span className="text-white/40">Date</span>
          <span className="font-mono text-white/60">{formatDate(pos.entry_date)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-white/40">Price</span>
          <span className="font-mono text-white/60">{formatINR(safeFloat(pos.entry_price))}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-white/40">Quantity</span>
          <span className="font-mono text-white/60">{pos.quantity}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-white/40">Sector</span>
          <span className="font-mono text-white/60">{pos.sector}</span>
        </div>
      </div>
      <div className="space-y-1.5">
        <div className="text-white/30 uppercase tracking-wider text-2xs font-semibold mb-2">Current</div>
        <div className="flex justify-between">
          <span className="text-white/40">Price</span>
          <span className="font-mono text-white/60">{formatINR(safeFloat(pos.current_price))}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-white/40">Stop Price</span>
          <span className="font-mono text-white/60">{formatINR(safeFloat(pos.stop_price))}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-white/40">Risk Amount</span>
          <span className="font-mono text-loss">{formatINR(safeFloat(pos.risk_amount))}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-white/40">Days Held</span>
          <span className="font-mono text-white/60">{pos.days_held}d</span>
        </div>
      </div>
      <div className="space-y-1.5">
        <div className="text-white/30 uppercase tracking-wider text-2xs font-semibold mb-2">Distances</div>
        <div className="flex justify-between">
          <span className="text-white/40">To Stop</span>
          <span className={`font-mono ${distanceToStopColor(pos.distance_to_stop_pct)}`}>
            {formatPct(pos.distance_to_stop_pct)}
          </span>
        </div>
        {pos.distance_to_2r_pct !== null && (
          <div className="flex justify-between">
            <span className="text-white/40">To 2R Target</span>
            <span className="font-mono text-info">{formatPct(pos.distance_to_2r_pct ?? 0)}</span>
          </div>
        )}
      </div>
    </div>
  );
}

export default function PositionsPage() {
  const {
    data,
    loading,
    error,
    refetch,
    layer,
    setLayer,
    sortBy,
    sortOrder,
    toggleSort,
    page,
    setPage,
  } = usePositions();

  const [expandedSymbol, setExpandedSymbol] = useState<string | null>(null);

  const positions = data?.data ?? [];
  const total = data?.total ?? 0;

  const SortBtn = ({
    col,
    label,
  }: {
    col: 'symbol' | 'pnl' | 'risk' | 'days';
    label: string;
  }) => (
    <button
      onClick={() => toggleSort(col)}
      className="text-2xs font-semibold uppercase tracking-widest text-white/30 hover:text-white/60 transition-colors flex items-center gap-1"
    >
      {label}
      {sortBy === col && (
        <span>{sortOrder === 'asc' ? '▲' : '▼'}</span>
      )}
    </button>
  );

  return (
    <PageWrapper title="Positions">
      {/* Filter bar */}
      <div className="flex items-center gap-3 mb-4">
        <span className="text-xs text-white/30">Layer:</span>
        {(['all', 'core', 'swing'] as const).map((l) => (
          <button
            key={l}
            onClick={() => setLayer(l === 'all' ? 'all' : l)}
            className={[
              'px-3 py-1 text-xs rounded-sm font-mono uppercase tracking-wider transition-colors',
              layer === l
                ? 'bg-info/20 text-info border border-info/30'
                : 'text-white/40 hover:text-white/70 border border-white/08',
            ].join(' ')}
            style={{ border: layer === l ? undefined : '1px solid rgba(255,255,255,0.08)' }}
          >
            {l}
          </button>
        ))}
        <Button variant="ghost" size="sm" onClick={refetch} className="ml-auto">
          ↻ Refresh
        </Button>
      </div>

      {loading && !data ? (
        <SkeletonTable rows={8} cols={10} />
      ) : error ? (
        <div
          className="p-4 rounded-sm text-sm text-loss/80"
          style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)' }}
        >
          {error}
        </div>
      ) : (
        <>
          <div
            className="rounded-sm overflow-hidden"
            style={{ border: '1px solid rgba(255,255,255,0.06)' }}
          >
            <table className="w-full console-table" style={{ borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.02)' }}>
                  <th className="px-4 py-2.5 text-left"><SortBtn col="symbol" label="Symbol" /></th>
                  <th className="px-4 py-2.5 text-left text-2xs font-semibold uppercase tracking-widest text-white/30">Layer</th>
                  <th className="px-4 py-2.5 text-right text-2xs font-semibold uppercase tracking-widest text-white/30">Qty</th>
                  <th className="px-4 py-2.5 text-right text-2xs font-semibold uppercase tracking-widest text-white/30">Entry</th>
                  <th className="px-4 py-2.5 text-right text-2xs font-semibold uppercase tracking-widest text-white/30">Current</th>
                  <th className="px-4 py-2.5 text-right"><SortBtn col="pnl" label="P&L" /></th>
                  <th className="px-4 py-2.5 text-right text-2xs font-semibold uppercase tracking-widest text-white/30">P&L %</th>
                  <th className="px-4 py-2.5 text-right"><SortBtn col="risk" label="Risk %" /></th>
                  <th className="px-4 py-2.5 text-right text-2xs font-semibold uppercase tracking-widest text-white/30">Stop</th>
                  <th className="px-4 py-2.5 text-right text-2xs font-semibold uppercase tracking-widest text-white/30">Dist Stop</th>
                  <th className="px-4 py-2.5 text-right"><SortBtn col="days" label="Days" /></th>
                </tr>
              </thead>
              <tbody>
                {positions.length === 0 ? (
                  <tr>
                    <td colSpan={11} className="px-4 py-8 text-center text-sm text-white/25">
                      No positions open. Run a simulation to generate data.
                    </td>
                  </tr>
                ) : (
                  positions.map((pos, idx) => {
                    const isExpanded = expandedSymbol === pos.symbol;
                    const distStop = safeFloat(pos.distance_to_stop_pct);
                    return (
                      <>
                        <tr
                          key={pos.symbol}
                          className="cursor-pointer transition-colors"
                          style={{
                            borderBottom: '1px solid rgba(255,255,255,0.04)',
                            background: idx % 2 === 1 ? 'rgba(255,255,255,0.015)' : undefined,
                          }}
                          onClick={() =>
                            setExpandedSymbol(isExpanded ? null : pos.symbol)
                          }
                        >
                          <td className="px-4 py-2.5">
                            <SymbolLink symbol={pos.symbol} />
                          </td>
                          <td className="px-4 py-2.5">
                            <Badge
                              label={pos.layer.toUpperCase()}
                              variant={pos.layer === 'core' ? 'blue' : 'amber'}
                            />
                          </td>
                          <td className="px-4 py-2.5 text-right font-mono text-sm text-white/60">
                            {pos.quantity}
                          </td>
                          <td className="px-4 py-2.5 text-right font-mono text-sm text-white/60">
                            {formatINR(safeFloat(pos.entry_price))}
                          </td>
                          <td className="px-4 py-2.5 text-right font-mono text-sm text-white/80">
                            {formatINR(safeFloat(pos.current_price))}
                          </td>
                          <td className="px-4 py-2.5 text-right">
                            <PnlDisplay value={pos.unrealized_pnl} size="sm" />
                          </td>
                          <td className="px-4 py-2.5 text-right">
                            <span
                              className={`font-mono text-sm ${safeFloat(pos.unrealized_pnl_pct) >= 0 ? 'text-profit' : 'text-loss'}`}
                            >
                              {safeFloat(pos.unrealized_pnl_pct) >= 0 ? '+' : ''}
                              {formatPct(pos.unrealized_pnl_pct)}
                            </span>
                          </td>
                          <td className="px-4 py-2.5 text-right">
                            <span
                              className={`font-mono text-sm ${utilizationColor(safeFloat(pos.risk_pct_of_equity) * 25)}`}
                            >
                              {formatPct(pos.risk_pct_of_equity)}
                            </span>
                          </td>
                          <td className="px-4 py-2.5 text-right font-mono text-sm text-white/50">
                            {formatINR(safeFloat(pos.stop_price))}
                          </td>
                          <td className="px-4 py-2.5 text-right">
                            <span className={`font-mono text-sm ${distanceToStopColor(distStop)}`}>
                              {formatPct(distStop)}
                            </span>
                          </td>
                          <td className="px-4 py-2.5 text-right font-mono text-sm text-white/40">
                            {pos.days_held}d
                          </td>
                        </tr>
                        {isExpanded && (
                          <tr key={`${pos.symbol}-expanded`}>
                            <td
                              colSpan={11}
                              className="px-4 py-3"
                              style={{
                                background: 'rgba(255,255,255,0.02)',
                                borderBottom: '1px solid rgba(255,255,255,0.06)',
                              }}
                            >
                              <PositionExpandedRow pos={pos} />
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
          <Pagination
            page={page}
            total={total}
            pageSize={20}
            onPage={setPage}
          />
        </>
      )}
    </PageWrapper>
  );
}

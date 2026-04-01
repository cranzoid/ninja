'use client';

import { useState } from 'react';
import { PageWrapper } from '@/components/layout/PageWrapper';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Pagination } from '@/components/ui/Table';
import { SkeletonCard } from '@/components/ui/SkeletonLoader';
import { useApi } from '@/hooks/useApi';
import { usePaginatedApi } from '@/hooks/useApi';
import type { ConfigSnapshot } from '@/lib/types';
import { formatDateTime, modeLabel, shortId } from '@/lib/utils';

function ConfigKV({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between py-2" style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
      <span className="text-xs text-white/40">{label}</span>
      <span className="text-xs font-mono text-white/70">{value}</span>
    </div>
  );
}

export default function ConfigPage() {
  const [activeTab, setActiveTab] = useState<'current' | 'history'>('current');
  const [histPage, setHistPage] = useState(1);

  const { data: current, loading } = useApi<ConfigSnapshot>('/api/config/current');
  const { data: histData, loading: histLoading } = usePaginatedApi<ConfigSnapshot>(
    `/api/config/history?page=${histPage}&page_size=20`,
    { enabled: activeTab === 'history' },
  );

  if (loading && !current) {
    return (
      <PageWrapper title="Configuration">
        <SkeletonCard lines={8} />
      </PageWrapper>
    );
  }

  const snapshots = histData?.data ?? [];
  const histTotal = histData?.total ?? 0;

  return (
    <PageWrapper title="Configuration">
      {/* Tabs */}
      <div className="flex gap-1 mb-4" style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        {(['current', 'history'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={[
              'px-4 py-2.5 text-sm font-medium capitalize transition-colors border-b-2 -mb-px',
              activeTab === tab
                ? 'text-white border-info'
                : 'text-white/40 border-transparent hover:text-white/60',
            ].join(' ')}
          >
            {tab === 'current' ? 'Current Config' : 'Snapshot History'}
          </button>
        ))}
      </div>

      {activeTab === 'current' && current && (
        <div className="grid grid-cols-2 gap-4">
          {/* Mode & Status */}
          <Card title="Runtime Status">
            <ConfigKV label="Snapshot ID" value={shortId(current.snapshot_id)} />
            <ConfigKV label="Captured At" value={formatDateTime(current.captured_at)} />
            <ConfigKV label="Mode" value={modeLabel(current.mode)} />
            <ConfigKV label="Armed Live" value={current.armed_live ? 'YES' : 'NO'} />
            <ConfigKV label="Regime State" value={current.regime_state.toUpperCase()} />
            <ConfigKV label="Universe Size" value={String(current.universe_size)} />
            <ConfigKV label="Active Blockers" value={String(current.active_blockers_count)} />
            <div className="pt-2">
              <div className="text-2xs font-mono text-white/20 break-all">
                checksum: {current.config_checksum}
              </div>
            </div>
          </Card>

          {/* Risk Limits */}
          <Card title="Risk Limits" subtitle="Charter §6.3">
            <ConfigKV
              label="Swing Risk / Trade"
              value={`${current.risk_limits.swing_risk_per_trade_pct}% of equity`}
            />
            <ConfigKV
              label="Core Add Risk"
              value={`${current.risk_limits.core_add_risk_pct}% of equity`}
            />
            <ConfigKV
              label="Core Position Cap"
              value={`${current.risk_limits.core_position_cap_pct}% of equity`}
            />
            <ConfigKV
              label="Swing Position Cap"
              value={`${current.risk_limits.swing_position_cap_pct}% of equity`}
            />
            <ConfigKV
              label="Sector Cap"
              value={`${current.risk_limits.sector_cap_pct}%`}
            />
            <ConfigKV
              label="Aggregate Open Risk Cap"
              value={`${current.risk_limits.aggregate_open_risk_pct}%`}
            />
            <ConfigKV
              label="Max New Swing Entries/Day"
              value={String(current.risk_limits.max_new_swing_entries_per_day)}
            />
          </Card>
        </div>
      )}

      {activeTab === 'history' && (
        <>
          {histLoading ? (
            <SkeletonCard lines={5} />
          ) : snapshots.length === 0 ? (
            <div
              className="p-8 text-center rounded-sm text-sm text-white/25"
              style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}
            >
              No config snapshots yet. Run EOD to capture a snapshot.
            </div>
          ) : (
            <>
              <div className="rounded-sm overflow-hidden" style={{ border: '1px solid rgba(255,255,255,0.06)' }}>
                <table className="w-full console-table" style={{ borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.02)' }}>
                      {['Captured At', 'Mode', 'Regime', 'Universe', 'Blockers', 'Agg Risk Cap', 'Checksum'].map((h) => (
                        <th key={h} className="px-4 py-2.5 text-left text-2xs font-semibold uppercase tracking-widest text-white/30">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {snapshots.map((s, idx) => (
                      <tr
                        key={s.snapshot_id}
                        style={{
                          borderBottom: '1px solid rgba(255,255,255,0.04)',
                          background: idx % 2 === 1 ? 'rgba(255,255,255,0.015)' : undefined,
                        }}
                      >
                        <td className="px-4 py-2.5 font-mono text-xs text-white/50">{formatDateTime(s.captured_at)}</td>
                        <td className="px-4 py-2.5">
                          <Badge label={modeLabel(s.mode)} variant={modeVariant(s.mode)} />
                        </td>
                        <td className="px-4 py-2.5 font-mono text-xs text-white/60 uppercase">{s.regime_state}</td>
                        <td className="px-4 py-2.5 font-mono text-sm text-white/60">{s.universe_size}</td>
                        <td className="px-4 py-2.5 font-mono text-sm text-white/60">{s.active_blockers_count}</td>
                        <td className="px-4 py-2.5 font-mono text-sm text-white/60">{s.risk_limits.aggregate_open_risk_pct}%</td>
                        <td className="px-4 py-2.5 font-mono text-2xs text-white/20">{s.config_checksum.slice(0, 8)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination page={histPage} total={histTotal} pageSize={20} onPage={setHistPage} />
            </>
          )}
        </>
      )}
    </PageWrapper>
  );
}

function modeVariant(mode: string): 'blue' | 'amber' | 'red' {
  if (mode === 'paper') return 'blue';
  if (mode === 'shadow-live') return 'amber';
  return 'red';
}

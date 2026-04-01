'use client';

import { useState } from 'react';

export interface TableColumn<T> {
  key: keyof T | string;
  label: string;
  render?: (value: unknown, row: T) => React.ReactNode;
  sortable?: boolean;
  align?: 'left' | 'right' | 'center';
  width?: string;
}

interface TableProps<T> {
  data: T[];
  columns: TableColumn<T>[];
  onSort?: (key: string, direction: 'asc' | 'desc') => void;
  emptyMessage?: string;
  rowKey?: (row: T, index: number) => string;
  onRowClick?: (row: T) => void;
  expandedRow?: (row: T) => React.ReactNode;
  expandedKey?: string | null;
}

export function Table<T extends object>({
  data,
  columns,
  onSort,
  emptyMessage = 'No data.',
  rowKey,
  onRowClick,
  expandedRow,
  expandedKey,
}: TableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');

  const handleSort = (key: string) => {
    const newDir = sortKey === key && sortDir === 'asc' ? 'desc' : 'asc';
    setSortKey(key);
    setSortDir(newDir);
    onSort?.(key, newDir);
  };

  return (
    <div
      className="w-full overflow-x-auto rounded-sm"
      style={{ border: '1px solid rgba(255,255,255,0.06)' }}
    >
      <table className="w-full console-table" style={{ borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
            {columns.map((col) => (
              <th
                key={String(col.key)}
                className={[
                  'px-4 py-2.5 text-2xs font-semibold uppercase tracking-widest text-white/30',
                  col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left',
                  col.sortable ? 'cursor-pointer select-none hover:text-white/50 transition-colors' : '',
                ].join(' ')}
                style={{ width: col.width, background: 'rgba(255,255,255,0.02)' }}
                onClick={() => col.sortable && handleSort(String(col.key))}
              >
                {col.label}
                {col.sortable && sortKey === String(col.key) && (
                  <span className="ml-1">{sortDir === 'asc' ? '▲' : '▼'}</span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="px-4 py-8 text-center text-sm text-white/25"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((row, idx) => {
              const key = rowKey ? rowKey(row, idx) : idx;
              const isExpanded = expandedKey === String(key);
              return (
                <>
                  <tr
                    key={key}
                    className={[
                      'transition-colors',
                      onRowClick ? 'cursor-pointer' : '',
                      idx % 2 === 1 ? 'bg-white/[0.015]' : '',
                    ].join(' ')}
                    style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}
                    onClick={() => onRowClick?.(row)}
                  >
                    {columns.map((col) => {
                      const val = (row as Record<string, unknown>)[String(col.key)];
                      return (
                        <td
                          key={String(col.key)}
                          className={[
                            'px-4 py-2.5 text-sm text-white/70',
                            col.align === 'right' ? 'text-right font-mono' : col.align === 'center' ? 'text-center' : '',
                          ].join(' ')}
                        >
                          {col.render ? col.render(val, row) : String(val ?? '—')}
                        </td>
                      );
                    })}
                  </tr>
                  {expandedRow && isExpanded && (
                    <tr key={`${key}-expanded`}>
                      <td
                        colSpan={columns.length}
                        className="px-4 py-3"
                        style={{ background: 'rgba(255,255,255,0.02)', borderBottom: '1px solid rgba(255,255,255,0.06)' }}
                      >
                        {expandedRow(row)}
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
  );
}

interface PaginationProps {
  page: number;
  total: number;
  pageSize: number;
  onPage: (p: number) => void;
}

export function Pagination({ page, total, pageSize, onPage }: PaginationProps) {
  const totalPages = Math.ceil(total / pageSize);
  if (totalPages <= 1) return null;

  return (
    <div className="flex items-center justify-between mt-3">
      <span className="text-xs text-white/30 font-mono">
        {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total}
      </span>
      <div className="flex gap-1">
        <button
          onClick={() => onPage(Math.max(1, page - 1))}
          disabled={page === 1}
          className="px-2.5 py-1 text-xs text-white/40 hover:text-white/70 disabled:opacity-30 rounded-sm border border-white/08 transition-colors"
          style={{ border: '1px solid rgba(255,255,255,0.08)' }}
        >
          ←
        </button>
        <button
          onClick={() => onPage(Math.min(totalPages, page + 1))}
          disabled={page === totalPages}
          className="px-2.5 py-1 text-xs text-white/40 hover:text-white/70 disabled:opacity-30 rounded-sm transition-colors"
          style={{ border: '1px solid rgba(255,255,255,0.08)' }}
        >
          →
        </button>
      </div>
    </div>
  );
}

'use client';

import { useState, useCallback } from 'react';
import { usePaginatedApi } from './useApi';
import type { PortfolioLayer, PositionDetail } from '@/lib/types';
import { POLL_INTERVAL_POSITIONS } from '@/lib/constants';

export type PositionSortBy = 'symbol' | 'pnl' | 'risk' | 'days';

export function usePositions() {
  const [layer, setLayer] = useState<PortfolioLayer | 'all'>('all');
  const [sortBy, setSortBy] = useState<PositionSortBy>('symbol');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [page, setPage] = useState(1);

  const layerParam = layer !== 'all' ? `&layer=${layer}` : '';
  const endpoint = `/api/positions?sort_by=${sortBy === 'days' ? 'symbol' : sortBy}&sort_order=${sortOrder}${layerParam}&page=${page}&page_size=20`;

  const { data, loading, error, refetch } = usePaginatedApi<PositionDetail>(
    endpoint,
    { refreshInterval: POLL_INTERVAL_POSITIONS },
  );

  const toggleSort = useCallback(
    (key: PositionSortBy) => {
      if (sortBy === key) {
        setSortOrder((o) => (o === 'asc' ? 'desc' : 'asc'));
      } else {
        setSortBy(key);
        setSortOrder('asc');
      }
      setPage(1);
    },
    [sortBy],
  );

  return {
    data,
    loading,
    error,
    refetch,
    layer,
    setLayer: (l: PortfolioLayer | 'all') => {
      setLayer(l);
      setPage(1);
    },
    sortBy,
    sortOrder,
    toggleSort,
    page,
    setPage,
  };
}

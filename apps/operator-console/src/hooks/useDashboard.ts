'use client';

import { useApi } from './useApi';
import type { DashboardData } from '@/lib/types';
import { POLL_INTERVAL_DASHBOARD } from '@/lib/constants';

export function useDashboard() {
  return useApi<DashboardData>('/api/dashboard', {
    refreshInterval: POLL_INTERVAL_DASHBOARD,
  });
}

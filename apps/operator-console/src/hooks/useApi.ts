'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { fetchApi, fetchPaginated } from '@/lib/api';
import type { APIResponse, PaginatedResponse } from '@/lib/types';

interface UseApiOptions {
  refreshInterval?: number;
  enabled?: boolean;
}

interface UseApiResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useApi<T>(
  endpoint: string,
  options: UseApiOptions = {},
): UseApiResult<T> {
  const { refreshInterval, enabled = true } = options;
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const fetch = useCallback(async () => {
    if (!enabled) return;
    try {
      const res: APIResponse<T> = await fetchApi<T>(endpoint);
      if (!mountedRef.current) return;
      if (res.success && res.data !== null) {
        setData(res.data);
        setError(null);
      } else {
        setError(res.error ?? 'Unknown error');
      }
    } catch (err) {
      if (!mountedRef.current) return;
      setError(err instanceof Error ? err.message : 'Request failed');
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, [endpoint, enabled]);

  useEffect(() => {
    mountedRef.current = true;
    setLoading(true);
    fetch();

    if (refreshInterval && refreshInterval > 0) {
      const id = setInterval(fetch, refreshInterval);
      return () => {
        mountedRef.current = false;
        clearInterval(id);
      };
    }
    return () => {
      mountedRef.current = false;
    };
  }, [fetch, refreshInterval]);

  return { data, loading, error, refetch: fetch };
}

export function usePaginatedApi<T>(
  endpoint: string,
  options: UseApiOptions = {},
): UseApiResult<PaginatedResponse<T>> {
  const { refreshInterval, enabled = true } = options;
  const [data, setData] = useState<PaginatedResponse<T> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const fetch = useCallback(async () => {
    if (!enabled) return;
    try {
      const res = await fetchPaginated<T>(endpoint);
      if (!mountedRef.current) return;
      if (res.success) {
        setData(res);
        setError(null);
      } else {
        setError('Paginated response error');
      }
    } catch (err) {
      if (!mountedRef.current) return;
      setError(err instanceof Error ? err.message : 'Request failed');
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, [endpoint, enabled]);

  useEffect(() => {
    mountedRef.current = true;
    setLoading(true);
    fetch();

    if (refreshInterval && refreshInterval > 0) {
      const id = setInterval(fetch, refreshInterval);
      return () => {
        mountedRef.current = false;
        clearInterval(id);
      };
    }
    return () => {
      mountedRef.current = false;
    };
  }, [fetch, refreshInterval]);

  return { data, loading, error, refetch: fetch };
}

import type { APIResponse, PaginatedResponse } from './types';

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit,
): Promise<APIResponse<T>> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`API error ${res.status}: ${text || res.statusText}`);
  }
  return res.json() as Promise<APIResponse<T>>;
}

export async function fetchPaginated<T>(
  endpoint: string,
  options?: RequestInit,
): Promise<PaginatedResponse<T>> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`API error ${res.status}: ${text || res.statusText}`);
  }
  return res.json() as Promise<PaginatedResponse<T>>;
}

export async function postApi<T>(
  endpoint: string,
  body: unknown,
): Promise<APIResponse<T>> {
  return fetchApi<T>(endpoint, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function postPaginated<T>(
  endpoint: string,
  body: unknown,
): Promise<PaginatedResponse<T>> {
  return fetchPaginated<T>(endpoint, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

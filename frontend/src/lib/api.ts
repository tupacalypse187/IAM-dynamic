import type {
  AccessRequest,
  AuditEvent,
  Credentials,
  PolicyResponse,
  ProvidersResponse,
  RequestStatus,
  ReviewDecision,
} from '@/types/api'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''
const TOKEN_KEY = 'iam_token'

function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token)
  } else {
    localStorage.removeItem(TOKEN_KEY)
  }
}

import { describeUnreachable, formatErrorDetail } from './net-error'

/**
 * The raw `fetch` TypeError ("Failed to fetch") tells users nothing.
 * Map it to where the request was going and what to check first.
 */
function unreachableError(): Error {
  return new Error(describeUnreachable(BASE_URL || undefined))
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }

  const token = getToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  let response: Response
  try {
    response = await fetch(`${BASE_URL}${url}`, {
      headers,
      ...options,
    })
  } catch (err) {
    // Network failure, DNS, refused connection, or file:// in the
    // packaged app when no API base URL was baked in at build time.
    if (err instanceof TypeError) throw unreachableError()
    throw err
  }

  if (response.status === 401 && !url.endsWith('/api/auth/login')) {
    setToken(null)
    window.dispatchEvent(new CustomEvent('auth:logout'))
    throw new Error('Session expired. Please log in again.')
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(formatErrorDetail(error.detail, `Request failed: ${response.status}`))
  }

  return response.json()
}

export interface AuthStatus {
  authenticated: boolean
  username: string | null
  auth_required: boolean
  is_admin: boolean
}

export interface LoginResponse {
  token: string
  expires_at: string
  username: string
}

export const api = {
  // Auth
  verifySession: () => request<AuthStatus>('/api/auth/verify'),

  login: (data: { username: string; password: string; turnstile_token?: string }) =>
    request<LoginResponse>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  register: (data: { username: string; password: string; turnstile_token?: string }) =>
    request<LoginResponse>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Providers
  getProviders: () => request<ProvidersResponse>('/config/providers'),

  generatePolicy: (data: { request_text: string; provider: string; model?: string; duration: number }) =>
    request<PolicyResponse>('/api/generate-policy', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  issueCredentials: (data: { policy: Record<string, unknown>; duration: number; approved: boolean; change_case?: string; risk?: string; auto_approved?: boolean }) =>
    request<Credentials>('/api/issue-credentials', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  generateRejectionGuidance: (data: { original_request: string; policy: Record<string, unknown>; risk: string; provider: string; model?: string }) =>
    request<{ guidance: string }>('/api/generate-rejection-guidance', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Access requests + review workflow
  submitRequest: (data: { request_text: string; provider: string; model?: string; duration: number }) =>
    request<AccessRequest>('/api/requests', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  recordRequest: (data: {
    request_text: string
    provider: string
    model?: string
    duration: number
    policy: Record<string, unknown>
    risk: string
    explanation: string
    approver_note: string
  }) =>
    request<AccessRequest>('/api/requests/record', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  listRequests: (params?: { status?: RequestStatus | 'all'; mine?: boolean }) => {
    const search = new URLSearchParams()
    if (params?.status && params.status !== 'all') search.set('status', params.status)
    if (params?.mine) search.set('mine', 'true')
    const query = search.toString()
    return request<AccessRequest[]>(`/api/requests${query ? `?${query}` : ''}`)
  },

  getRequest: (id: number) => request<AccessRequest>(`/api/requests/${id}`),

  reviewRequest: (id: number, data: { decision: ReviewDecision; feedback?: string }) =>
    request<AccessRequest>(`/api/requests/${id}/review`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  resubmitRequest: (id: number, data: { request_text?: string; provider?: string; model?: string; duration?: number }) =>
    request<AccessRequest>(`/api/requests/${id}/resubmit`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  discardRequest: (id: number) =>
    request<AccessRequest>(`/api/requests/${id}/discard`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),

  activateRequest: (id: number) =>
    request<Credentials>(`/api/requests/${id}/activate`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),

  readAudit: (params?: { request_id?: number; actor?: string; event?: string; limit?: number }) => {
    const search = new URLSearchParams()
    if (params?.request_id !== undefined) search.set('request_id', String(params.request_id))
    if (params?.actor) search.set('actor', params.actor)
    if (params?.event) search.set('event', params.event)
    if (params?.limit !== undefined) search.set('limit', String(params.limit))
    const query = search.toString()
    return request<AuditEvent[]>(`/api/audit${query ? `?${query}` : ''}`)
  },
}

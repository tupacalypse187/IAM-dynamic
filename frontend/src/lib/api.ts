import type {
  AccessRequest,
  AuditEvent,
  CatalogEntry,
  Credentials,
  DemoUser,
  ImpersonateResponse,
  LlmProfile,
  PolicyResponse,
  ProvidersResponse,
  RequestStatus,
  ReviewDecision,
} from '@/types/api'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''
const TOKEN_KEY = 'iam_token'

export function getToken(): string | null {
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

  // TEMPORARY hackathon demo aid: admin view-as-allowlisted-user.
  listDemoUsers: () => request<{ users: DemoUser[] }>('/api/auth/demo-users'),

  impersonate: (username: string) =>
    request<ImpersonateResponse>('/api/auth/impersonate', {
      method: 'POST',
      body: JSON.stringify({ username }),
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

  // Access requests + review workflow. Submit/record return the created
  // batch (usually one row): units share a batch_id for grouped display.
  submitRequest: (data: { request_text: string; provider?: string; model?: string; duration: number; environment?: string; profile_id?: number }) =>
    request<AccessRequest[]>('/api/requests', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  recordRequest: (data: {
    request_text: string
    provider?: string
    model?: string
    duration: number
    environment?: string
    policy: Record<string, unknown>
    risk: string
    explanation: string
    approver_note: string
    profile_id?: number
  }) =>
    request<AccessRequest[]>('/api/requests/record', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // LLM profiles + provider catalog
  listCatalog: () => request<CatalogEntry[]>('/api/providers/catalog'),

  updateCatalog: (data: { provider: string; model: string; enabled: boolean }) =>
    request<CatalogEntry>('/api/providers/catalog', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  listProfiles: () => request<LlmProfile[]>('/api/profiles'),

  createProfile: (data: { name: string; provider: string; model: string; api_key: string }) =>
    request<LlmProfile>('/api/profiles', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateProfile: (id: number, data: { name?: string; api_key?: string }) =>
    request<LlmProfile>(`/api/profiles/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  deleteProfile: (id: number) =>
    request<void>(`/api/profiles/${id}`, { method: 'DELETE' }),

  activateProfile: (id: number) =>
    request<LlmProfile>(`/api/profiles/${id}/activate`, {
      method: 'POST',
      body: JSON.stringify({}),
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

  discardRequest: (id: number) =>
    request<AccessRequest>(`/api/requests/${id}/discard`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),

  cancelRequest: (id: number) =>
    request<AccessRequest>(`/api/requests/${id}/cancel`, {
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

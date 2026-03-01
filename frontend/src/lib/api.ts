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

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }

  const token = getToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(`${BASE_URL}${url}`, {
    headers,
    ...options,
  })

  if (response.status === 401) {
    setToken(null)
    window.dispatchEvent(new CustomEvent('auth:logout'))
    throw new Error('Session expired. Please log in again.')
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(error.detail || `Request failed: ${response.status}`)
  }

  return response.json()
}

export interface AuthStatus {
  authenticated: boolean
  username: string | null
  auth_required: boolean
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

  // Providers
  getProviders: () =>
    request<{ providers: Array<{ id: string; name: string; model: string }>; account_id: string }>(
      '/config/providers'
    ),

  generatePolicy: (data: { request_text: string; provider: string; duration: number }) =>
    request('/api/generate-policy', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  issueCredentials: (data: { policy: Record<string, unknown>; duration: number; approved: boolean; change_case?: string }) =>
    request('/api/issue-credentials', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
}

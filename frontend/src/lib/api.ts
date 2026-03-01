const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(error.detail || `Request failed: ${response.status}`)
  }

  return response.json()
}

export const api = {
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

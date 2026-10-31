/**
 * Remote backend client for the desktop shell.
 *
 * The desktop is remote-first: policy synthesis, credential issuance, and
 * LLM provider selection all run against the existing FastAPI backend.
 * The base URL and JWT come from app config / OS vault; every call sends
 * the bearer token when one is stored.
 */

import type { GeneratedPolicy, LeaseCredentials } from '../../shared/ipc-contract'

export interface BackendConfig {
  baseUrl: string
  getToken: () => Promise<string | null>
}

interface BackendError extends Error {
  status: number
}

export function backendError(message: string, status: number): BackendError {
  const err = new Error(message) as BackendError
  err.status = status
  return err
}

async function callBackend<T>(
  config: BackendConfig,
  path: string,
  body: unknown,
): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const token = await config.getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  let response: Response
  try {
    response = await fetch(`${config.baseUrl}${path}`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    })
  } catch (cause) {
    throw backendError(
      `Cannot reach the backend at ${config.baseUrl}. Check the backend URL in settings and that the server is running.`,
      0,
    )
  }

  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }))
    const message =
      typeof payload?.detail === 'string' ? payload.detail : `Request failed: ${response.status}`
    throw backendError(message, response.status)
  }
  return (await response.json()) as T
}

export function createBackendClient(config: BackendConfig) {
  return {
    generatePolicy: (input: {
      request_text: string
      provider: string
      model?: string
      duration: number
    }) =>
      callBackend<GeneratedPolicy>(config, '/api/generate-policy', {
        request_text: input.request_text,
        provider: input.provider,
        model: input.model,
        duration: input.duration,
      }),

    issueCredentials: (input: {
      policy: Record<string, unknown>
      duration: number
      approved: boolean
      changeCase?: string
      risk?: string
      autoApproved?: boolean
    }) =>
      callBackend<LeaseCredentials>(config, '/api/issue-credentials', {
        policy: input.policy,
        duration: input.duration,
        approved: input.approved,
        change_case: input.changeCase,
        risk: input.risk ?? 'medium',
        auto_approved: input.autoApproved ?? false,
      }),
  }
}

export type BackendClient = ReturnType<typeof createBackendClient>

import type { AccessRequest } from '@/types/api'

/** Human-readable request identifier (req-00001). Display-only; the integer id stays canonical. */
export function formatRequestRef(id: number): string {
  return `req-${String(id).padStart(5, '0')}`
}

/**
 * Match a request against a free-text queue query. A query matches when it
 * appears in the request text, requester, or reviewer — or when it names the
 * request id as `7`, `00007`, `req-7`, or `req-00007` (case-insensitive).
 */
export function matchesRequestQuery(request: AccessRequest, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (q === '') return true
  if (
    request.request_text.toLowerCase().includes(q) ||
    request.requester.toLowerCase().includes(q) ||
    (request.reviewer ?? '').toLowerCase().includes(q)
  ) {
    return true
  }
  const digits = q.replace(/^req-?/, '').replace(/\D/g, '')
  if (digits === '') return false
  return request.id === Number(digits)
}

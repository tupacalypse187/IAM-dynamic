/**
 * User-facing copy for unreachable-server failures.
 *
 * Pure and dependency-free (no Vite, DOM, or Node APIs) so it stays
 * unit-testable with the stock Node runner — see `frontend/test/`.
 * The raw `fetch` TypeError ("Failed to fetch") tells users nothing;
 * this names where the request was going and what to check first.
 */
export function describeUnreachable(baseUrl: string | undefined): string {
  const target = baseUrl ? ` at ${baseUrl}` : ''
  return (
    `Cannot reach the server${target}. ` +
    'Check that the backend is running and reachable, then try again.'
  )
}

/**
 * Normalize a FastAPI error `detail` payload into a user-facing message.
 *
 * FastAPI returns a plain string for most errors but an ARRAY of
 * `{ loc, msg, ... }` objects for 422 validation failures. Stringifying
 * that array directly renders "[object Object],..." — join each item's
 * `msg` (with a trivial field prefix from `loc` when present) instead.
 */
export function formatErrorDetail(detail: unknown, fallback: string): string {
  if (typeof detail === 'string') {
    return detail === '' ? fallback : detail
  }
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (typeof item === 'string') return item
        if (item && typeof item === 'object') {
          const entry = item as { msg?: unknown; loc?: unknown }
          const msg =
            typeof entry.msg === 'string' ? entry.msg : safeStringify(entry.msg ?? item)
          const field = locField(entry.loc)
          return field && msg ? `${field}: ${msg}` : msg
        }
        return safeStringify(item)
      })
      .filter((part) => part !== '')
    if (parts.length > 0) return parts.join('; ')
    return fallback
  }
  return fallback
}

function locField(loc: unknown): string {
  if (!Array.isArray(loc)) return ''
  // Drop the leading "body"/"query"/"path" segment FastAPI always adds;
  // the remainder names the offending field (e.g. ["body","duration"]).
  const segments = loc.map(String).filter((s) => s !== 'body')
  return segments.join('.')
}

function safeStringify(value: unknown): string {
  try {
    const text = JSON.stringify(value)
    return text === undefined ? '' : text
  } catch {
    return ''
  }
}

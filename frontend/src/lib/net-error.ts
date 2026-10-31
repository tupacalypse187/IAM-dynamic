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

/** TEMPORARY hackathon demo aid: per-tab view-as session persistence. */

export interface ViewAsSession {
  username: string
  adminToken: string
  adminName: string
}

const STORAGE_KEY = 'iam-view-as'

function isSession(value: unknown): value is ViewAsSession {
  if (typeof value !== 'object' || value === null) return false
  const s = value as Record<string, unknown>
  return (
    typeof s.username === 'string' &&
    typeof s.adminToken === 'string' &&
    typeof s.adminName === 'string'
  )
}

export function loadViewAsSession(
  storage?: Pick<Storage, 'getItem'>,
): ViewAsSession | null {
  const store =
    storage ?? (typeof sessionStorage !== 'undefined' ? sessionStorage : undefined)
  if (!store) return null
  try {
    const raw = store.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    return isSession(parsed) ? parsed : null
  } catch {
    return null
  }
}

export function saveViewAsSession(
  session: ViewAsSession,
  storage?: Pick<Storage, 'setItem'>,
): void {
  try {
    const store =
      storage ?? (typeof sessionStorage !== 'undefined' ? sessionStorage : undefined)
    store?.setItem(STORAGE_KEY, JSON.stringify(session))
  } catch {
    // Storage unavailable — the session simply won't survive reload.
  }
}

export function clearViewAsSession(
  storage?: Pick<Storage, 'removeItem'>,
): void {
  try {
    const store =
      storage ?? (typeof sessionStorage !== 'undefined' ? sessionStorage : undefined)
    store?.removeItem(STORAGE_KEY)
  } catch {
    // Nothing to clean up.
  }
}

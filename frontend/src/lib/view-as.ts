/** TEMPORARY hackathon demo aid: per-tab view-as session persistence. */

export interface ViewAsSession {
  username: string
  adminToken: string
  adminName: string
}

const STORAGE_KEY = 'iam-view-as'
/** Survives app restarts so a fresh boot can restore the admin session. */
const ADMIN_STASH_KEY = 'iam-view-as-admin'

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

export interface AdminStash {
  adminToken: string
  adminName: string
  username: string
}

/** Stash the admin session where a fresh boot can find it. */
export function saveAdminStash(
  stash: AdminStash,
  storage?: Pick<Storage, 'setItem'>,
): void {
  try {
    const store =
      storage ?? (typeof localStorage !== 'undefined' ? localStorage : undefined)
    store?.setItem(ADMIN_STASH_KEY, JSON.stringify(stash))
  } catch {
    // No stash — a restart simply lands logged out instead of as admin.
  }
}

export function loadAdminStash(
  storage?: Pick<Storage, 'getItem'>,
): AdminStash | null {
  const store =
    storage ?? (typeof localStorage !== 'undefined' ? localStorage : undefined)
  if (!store) return null
  try {
    const raw = store.getItem(ADMIN_STASH_KEY)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null) return null
    const s = parsed as Record<string, unknown>
    if (
      typeof s.adminToken !== 'string' ||
      typeof s.adminName !== 'string' ||
      typeof s.username !== 'string'
    ) {
      return null
    }
    return { adminToken: s.adminToken, adminName: s.adminName, username: s.username }
  } catch {
    return null
  }
}

export function clearAdminStash(
  storage?: Pick<Storage, 'removeItem'>,
): void {
  try {
    const store =
      storage ?? (typeof localStorage !== 'undefined' ? localStorage : undefined)
    store?.removeItem(ADMIN_STASH_KEY)
  } catch {
    // Nothing to clean up.
  }
}

/** True when the token carries the impersonation claim (decode only). */
export function isViewAsToken(token: string | null): boolean {
  if (!token || typeof atob !== 'function') return false
  try {
    const payload = token.split('.')[1]
    if (!payload) return false
    const padded = payload.replace(/-/g, '+').replace(/_/g, '/')
    const json: unknown = JSON.parse(atob(padded))
    if (typeof json !== 'object' || json === null) return false
    return (
      typeof (json as Record<string, unknown>).impersonated_from === 'string'
    )
  } catch {
    return false
  }
}

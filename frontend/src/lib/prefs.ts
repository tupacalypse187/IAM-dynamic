/** User preferences persisted in localStorage (renderer-side only). */

export interface Prefs {
  /** Hover tooltips on interactive controls. */
  tooltips: boolean
  /** Start the guided demo tour automatically for first-run users. */
  tourAutoplay: boolean
  /** Collapse the desktop sidebar rail (mobile drawer unaffected). */
  sidebarCollapsed: boolean
  /** Monaco theme id for the JSON policy preview ('match' follows the app theme). */
  codeTheme: string
}

export const DEFAULT_PREFS: Prefs = {
  tooltips: true,
  tourAutoplay: true,
  sidebarCollapsed: false,
  codeTheme: 'match',
}

const STORAGE_KEY = 'iam-prefs-v1'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

/** Read stored prefs, falling back to defaults for missing/invalid keys. */
export function loadPrefs(storage?: Pick<Storage, 'getItem'>): Prefs {
  const store = storage ?? (typeof localStorage !== 'undefined' ? localStorage : undefined)
  if (!store) return { ...DEFAULT_PREFS }
  try {
    const raw = store.getItem(STORAGE_KEY)
    if (!raw) return { ...DEFAULT_PREFS }
    const parsed: unknown = JSON.parse(raw)
    if (!isRecord(parsed)) return { ...DEFAULT_PREFS }
    return {
      tooltips: typeof parsed.tooltips === 'boolean' ? parsed.tooltips : DEFAULT_PREFS.tooltips,
      tourAutoplay:
        typeof parsed.tourAutoplay === 'boolean' ? parsed.tourAutoplay : DEFAULT_PREFS.tourAutoplay,
      sidebarCollapsed:
        typeof parsed.sidebarCollapsed === 'boolean'
          ? parsed.sidebarCollapsed
          : DEFAULT_PREFS.sidebarCollapsed,
      codeTheme:
        typeof parsed.codeTheme === 'string' ? parsed.codeTheme : DEFAULT_PREFS.codeTheme,
    }
  } catch {
    return { ...DEFAULT_PREFS }
  }
}

/** Merge a partial update into storage. Never throws (private-mode safe). */
export function savePrefs(patch: Partial<Prefs>, storage?: Pick<Storage, 'setItem' | 'getItem'>): Prefs {
  const next = { ...loadPrefs(storage), ...patch }
  try {
    const store = storage ?? (typeof localStorage !== 'undefined' ? localStorage : undefined)
    store?.setItem(STORAGE_KEY, JSON.stringify(next))
  } catch {
    // Private mode or unavailable storage — prefs apply for this session only.
  }
  return next
}

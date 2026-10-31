/**
 * Desktop configuration — single source for backend URL, update feed,
 * and runtime flags. Precedence: environment variable > stored setting >
 * built-in default. All values are safe to log (no secrets).
 */

export interface DesktopConfig {
  backendUrl: string
  updateFeedUrl: string | null
  isDev: boolean
}

function normalizeUrl(value: string | undefined, fallback: string): string {
  const raw = (value ?? '').trim() || fallback
  return raw.replace(/\/+$/, '')
}

/**
 * Dev-mode decision as a pure function so it stays unit-testable.
 * NOTE: never use NODE_ENV here — electron-builder does not set it in
 * packaged apps, which once made every release load the dev server URL
 * (blue screen) and pop DevTools. `app.isPackaged` is the only signal.
 */
export function resolveDevMode(
  isPackaged: boolean,
  env: NodeJS.ProcessEnv = process.env,
): boolean {
  if ((env['IAM_DESKTOP_DEV'] ?? '').trim() === '1') return true
  return !isPackaged
}

export function loadConfig(isPackaged: boolean): DesktopConfig {
  const feed = (process.env.IAM_DESKTOP_UPDATE_FEED_URL ?? '').trim()
  return {
    backendUrl: normalizeUrl(process.env.IAM_DESKTOP_BACKEND_URL, 'http://localhost:8000'),
    updateFeedUrl: feed || null,
    isDev: resolveDevMode(isPackaged),
  }
}

import type { DesktopApi } from '@/types/desktop'

/**
 * Desktop bridge access. In a browser there is no preload bridge, so every
 * helper degrades gracefully — callers branch on `isDesktop()` and use the
 * direct web API path instead.
 */

export function isDesktop(): boolean {
  return typeof window !== 'undefined' && typeof window.desktopApi !== 'undefined'
}

/**
 * Resolve the platform string, preferring `userAgentData.platform` but
 * falling through on empty values. Electron exposes `userAgentData` with an
 * EMPTY low-entropy `platform` (""), so a `??` chain keeps "" and macOS goes
 * undetected — an `||` chain falls back to `navigator.platform` ("MacIntel").
 */
export function resolvePlatform(
  userAgentDataPlatform?: unknown,
  navigatorPlatform?: string | null,
): string {
  if (typeof userAgentDataPlatform === 'string' && userAgentDataPlatform) {
    return userAgentDataPlatform
  }
  return navigatorPlatform || ''
}

/** macOS reports "MacIntel"/"macOS" via navigator; main-process values report "darwin". */
export function isMacPlatformString(platform: string | null | undefined): boolean {
  if (!platform) return false
  return /^mac/i.test(platform) || platform === 'darwin'
}

/**
 * Platform injected by the main process (`?platform=darwin` on the
 * renderer URL). Deterministic — independent of bridge and navigator
 * quirks, which both failed in the field.
 */
export function queryPlatform(search?: string): string | null {
  try {
    const raw =
      search ?? (typeof window !== 'undefined' ? window.location.search : '')
    const value = new URLSearchParams(raw).get('platform')
    return value || null
  } catch {
    return null
  }
}

/**
 * True only inside the packaged app on macOS — the one configuration with a
 * frameless `hiddenInset` window whose traffic lights overlay the top-left
 * of the UI. Callers reserve a drag strip there; browsers (no preload
 * bridge) always get false so web layouts are untouched. Parameters default
 * to the live globals and exist so tests can inject values.
 */
export function isMacDesktop(
  bridge: unknown = typeof window !== 'undefined' ? window.desktopApi : undefined,
  platform?: string,
): boolean {
  if (typeof bridge === 'undefined') return false
  if (platform !== undefined) return isMacPlatformString(platform)
  if (typeof navigator === 'undefined') return false
  const userAgentData = (
    navigator as Navigator & { userAgentData?: { platform?: string } }
  ).userAgentData
  return isMacPlatformString(resolvePlatform(userAgentData?.platform, navigator.platform))
}

function requireApi(): DesktopApi {
  if (!window.desktopApi) {
    throw new Error('Desktop bridge is unavailable (running in a browser).')
  }
  return window.desktopApi
}

export const desktop = {
  get isDesktop() {
    return isDesktop()
  },
  getAppInfo: () => requireApi().getAppInfo(),
  generatePolicy: (...args: Parameters<DesktopApi['generatePolicy']>) =>
    requireApi().generatePolicy(...args),
  onAgentProgress: (...args: Parameters<DesktopApi['onAgentProgress']>) =>
    requireApi().onAgentProgress(...args),
  issueCredentials: (...args: Parameters<DesktopApi['issueCredentials']>) =>
    requireApi().issueCredentials(...args),
  activateRequest: (...args: Parameters<DesktopApi['activateRequest']>) =>
    requireApi().activateRequest(...args),
  logAudit: (...args: Parameters<DesktopApi['logAudit']>) =>
    requireApi().logAudit(...args),
  revokeCredentials: () => requireApi().revokeCredentials(),
  getLeaseStatus: () => requireApi().getLeaseStatus(),
  getRecentEvents: (...args: Parameters<DesktopApi['getRecentEvents']>) =>
    requireApi().getRecentEvents(...args),
  exportLedger: (...args: Parameters<DesktopApi['exportLedger']>) =>
    requireApi().exportLedger(...args),
  setToken: (token: string) => requireApi().setToken(token),
  clearToken: () => requireApi().clearToken(),
  checkForUpdates: () => requireApi().checkForUpdates(),
  quitAndInstall: () => requireApi().quitAndInstall(),
  onUpdaterEvent: (...args: Parameters<DesktopApi['onUpdaterEvent']>) =>
    requireApi().onUpdaterEvent(...args),
  onCaptureShortcut: (...args: Parameters<DesktopApi['onCaptureShortcut']>) =>
    requireApi().onCaptureShortcut(...args),
}

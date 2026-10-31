import type { DesktopApi } from '@/types/desktop'

/**
 * Desktop bridge access. In a browser there is no preload bridge, so every
 * helper degrades gracefully — callers branch on `isDesktop()` and use the
 * direct web API path instead.
 */

export function isDesktop(): boolean {
  return typeof window !== 'undefined' && typeof window.desktopApi !== 'undefined'
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

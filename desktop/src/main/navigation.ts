/**
 * URL policy for the desktop shell's single app window.
 *
 * Pure helpers with no Electron imports so they are unit-testable with
 * plain node:test against the compiled output.
 */

export const DEV_URL = 'http://localhost:3000'

/**
 * External URLs the shell may hand to the OS browser via
 * shell.openExternal: http(s) only. Everything else (file:, data:,
 * custom schemes) is denied so a crafted link can never reach a local
 * file handler or another app's protocol.
 */
export function isAllowedExternalUrl(urlString: string): boolean {
  let parsed: URL
  try {
    parsed = new URL(urlString)
  } catch {
    return false
  }
  return parsed.protocol === 'http:' || parsed.protocol === 'https:'
}

/**
 * URLs the app window itself may navigate to: the dev-server origin, the
 * packaged file:// bundle index, or the app-generated data:text/html load
 * error page (see the did-fail-load handler in main.ts). The boundary check
 * uses DEV_URL + '/' (not a bare prefix) so http://localhost:3000.evil.com
 * does not pass. Everything else must be prevented by the caller; http(s)
 * strays are re-opened in the OS browser instead.
 */
export function isInternalNavigationUrl(urlString: string, devUrl: string = DEV_URL): boolean {
  if (
    urlString === devUrl ||
    urlString.startsWith(`${devUrl}/`) ||
    urlString.startsWith(`${devUrl}?`) ||
    urlString.startsWith(`${devUrl}#`)
  ) {
    return true
  }
  let parsed: URL
  try {
    parsed = new URL(urlString)
  } catch {
    return false
  }
  if (parsed.protocol === 'file:') {
    // pathname excludes query/hash, so same-file variants are covered.
    return parsed.pathname.endsWith('frontend-dist/index.html')
  }
  if (parsed.protocol === 'data:') {
    return urlString.startsWith('data:text/html,')
  }
  return false
}

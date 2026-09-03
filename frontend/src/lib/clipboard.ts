/**
 * Clipboard helper with a fallback chain.
 *
 * 1. Async Clipboard API (secure contexts: https or localhost)
 * 2. execCommand('copy') via a hidden textarea (older browsers, http/LAN)
 *
 * Returns true when the text verifiably reached the clipboard.
 */
export async function copyText(text: string): Promise<boolean> {
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch {
      // Permission denied or document not focused — fall through to legacy path
    }
  }

  try {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.setAttribute('readonly', '')
    textarea.style.position = 'fixed'
    textarea.style.top = '0'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    try {
      textarea.select()
      textarea.setSelectionRange(0, text.length)
      return document.execCommand('copy')
    } finally {
      // execCommand can throw in some browsers; never leak the textarea
      document.body.removeChild(textarea)
    }
  } catch {
    return false
  }
}

import { useEffect } from 'react'
import { desktop } from '@/lib/desktop'

/**
 * Central keyboard-shortcut registry — the single source of truth.
 * The Help view renders this list, so documented shortcuts cannot drift
 * from implemented ones: add the shortcut here or it doesn't exist.
 */

export interface ShortcutDef {
  id: string
  label: string
  description: string
  /** Display keys, e.g. ['⌘/Ctrl', 'Shift', 'I']. */
  keys: string[]
}

export const SHORTCUTS: ShortcutDef[] = [
  {
    id: 'capture',
    label: 'Voice / quick capture',
    description: 'Focus the request box from anywhere (desktop global shortcut).',
    keys: ['⌘/Ctrl', 'Shift', 'I'],
  },
  {
    id: 'shortcuts-help',
    label: 'Keyboard shortcuts',
    description: 'Open this shortcut reference.',
    keys: ['?'],
  },
  {
    id: 'tour-advance',
    label: 'Advance tour',
    description: 'Move to the next step while the guided tour is open.',
    keys: ['→', 'Enter'],
  },
  {
    id: 'tour-exit',
    label: 'Exit tour / dialogs',
    description: 'Close the tour, help dialog, or cancel the current step.',
    keys: ['Esc'],
  },
]

/**
 * Global key handling owned by the app shell:
 * - `?` (Shift+/) opens the shortcut reference. Ignored while typing,
 *   except that Escape still bubbles to dialogs/tour via Radix defaults.
 */
export function useGlobalShortcuts(onOpenHelp: () => void) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null
      const typing =
        target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)
      if (typing) return
      if (e.key === '?' && !e.metaKey && !e.ctrlKey && !e.altKey) {
        e.preventDefault()
        onOpenHelp()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onOpenHelp])
}

/**
 * Desktop global capture shortcut (Cmd/Ctrl+Shift+I, registered in main):
 * focuses the request textarea and toasts a hint. Voice transcription
 * itself is stretch — this path also serves typed quick-capture.
 */
export function useCaptureShortcut(onCapture: () => void) {
  useEffect(() => {
    if (!desktop.isDesktop) return
    return desktop.onCaptureShortcut(onCapture)
  }, [onCapture])
}

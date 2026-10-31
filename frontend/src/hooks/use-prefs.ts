import { createContext, useContext } from 'react'
import { DEFAULT_PREFS, type Prefs } from '@/lib/prefs'

export type PrefsState = {
  prefs: Prefs
  updatePrefs: (patch: Partial<Prefs>) => void
}

export const PrefsContext = createContext<PrefsState>({
  prefs: DEFAULT_PREFS,
  updatePrefs: () => null,
})

export function usePrefs() {
  const context = useContext(PrefsContext)
  if (context === undefined) throw new Error('usePrefs must be used within a PrefsProvider')
  return context
}

import { useCallback, useMemo, useState, type ReactNode } from 'react'
import * as Tooltip from '@radix-ui/react-tooltip'
import { PrefsContext, usePrefs } from '@/hooks/use-prefs'
import { loadPrefs, savePrefs, type Prefs } from '@/lib/prefs'

/**
 * App-wide preferences: loads once from localStorage, persists updates.
 * Wraps the authenticated shell in App (never the login gate).
 */
export function PrefsProvider({ children }: { children: ReactNode }) {
  const [prefs, setPrefs] = useState<Prefs>(() => loadPrefs())

  const updatePrefs = useCallback((patch: Partial<Prefs>) => {
    setPrefs((current) => {
      const next = { ...current, ...patch }
      savePrefs(patch)
      return next
    })
  }, [])

  const value = useMemo(() => ({ prefs, updatePrefs }), [prefs, updatePrefs])
  return <PrefsContext.Provider value={value}>{children}</PrefsContext.Provider>
}

interface TipProps {
  /** Hover text. Omit to render children bare (no tooltip DOM at all). */
  label?: string
  side?: 'top' | 'right' | 'bottom' | 'left'
  children: ReactNode
}

/**
 * Settings-gated hover tooltip. When the user disables tooltips (or no
 * label is given), children render with zero tooltip markup — the
 * preference truly removes them instead of hiding them with CSS.
 */
export function Tip({ label, side = 'top', children }: TipProps) {
  const { prefs } = usePrefs()
  if (!label || !prefs.tooltips) return <>{children}</>
  return <MaybeTooltip label={label} side={side}>{children}</MaybeTooltip>
}

function MaybeTooltip({ label, side, children }: Required<Pick<TipProps, 'label' | 'side'>> & { children: ReactNode }) {
  return (
    <Tooltip.Provider delayDuration={350}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>{children}</Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            side={side}
            sideOffset={6}
            className="z-50 max-w-xs rounded-md border bg-popover px-2.5 py-1.5 text-xs text-popover-foreground shadow-md motion-safe:data-[state=delayed-open]:animate-in motion-safe:data-[state=delayed-open]:fade-in-0"
          >
            {label}
            <Tooltip.Arrow className="fill-popover" />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  )
}

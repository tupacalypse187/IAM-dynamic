import { useEffect, useState } from 'react'
import { Download, RefreshCw, AlertTriangle } from 'lucide-react'
import { desktop } from '@/lib/desktop'
import { useToast } from '@/hooks/use-toast'
import { Button } from '@/components/ui/button'

/**
 * Desktop auto-update UI. Listens for main-process updater events:
 * - available  -> info toast (download starts automatically in main)
 * - downloaded -> persistent banner with "Restart & apply"
 * - error      -> warning toast, never blocks the user
 * Renders nothing in browsers or when updates are disabled.
 */
export default function UpdateBanner() {
  const { toast } = useToast()
  const [downloadedVersion, setDownloadedVersion] = useState<string | null>(null)
  const [availableVersion, setAvailableVersion] = useState<string | null>(null)

  useEffect(() => {
    if (!desktop.isDesktop) return
    return desktop.onUpdaterEvent((event) => {
      switch (event.type) {
        case 'available':
          setAvailableVersion(event.version)
          toast({
            title: `Update ${event.version} found`,
            description: 'Downloading in the background — keep working.',
          })
          break
        case 'downloaded':
          setAvailableVersion(null)
          setDownloadedVersion(event.version)
          break
        case 'error':
          toast({
            title: 'Update check failed',
            description: event.message,
            variant: 'destructive',
          })
          break
        default:
          break
      }
    })
  }, [toast])

  if (!desktop.isDesktop) return null

  if (downloadedVersion) {
    return (
      <div
        className="fixed bottom-4 left-1/2 z-50 flex w-[calc(100%-2rem)] max-w-xl -translate-x-1/2 items-center gap-3 rounded-lg border bg-card p-4 shadow-lg"
        role="status"
        aria-live="polite"
      >
        <RefreshCw className="h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
        <p className="flex-1 text-sm">
          <span className="font-medium">Update {downloadedVersion} ready.</span>{' '}
          Restart to apply it — your local audit log is preserved.
        </p>
        <Button size="sm" onClick={() => void desktop.quitAndInstall()}>
          Restart & apply
        </Button>
      </div>
    )
  }

  if (availableVersion) {
    return (
      <div
        className="fixed bottom-4 left-1/2 z-50 flex w-[calc(100%-2rem)] max-w-xl -translate-x-1/2 items-center gap-3 rounded-lg border bg-card p-3 shadow-lg"
        role="status"
        aria-live="polite"
      >
        <Download className="h-4 w-4 animate-pulse text-muted-foreground" aria-hidden="true" />
        <p className="flex-1 text-sm text-muted-foreground">
          Downloading update {availableVersion}…
        </p>
      </div>
    )
  }

  return null
}

export function UpdateCheckHint() {
  if (!desktop.isDesktop) return null
  return (
    <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
      <AlertTriangle className="h-3 w-3" aria-hidden="true" />
      Updates install only when you restart — nothing applies silently.
    </p>
  )
}

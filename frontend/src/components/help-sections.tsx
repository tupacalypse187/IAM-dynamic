import { useEffect, useState } from 'react'
import { BookOpen, Download, Keyboard, History, RefreshCw } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { desktop } from '@/lib/desktop'
import { SHORTCUTS } from '@/lib/shortcuts'
import { useToast } from '@/hooks/use-toast'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

interface HelpSectionsProps {
  appVersion: string | null
}

function downloadText(filename: string, text: string, mime: string) {
  const blob = new Blob([text], { type: mime })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

const GUIDES = [
  {
    title: 'Requesting access',
    body: `1. Describe the **job** you need to do, not the IAM actions.\n2. Fill in task / resources / ticket if you know them.\n3. Answer up to three follow-up questions when asked.\n4. Review the policy, summary, and guardrail findings.\n5. Issue credentials — they expire automatically.`,
  },
  {
    title: 'Reading a guardrail finding',
    body: `Each finding names a **location** (e.g. \`Statement[0].Action\`), explains the risk, and suggests a fix. **Revise with this fix** sends the suggestion back to the request box. Findings can raise the risk level, never lower it.`,
  },
  {
    title: 'Credential lifecycle',
    body: `Temporary credentials live in the desktop app only for their lease. The tray shows the countdown and warns 5 minutes before expiry. **Revoke** discards them locally. Note: AWS STS sessions cannot be force-revoked server-side — expiry is the enforcement.`,
  },
] as const

export default function HelpSections({ appVersion }: HelpSectionsProps) {
  const { toast } = useToast()
  const [events, setEvents] = useState<Array<{ id: number; ts: string; kind: string; summary: string }>>([])
  const [checking, setChecking] = useState(false)

  useEffect(() => {
    if (!desktop.isDesktop) return
    desktop.getRecentEvents(20).then(setEvents).catch(() => undefined)
  }, [])

  const handleExport = async (format: 'markdown' | 'json') => {
    if (!desktop.isDesktop) return
    try {
      const text = await desktop.exportLedger(format)
      downloadText(`iam-audit.${format === 'json' ? 'json' : 'md'}`, text, 'text/plain')
    } catch (err) {
      toast({
        title: 'Export failed',
        description: err instanceof Error ? err.message : 'Could not export the audit log.',
        variant: 'destructive',
      })
    }
  }

  const handleCheckUpdates = async () => {
    if (!desktop.isDesktop) return
    setChecking(true)
    try {
      await desktop.checkForUpdates()
      toast({ title: 'Checking for updates…', description: 'You will be notified of the result.' })
    } finally {
      setChecking(false)
    }
  }

  return (
    <>
      {/* Shortcuts */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Keyboard className="h-5 w-5" aria-hidden="true" />
            Keyboard shortcuts
          </CardTitle>
          <CardDescription>Press ? anywhere to open Settings.</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="divide-y">
            {SHORTCUTS.map((s) => (
              <li key={s.id} className="flex items-center gap-3 py-2.5">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{s.label}</p>
                  <p className="truncate text-xs text-muted-foreground">{s.description}</p>
                </div>
                <span className="flex shrink-0 gap-1">
                  {s.keys.map((k) => (
                    <kbd
                      key={k}
                      className="rounded border bg-muted px-1.5 py-0.5 font-mono text-xs"
                    >
                      {k}
                    </kbd>
                  ))}
                </span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      {/* Guides */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BookOpen className="h-5 w-5" aria-hidden="true" />
            How-to guides
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          {GUIDES.map((g) => (
            <div key={g.title}>
              <h3 className="font-semibold">{g.title}</h3>
              <div className="prose prose-sm mt-1 max-w-none dark:prose-invert">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{g.body}</ReactMarkdown>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Updates */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <RefreshCw className="h-5 w-5" aria-hidden="true" />
            Updates
          </CardTitle>
          <CardDescription>
            {desktop.isDesktop
              ? `Desktop app${appVersion ? ` v${appVersion}` : ''}. Updates download in the background and apply only on restart.`
              : 'You are running in a browser — updates are handled by your deployment.'}
          </CardDescription>
        </CardHeader>
        {desktop.isDesktop && (
          <CardContent>
            <Button variant="outline" onClick={handleCheckUpdates} disabled={checking}>
              {checking ? 'Checking…' : 'Check for updates now'}
            </Button>
          </CardContent>
        )}
      </Card>

      {/* Audit log */}
      {desktop.isDesktop && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <History className="h-5 w-5" aria-hidden="true" />
              Local audit log
            </CardTitle>
            <CardDescription>
              Generations, approvals, issuances, and revocations on this machine. For PDF,
              export Markdown and print from any Markdown viewer.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => void handleExport('markdown')}>
                <Download className="mr-1 h-3 w-3" /> Markdown
              </Button>
              <Button variant="outline" size="sm" onClick={() => void handleExport('json')}>
                <Download className="mr-1 h-3 w-3" /> JSON
              </Button>
            </div>
            {events.length === 0 ? (
              <p className="text-sm text-muted-foreground">No audit events yet on this machine.</p>
            ) : (
              <ul className="divide-y">
                {events.map((e) => (
                  <li key={e.id} className="flex items-center gap-3 py-2">
                    <Badge variant="outline" className="shrink-0 font-mono text-xs">
                      #{e.id}
                    </Badge>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm">{e.summary}</p>
                      <p className="font-mono text-xs text-muted-foreground">
                        {e.ts} · {e.kind}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}
    </>
  )
}

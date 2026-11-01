import type { LlmProfile, ProvidersResponse } from '@/types/api'
import { useTheme } from '@/hooks/use-theme'
import { Button } from './ui/button'
import { Tip } from './tip'
import { ScrollArea } from './ui/scroll-area'
import { Separator } from './ui/separator'
import { Label } from './ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select'
import { Monitor, Moon, Sun, LayoutTemplate, Settings2 } from 'lucide-react'

interface SidebarContentProps {
  config?: ProvidersResponse
  onRequestTextChange: (text: string) => void
  onTemplateSelected?: () => void
  /** True on macOS frameless windows — reserves the traffic-light strip. */
  macDesktop?: boolean
  /** Show the strip here (drawer). The rail leaves it to the full-width strip. */
  showTopStrip?: boolean
  /** Saved LLM profiles for the switcher (empty = server defaults). */
  profiles?: LlmProfile[]
  onSelectProfile?: (id: number) => void
  onManageProfiles?: () => void
}

const templates = [
  { id: 'debug', name: '🐞 Debug my app', prompt: 'I need to debug my application errors in dev: read CloudWatch log streams for the (LOG GROUP NAME) log group and describe the related EC2 instances, for 2 days.' },
  { id: 'deploy', name: '🚀 Ship a release', prompt: 'I need to deploy Friday’s release to staging: invoke the (FUNCTION NAME) Lambda function and read/write the (BUCKET NAME) S3 bucket, for 3 days.' },
  { id: 'readonly', name: '🔍 Read-only look', prompt: 'I need read-only access to list and download files from the (BUCKET NAME) S3 bucket in (dev/stage/prod) to investigate (WHAT HAPPENED).' },
  { id: 'data', name: '📊 Query data', prompt: 'I need to query and scan items (no writes) from the (TABLE NAME) DynamoDB table in (dev/stage/prod) for analytics, for 1 week.' },
  { id: 'secrets', name: '🔑 Fetch a secret', prompt: 'I need to retrieve the (SECRET NAME) secret from Secrets Manager in (dev/stage/prod) for the app to start.' },
  { id: 'incident', name: '🚨 Handle an incident', prompt: 'There is an ongoing incident in prod: I need to read CloudWatch alarms and metrics plus reboot EC2 instances tagged (TAG=VALUE) for the next 2 hours.' },
]

const themeCycle: ('system' | 'light' | 'dark')[] = ['system', 'light', 'dark']
const themeLabels = { system: 'System theme', light: 'Light theme', dark: 'Dark theme' }
const themeIcons = {
  system: Monitor,
  light: Sun,
  dark: Moon,
}

/**
 * Shared sidebar body — rendered in the desktop rail and the mobile drawer.
 * Quick actions only; AI provider and full preferences live in Settings.
 */
export function SidebarContent({
  config,
  onRequestTextChange,
  onTemplateSelected,
  macDesktop = false,
  showTopStrip = true,
  profiles = [],
  onSelectProfile,
  onManageProfiles,
}: SidebarContentProps) {
  const activeProfile = profiles.find((p) => p.active) ?? null
  const { theme, setTheme } = useTheme()

  const cycleTheme = () => {
    const currentIndex = themeCycle.indexOf(theme as 'system' | 'light' | 'dark')
    const nextTheme = themeCycle[(currentIndex + 1) % themeCycle.length]
    setTheme(nextTheme)
  }

  const ThemeIcon = themeIcons[theme as 'system' | 'light' | 'dark']
  const themeLabel = themeLabels[theme as 'system' | 'light' | 'dark']

  return (
    <div className="flex h-full flex-col">
      {/* Traffic-light safe area (macOS frameless window only): clears the
          hiddenInset lights and doubles as a grabbable drag strip. The rail
          is already below the full-width strip, so only the drawer shows it. */}
      {macDesktop && showTopStrip && (
        <div className="app-drag h-7 w-full shrink-0 select-none" aria-hidden="true" />
      )}

      {/* Theme quick toggle */}
      <div className="border-b border-sidebar-border p-4">
        <div className="flex items-center justify-between">
          <Label className="text-xs text-sidebar-foreground/70">Theme</Label>
          <Tip label={`Switch theme — currently ${themeLabel.toLowerCase()}. Full theme picker lives in Settings.`}>
            <Button
              variant="outline"
              size="sm"
              onClick={cycleTheme}
              className="h-9 w-9 p-0 border-sidebar-border bg-transparent text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
              aria-label={`Change theme (currently ${themeLabel})`}
            >
              <ThemeIcon className="h-4 w-4" />
            </Button>
          </Tip>
        </div>
      </div>

      {/* LLM profile switcher */}
      <div className="border-b border-sidebar-border p-4">
        <div className="mb-2 flex items-center justify-between">
          <Label className="text-xs text-sidebar-foreground/70">LLM Profile</Label>
          {onManageProfiles && (
            <Tip label="Add, rename, or rotate profile keys in Settings">
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs text-sidebar-foreground/70 hover:text-sidebar-accent-foreground"
                onClick={onManageProfiles}
              >
                <Settings2 className="mr-1 h-3 w-3" />
                Manage
              </Button>
            </Tip>
          )}
        </div>
        {profiles.length === 0 ? (
          <p className="text-xs text-sidebar-foreground/60">
            Server defaults.{' '}
            {onManageProfiles && (
              <button
                type="button"
                className="underline hover:text-sidebar-accent-foreground"
                onClick={onManageProfiles}
              >
                Save your own key
              </button>
            )}
          </p>
        ) : (
          <Tip label="Whose key evaluates new requests">
            <Select
              value={activeProfile ? String(activeProfile.id) : ''}
              onValueChange={(v) => onSelectProfile?.(Number(v))}
            >
              <SelectTrigger className="border-sidebar-border bg-transparent text-sidebar-foreground">
                <SelectValue placeholder="Select profile" />
              </SelectTrigger>
              <SelectContent>
                {profiles.map((p) => (
                  <SelectItem key={p.id} value={String(p.id)}>
                    {p.name} · {p.model}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Tip>
        )}
      </div>

      {/* Quick Templates */}
      <ScrollArea className="flex-1">
        <div className="p-4 space-y-4">
          <div>
            <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold">
              <LayoutTemplate className="h-4 w-4 text-sidebar-foreground/70" aria-hidden="true" />
              Quick Templates
            </h3>
            <div className="space-y-1">
              {templates.map((template) => (
                <Tip key={template.id} label={template.prompt} side="right">
                  <button
                    onClick={() => {
                      onRequestTextChange(template.prompt)
                      onTemplateSelected?.()
                    }}
                    className="w-full rounded-md px-3 py-2 text-left text-sm text-sidebar-foreground/85 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring"
                  >
                    {template.name}
                  </button>
                </Tip>
              ))}
            </div>
          </div>

          <Separator className="bg-sidebar-border" />

          {/* Configuration */}
          <div>
            <h3 className="mb-2 text-sm font-semibold">Account Info</h3>
            <div className="break-all text-sm text-sidebar-foreground/85">
              Account: {config?.account_id || 'N/A'}
            </div>
          </div>
        </div>
      </ScrollArea>
    </div>
  )
}

/**
 * Desktop sidebar rail (hidden below the lg breakpoint; the App shell
 * renders SidebarContent inside a drawer for small screens).
 */
export default function Sidebar(props: SidebarContentProps) {
  return (
    <aside className="hidden w-72 shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground lg:flex">
      <div className="flex min-h-0 flex-1 flex-col">
        <SidebarContent {...props} />
      </div>
    </aside>
  )
}

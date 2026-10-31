import { ProvidersResponse } from '@/types/api'
import { useTheme } from '@/hooks/use-theme'
import { Button } from './ui/button'
import { Tip } from './tip'
import { ScrollArea } from './ui/scroll-area'
import { Separator } from './ui/separator'
import { Label } from './ui/label'
import { Monitor, Moon, Sun, LayoutTemplate } from 'lucide-react'

interface SidebarContentProps {
  config?: ProvidersResponse
  onRequestTextChange: (text: string) => void
  onTemplateSelected?: () => void
  /** True on macOS frameless windows — reserves the traffic-light strip. */
  macDesktop?: boolean
}

const templates = [
  { id: 's3', name: 'S3 Read-Only', prompt: 'I need read-only access to list and get objects from all S3 buckets.' },
  { id: 'ec2', name: 'EC2 Observer', prompt: 'I need to describe instances and view status checks for EC2.' },
  { id: 'lambda', name: 'Lambda Invoker', prompt: 'I need to invoke Lambda functions in us-east-1.' },
  { id: 'logs', name: 'CloudWatch Logs', prompt: 'I need to read and filter CloudWatch log streams for application debugging.' },
  { id: 'dynamodb', name: 'DynamoDB Reader', prompt: 'I need to query and scan items from DynamoDB tables in production.' },
  { id: 'secrets', name: 'Secrets Manager', prompt: 'I need to retrieve specific secrets from AWS Secrets Manager.' },
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
}: SidebarContentProps) {
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
          hiddenInset lights and doubles as a grabbable drag strip. Lives
          here (not the rail) so the mobile drawer is covered too. */}
      {macDesktop && (
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

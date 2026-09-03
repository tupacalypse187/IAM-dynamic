import { useState, useEffect } from 'react'
import { ProvidersResponse } from '@/types/api'
import { useTheme } from './theme-provider'
import { Button } from './ui/button'
import { ScrollArea } from './ui/scroll-area'
import { Separator } from './ui/separator'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select'
import { Label } from './ui/label'
import { Skeleton } from './ui/skeleton'
import { AlertCircle, Monitor, Moon, RefreshCw, Sun, Settings } from 'lucide-react'

interface SidebarContentProps {
  config?: ProvidersResponse
  configLoading?: boolean
  configError?: boolean
  onRetryConfig?: () => void
  onRequestTextChange: (text: string) => void
  selectedProvider?: string
  onProviderChange?: (provider: string) => void
  selectedModel?: string
  onModelChange?: (model: string) => void
  onTemplateSelected?: () => void
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
 */
export function SidebarContent({
  config,
  configLoading = false,
  configError = false,
  onRetryConfig,
  onRequestTextChange,
  selectedProvider,
  onProviderChange,
  selectedModel,
  onModelChange,
  onTemplateSelected,
}: SidebarContentProps) {
  const { theme, setTheme } = useTheme()
  const [provider, setProvider] = useState(selectedProvider || config?.providers[0]?.id || 'gemini')
  const [model, setModel] = useState(selectedModel || '')

  // Sync provider with parent
  useEffect(() => {
    if (onProviderChange) {
      onProviderChange(provider)
    }
  }, [provider, onProviderChange])

  // Follow the parent's selection when it changes externally (e.g. after
  // the backend config loads and App sets the default provider). Including
  // `provider` here is safe: the setProvider below only fires when the
  // values differ, so the effect settles instead of looping.
  useEffect(() => {
    if (selectedProvider && selectedProvider !== provider) {
      setProvider(selectedProvider)
    }
  }, [selectedProvider, provider])

  // Sync model with parent
  useEffect(() => {
    if (onModelChange) {
      onModelChange(model)
    }
  }, [model, onModelChange])

  // Reset model to default when provider changes
  useEffect(() => {
    const providerData = config?.providers.find((p) => p.id === provider)
    if (providerData?.model) {
      setModel(providerData.model)
    }
  }, [provider, config?.providers])

  const selectedProviderData = config?.providers.find((p) => p.id === provider)

  const cycleTheme = () => {
    const currentIndex = themeCycle.indexOf(theme as 'system' | 'light' | 'dark')
    const nextTheme = themeCycle[(currentIndex + 1) % themeCycle.length]
    setTheme(nextTheme)
  }

  const ThemeIcon = themeIcons[theme as 'system' | 'light' | 'dark']
  const themeLabel = themeLabels[theme as 'system' | 'light' | 'dark']

  return (
    <div className="flex h-full flex-col">
      {/* Theme Toggle & Settings */}
      <div className="border-b border-sidebar-border p-4 space-y-4">
        <div className="flex items-center gap-2">
          <Settings className="h-4 w-4 text-sidebar-foreground/70" />
          <span className="text-sm font-semibold">Settings</span>
        </div>

        {/* Theme Toggle - cycle button */}
        <div className="flex items-center justify-between">
          <Label className="text-xs text-sidebar-foreground/70">Theme</Label>
          <Button
            variant="outline"
            size="sm"
            onClick={cycleTheme}
            className="h-9 w-9 p-0 border-sidebar-border bg-transparent text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
            aria-label={`Change theme (currently ${themeLabel})`}
          >
            <ThemeIcon className="h-4 w-4" />
          </Button>
        </div>

        {/* Provider / Model loading state */}
        {configLoading && (
          <div className="space-y-4" aria-label="Loading AI provider configuration">
            <div className="space-y-2">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-8 w-full" />
            </div>
            <div className="space-y-2">
              <Skeleton className="h-3 w-14" />
              <Skeleton className="h-8 w-full" />
            </div>
          </div>
        )}

        {/* Provider / Model error state with retry */}
        {configError && !configLoading && (
          <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-xs" role="alert">
            <div className="flex items-start gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 text-destructive" />
              <div className="space-y-2">
                <p className="text-sidebar-foreground">
                  Couldn't load AI providers. Check that the backend is running.
                </p>
                {onRetryConfig && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={onRetryConfig}
                    className="h-7 border-sidebar-border bg-transparent text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                  >
                    <RefreshCw className="h-3 w-3" />
                    Retry
                  </Button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* LLM Provider Selector */}
        {!configLoading && !configError && config && config.providers.length > 0 && (
          <div className="space-y-2">
            <Label htmlFor="provider-select" className="text-xs text-sidebar-foreground/70">
              AI Provider
            </Label>
            <Select value={provider} onValueChange={setProvider}>
              <SelectTrigger id="provider-select" className="h-9 border-sidebar-border bg-sidebar-accent/50">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {config.providers.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        {/* Model Selector */}
        {!configLoading && !configError && selectedProviderData && selectedProviderData.models.length > 0 && (
          <div className="space-y-2">
            <Label htmlFor="model-select" className="text-xs text-sidebar-foreground/70">
              Model
            </Label>
            <Select value={model} onValueChange={setModel}>
              <SelectTrigger id="model-select" className="h-9 border-sidebar-border bg-sidebar-accent/50">
                <SelectValue placeholder="Select model" />
              </SelectTrigger>
              <SelectContent>
                {selectedProviderData.models.map((m) => (
                  <SelectItem key={m.id} value={m.id}>
                    {m.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
      </div>

      {/* Quick Templates */}
      <ScrollArea className="flex-1">
        <div className="p-4 space-y-4">
          <div>
            <h3 className="mb-2 text-sm font-semibold">Quick Templates</h3>
            <div className="space-y-1">
              {templates.map((template) => (
                <button
                  key={template.id}
                  onClick={() => {
                    onRequestTextChange(template.prompt)
                    onTemplateSelected?.()
                  }}
                  className="w-full rounded-md px-3 py-2 text-left text-sm text-sidebar-foreground/85 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring"
                >
                  {template.name}
                </button>
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
    <aside className="hidden w-72 shrink-0 border-r border-sidebar-border bg-sidebar text-sidebar-foreground lg:block">
      <SidebarContent {...props} />
    </aside>
  )
}

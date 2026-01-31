import { useState, useEffect } from 'react'
import { ProvidersResponse } from '@/types/api'
import { useTheme } from './theme-provider'
import { Button } from './ui/button'
import { ScrollArea } from './ui/scroll-area'
import { Separator } from './ui/separator'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select'
import { Label } from './ui/label'
import { Monitor, Moon, Sun, Settings } from 'lucide-react'

interface SidebarProps {
  config?: ProvidersResponse
  onRequestTextChange: (text: string) => void
  selectedProvider?: string
  onProviderChange?: (provider: string) => void
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
const themeIcons = {
  system: Monitor,
  light: Sun,
  dark: Moon,
}

export default function Sidebar({ config, onRequestTextChange, selectedProvider, onProviderChange }: SidebarProps) {
  const { theme, setTheme } = useTheme()
  const [provider, setProvider] = useState(selectedProvider || config?.providers[0]?.id || 'gemini')

  // Update parent when provider changes
  useEffect(() => {
    if (onProviderChange) {
      onProviderChange(provider)
    }
  }, [provider, onProviderChange])

  const selectedProviderData = config?.providers.find(p => p.id === provider)

  const cycleTheme = () => {
    const currentIndex = themeCycle.indexOf(theme as 'system' | 'light' | 'dark')
    const nextTheme = themeCycle[(currentIndex + 1) % themeCycle.length]
    setTheme(nextTheme)
  }

  const ThemeIcon = themeIcons[theme as 'system' | 'light' | 'dark']

  return (
    <aside className="w-72 border-r bg-background">
      <div className="flex h-full flex-col">
        {/* Theme Toggle & Settings */}
        <div className="border-b p-4 space-y-4">
          <div className="flex items-center gap-2">
            <Settings className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-semibold">Settings</span>
          </div>

          {/* Theme Toggle - Modern cycle button */}
          <div className="flex items-center justify-between">
            <Label className="text-xs text-muted-foreground">Theme</Label>
            <Button
              variant="outline"
              size="sm"
              onClick={cycleTheme}
              className="h-9 w-9 p-0"
            >
              <ThemeIcon className="h-4 w-4" />
              <span className="sr-only">Toggle theme</span>
            </Button>
          </div>

          {/* LLM Provider Selector */}
          {config && config.providers.length > 0 && (
            <div className="space-y-2">
              <Label className="text-xs text-muted-foreground">AI Provider</Label>
              <Select value={provider} onValueChange={setProvider}>
                <SelectTrigger className="h-8">
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

          {/* Current Model Display */}
          {selectedProviderData && (
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Model</Label>
              <div className="text-sm font-mono bg-muted px-2 py-1 rounded">
                {selectedProviderData.model}
              </div>
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
                    onClick={() => onRequestTextChange(template.prompt)}
                    className="w-full rounded-md px-3 py-2 text-left text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
                  >
                    {template.name}
                  </button>
                ))}
              </div>
            </div>

            <Separator />

            {/* Configuration */}
            <div>
              <h3 className="mb-2 text-sm font-semibold">Account Info</h3>
              <div className="text-sm text-muted-foreground">
                Account: {config?.account_id || 'N/A'}
              </div>
            </div>
          </div>
        </ScrollArea>
      </div>
    </aside>
  )
}

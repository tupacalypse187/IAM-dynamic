import { Monitor, Moon, Play, Sun } from 'lucide-react'
import { useTheme } from '@/hooks/use-theme'
import { usePrefs } from '@/hooks/use-prefs'
import { launchTour } from '@/lib/tour'
import type { ProvidersResponse } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { ProviderSelects } from '@/components/provider-selects'
import { ProfileManager } from '@/components/profile-manager'
import { CatalogManager } from '@/components/catalog-manager'
import HelpSections from '@/components/help-sections'
import { Tip } from '@/components/tip'

export interface WindowDiagnostics {
  /** Preload bridge present (false in browsers). */
  bridge: boolean
  /** ?platform= value injected by the main process, if any. */
  urlPlatform: string | null
  /** Live navigator-based macOS detection result. */
  liveDetect: boolean
  /** Effective clearance actually applied to the layout. */
  effective: boolean
}

interface SettingsViewProps {
  appVersion: string | null
  backendUrl: string | null
  diagnostics: WindowDiagnostics
  isAdmin: boolean
  config?: ProvidersResponse
  configLoading?: boolean
  configError?: boolean
  onRetryConfig?: () => void
  selectedProvider: string
  onProviderChange: (provider: string) => void
  selectedModel: string
  onModelChange: (model: string) => void
}

const themes = [
  { id: 'system', label: 'System', icon: Monitor },
  { id: 'light', label: 'Light', icon: Sun },
  { id: 'dark', label: 'Dark', icon: Moon },
] as const

export default function SettingsView({
  appVersion,
  backendUrl,
  diagnostics,
  isAdmin,
  config,
  configLoading,
  configError,
  onRetryConfig,
  selectedProvider,
  onProviderChange,
  selectedModel,
  onModelChange,
}: SettingsViewProps) {
  const { theme, setTheme } = useTheme()
  const { prefs, updatePrefs } = usePrefs()

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">Settings</h2>
        <p className="text-muted-foreground">
          Display, AI provider defaults, the guided demo, help guides, and about.
        </p>
      </div>

      {/* Demo & display */}
      <Card>
        <CardHeader>
          <CardTitle>Demo &amp; display</CardTitle>
          <CardDescription>Theme, hover help, and the guided tour.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="space-y-2">
            <Label>Theme</Label>
            <div className="flex gap-2" role="group" aria-label="Theme">
              {themes.map((t) => {
                const Icon = t.icon
                const active = theme === t.id
                return (
                  <Tip key={t.id} label={`Use the ${t.label.toLowerCase()} theme`}>
                    <Button
                      variant={active ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setTheme(t.id)}
                      aria-pressed={active}
                    >
                      <Icon className="mr-1.5 h-4 w-4" aria-hidden="true" />
                      {t.label}
                    </Button>
                  </Tip>
                )
              })}
            </div>
          </div>

          <div className="flex items-center justify-between gap-4">
            <div className="space-y-0.5">
              <Label htmlFor="tooltips-switch">Hover tooltips</Label>
              <p className="text-xs text-muted-foreground">
                Explain buttons and controls on hover throughout the app.
              </p>
            </div>
            <Switch
              id="tooltips-switch"
              checked={prefs.tooltips}
              onCheckedChange={(checked) => updatePrefs({ tooltips: checked })}
              aria-label="Hover tooltips"
            />
          </div>

          <div className="flex items-center justify-between gap-4">
            <div className="space-y-0.5">
              <Label htmlFor="tour-autoplay-switch">Play demo on startup</Label>
              <p className="text-xs text-muted-foreground">
                First-run users get the 5-step guided tour automatically.
              </p>
            </div>
            <Switch
              id="tour-autoplay-switch"
              checked={prefs.tourAutoplay}
              onCheckedChange={(checked) => updatePrefs({ tourAutoplay: checked })}
              aria-label="Play demo on startup"
            />
          </div>

          <div>
            <Tip label="Replay the 5-step guided tour of requesting access">
              <Button variant="outline" onClick={launchTour}>
                <Play className="mr-1.5 h-4 w-4" aria-hidden="true" />
                Replay the demo tour
              </Button>
            </Tip>
          </div>
        </CardContent>
      </Card>

      {/* Profiles + catalog */}
      <ProfileManager />
      {isAdmin && <CatalogManager />}

      {/* AI provider */}
      <Card>
        <CardHeader>
          <CardTitle>AI provider fallback</CardTitle>
          <CardDescription>
            Server defaults used when no profile is active. Switching here applies to the next
            submission; prefer a profile above for your own key.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ProviderSelects
            config={config}
            configLoading={configLoading}
            configError={configError}
            onRetryConfig={onRetryConfig}
            selectedProvider={selectedProvider}
            onProviderChange={onProviderChange}
            selectedModel={selectedModel}
            onModelChange={onModelChange}
          />
          {config?.account_id && (
            <p className="mt-4 text-sm text-muted-foreground">
              AWS Account: <span className="break-all font-mono text-xs">{config.account_id}</span>
            </p>
          )}
        </CardContent>
      </Card>

      {/* Help & guides */}
      <div className="space-y-6">
        <div>
          <h3 className="text-lg font-semibold tracking-tight">Help &amp; guides</h3>
          <p className="text-sm text-muted-foreground">
            Shortcuts, how-tos, updates, and your local audit log.
          </p>
        </div>
        <HelpSections appVersion={appVersion} />
      </div>

      {/* About */}
      <Card>
        <CardHeader>
          <CardTitle>About</CardTitle>
          <CardDescription>
            Build and window diagnostics — screenshot this section if the traffic lights overlap anything.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="space-y-1 text-sm">
            <div className="flex gap-2">
              <dt className="text-muted-foreground">Version:</dt>
              <dd>{appVersion ? `v${appVersion}` : 'local build'}</dd>
            </div>
            {backendUrl && (
              <div className="flex gap-2">
                <dt className="text-muted-foreground">Backend:</dt>
                <dd className="break-all font-mono text-xs">{backendUrl}</dd>
              </div>
            )}
            <div className="flex gap-2">
              <dt className="text-muted-foreground">Desktop bridge:</dt>
              <dd>{diagnostics.bridge ? 'connected' : 'missing (browser or broken preload)'}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-muted-foreground">Injected platform:</dt>
              <dd className="font-mono text-xs">{diagnostics.urlPlatform ?? 'none (browser load)'}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-muted-foreground">Live mac detection:</dt>
              <dd>{diagnostics.liveDetect ? 'true' : 'false'}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-muted-foreground">Clearance applied:</dt>
              <dd>{diagnostics.effective ? 'true' : 'false'}</dd>
            </div>
          </dl>
        </CardContent>
      </Card>
    </div>
  )
}

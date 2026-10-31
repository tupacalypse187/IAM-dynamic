import { useEffect, useState } from 'react'
import { AlertCircle, RefreshCw } from 'lucide-react'
import type { ProvidersResponse } from '@/types/api'
import { Button } from './ui/button'
import { Label } from './ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select'
import { Skeleton } from './ui/skeleton'

interface ProviderSelectsProps {
  config?: ProvidersResponse
  configLoading?: boolean
  configError?: boolean
  onRetryConfig?: () => void
  selectedProvider: string
  onProviderChange?: (provider: string) => void
  selectedModel: string
  onModelChange?: (model: string) => void
}

/**
 * AI provider + model selectors with backend-config sync. Single home is
 * the Settings view; the submit form consumes the selection from App state.
 */
export function ProviderSelects({
  config,
  configLoading = false,
  configError = false,
  onRetryConfig,
  selectedProvider,
  onProviderChange,
  selectedModel,
  onModelChange,
}: ProviderSelectsProps) {
  const [provider, setProvider] = useState(selectedProvider || config?.providers[0]?.id || 'muse')
  const [model, setModel] = useState(selectedModel || '')

  // Sync provider with parent
  useEffect(() => {
    if (onProviderChange) {
      onProviderChange(provider)
    }
  }, [provider, onProviderChange])

  // Follow the parent's selection when it changes externally (e.g. after
  // the backend config loads). Including `provider` here is safe: the
  // setProvider below only fires when the values differ, so the effect
  // settles instead of looping.
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

  // Follow the parent's model selection when it changes externally
  useEffect(() => {
    if (selectedModel && selectedModel !== model) {
      setModel(selectedModel)
    }
  }, [selectedModel, model])

  // Reset model to default when provider changes
  useEffect(() => {
    const providerData = config?.providers.find((p) => p.id === provider)
    if (providerData?.model) {
      setModel(providerData.model)
    }
  }, [provider, config?.providers])

  const selectedProviderData = config?.providers.find((p) => p.id === provider)

  return (
    <div className="space-y-4">
      {configLoading && (
        <div className="space-y-4" aria-label="Loading AI provider configuration">
          <div className="space-y-2">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-9 w-full" />
          </div>
          <div className="space-y-2">
            <Skeleton className="h-3 w-14" />
            <Skeleton className="h-9 w-full" />
          </div>
        </div>
      )}

      {configError && !configLoading && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm" role="alert">
          <div className="flex items-start gap-2">
            <AlertCircle className="h-4 w-4 shrink-0 text-destructive" />
            <div className="space-y-2">
              <p>Couldn&apos;t load AI providers. Check that the backend is running.</p>
              {onRetryConfig && (
                <Button variant="outline" size="sm" onClick={onRetryConfig}>
                  <RefreshCw className="mr-1 h-3 w-3" />
                  Retry
                </Button>
              )}
            </div>
          </div>
        </div>
      )}

      {!configLoading && !configError && config && config.providers.length > 0 && (
        <div className="space-y-2">
          <Label htmlFor="provider-select">AI Provider</Label>
          <Select value={provider} onValueChange={setProvider}>
            <SelectTrigger id="provider-select">
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

      {!configLoading && !configError && selectedProviderData && selectedProviderData.models.length > 0 && (
        <div className="space-y-2">
          <Label htmlFor="model-select">Model</Label>
          <Select value={model} onValueChange={setModel}>
            <SelectTrigger id="model-select">
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
  )
}

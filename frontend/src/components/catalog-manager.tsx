import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { api } from '@/lib/api'
import { Button } from './ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card'
import { Label } from './ui/label'
import { Switch } from './ui/switch'

/**
 * Administrator control over which provider/model pairs exist for profiles.
 * Disabling a pair blocks new profiles and new evaluations with it.
 */
export function CatalogManager() {
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const catalogQuery = useQuery({ queryKey: ['catalog'], queryFn: api.listCatalog })

  const toggleMutation = useMutation({
    mutationFn: (input: { provider: string; model: string; enabled: boolean }) =>
      api.updateCatalog(input),
    onSuccess: () => {
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['catalog'] })
    },
    onError: (err: Error) => setError(err.message),
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>Provider catalog</CardTitle>
        <CardDescription>
          Which providers and models users may save profiles for. Disabling a pair blocks new
          profiles and new evaluations with it (existing requests are unaffected).
        </CardDescription>
      </CardHeader>
      <CardContent>
        {catalogQuery.isLoading && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading catalog…
          </p>
        )}
        {catalogQuery.isError && (
          <div>
            <p className="text-sm text-destructive">Could not load the catalog.</p>
            <Button variant="outline" size="sm" className="mt-2" onClick={() => catalogQuery.refetch()}>
              Retry
            </Button>
          </div>
        )}
        {catalogQuery.data && (
          <ul className="space-y-1">
            {catalogQuery.data.map((entry) => (
              <li
                key={`${entry.provider}/${entry.model}`}
                className="flex items-center gap-3 rounded-md border px-3 py-2"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">
                    {entry.display_name || entry.model}
                  </p>
                  <p className="truncate font-mono text-xs text-muted-foreground">
                    {entry.provider} · {entry.model}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Label
                    htmlFor={`catalog-${entry.provider}-${entry.model}`}
                    className="text-xs text-muted-foreground"
                  >
                    {entry.enabled ? 'Enabled' : 'Disabled'}
                  </Label>
                  <Switch
                    id={`catalog-${entry.provider}-${entry.model}`}
                    checked={entry.enabled}
                    disabled={toggleMutation.isPending}
                    onCheckedChange={(checked) =>
                      toggleMutation.mutate({
                        provider: entry.provider,
                        model: entry.model,
                        enabled: checked,
                      })
                    }
                    aria-label={`${entry.enabled ? 'Disable' : 'Enable'} ${entry.display_name || entry.model}`}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}
        {error && (
          <p className="mt-3 text-sm text-destructive" role="alert">
            {error}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

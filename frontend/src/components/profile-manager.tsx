import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, KeyRound, Loader2, Pencil, Plus, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import type { LlmProfile } from '@/types/api'
import { Button } from './ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card'
import { Input } from './ui/input'
import { Label } from './ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select'
import { Badge } from './ui/badge'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from './ui/alert-dialog'
import { Tip } from './tip'

/**
 * The user's saved LLM profiles. Keys are write-only: creation and
 * rotation send the key, every read shows only a last-4 hint.
 */
export function ProfileManager() {
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const [showAdd, setShowAdd] = useState(false)
  const [name, setName] = useState('')
  const [provider, setProvider] = useState('')
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editName, setEditName] = useState('')
  const [editKey, setEditKey] = useState('')

  const profilesQuery = useQuery({ queryKey: ['profiles'], queryFn: api.listProfiles })
  const catalogQuery = useQuery({ queryKey: ['catalog'], queryFn: api.listCatalog })
  const profiles = profilesQuery.data ?? []
  const enabledEntries = useMemo(
    () => (catalogQuery.data ?? []).filter((e) => e.enabled),
    [catalogQuery.data],
  )
  const providers = useMemo(
    () => [...new Set(enabledEntries.map((e) => e.provider))],
    [enabledEntries],
  )
  const modelsForProvider = useMemo(
    () => enabledEntries.filter((e) => e.provider === provider),
    [enabledEntries, provider],
  )

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['profiles'] })
  }

  const createMutation = useMutation({
    mutationFn: () => api.createProfile({ name: name.trim(), provider, model, api_key: apiKey }),
    onSuccess: () => {
      setError(null)
      setName('')
      setApiKey('')
      setShowAdd(false)
      invalidate()
    },
    onError: (err: Error) => setError(err.message),
  })

  const updateMutation = useMutation({
    mutationFn: (id: number) =>
      api.updateProfile(id, {
        ...(editName.trim() ? { name: editName.trim() } : {}),
        ...(editKey.trim() ? { api_key: editKey.trim() } : {}),
      }),
    onSuccess: () => {
      setError(null)
      setEditingId(null)
      setEditName('')
      setEditKey('')
      invalidate()
    },
    onError: (err: Error) => setError(err.message),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteProfile(id),
    onSuccess: () => {
      setError(null)
      invalidate()
    },
    onError: (err: Error) => setError(err.message),
  })

  const activateMutation = useMutation({
    mutationFn: (id: number) => api.activateProfile(id),
    onSuccess: () => {
      setError(null)
      invalidate()
    },
    onError: (err: Error) => setError(err.message),
  })

  const busy = createMutation.isPending || updateMutation.isPending

  const startEdit = (profile: LlmProfile) => {
    setEditingId(profile.id)
    setEditName(profile.name)
    setEditKey('')
    setError(null)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>LLM profiles</CardTitle>
        <CardDescription>
          Your own provider keys, saved per profile. Keys are encrypted on the server and never
          shown back — only a last-4 hint. The active profile evaluates new requests.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {profilesQuery.isLoading && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading profiles…
          </p>
        )}
        {profilesQuery.isError && (
          <div>
            <p className="text-sm text-destructive">Could not load profiles.</p>
            <Button variant="outline" size="sm" className="mt-2" onClick={() => profilesQuery.refetch()}>
              Retry
            </Button>
          </div>
        )}

        {profiles.length > 0 && (
          <ul className="space-y-2">
            {profiles.map((profile) => (
              <li key={profile.id} className="rounded-md border p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{profile.name}</span>
                  {profile.active && <Badge className="bg-success/15 text-success">Active</Badge>}
                  <span className="text-xs text-muted-foreground">
                    {profile.provider} · {profile.model} · key …{profile.key_hint || '????'}
                  </span>
                  <span className="ml-auto flex gap-1">
                    {!profile.active && (
                      <Tip label="Evaluate new requests with this profile">
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={activateMutation.isPending}
                          onClick={() => activateMutation.mutate(profile.id)}
                        >
                          <Check className="mr-1 h-3 w-3" />
                          Use
                        </Button>
                      </Tip>
                    )}
                    <Tip label="Rename or replace this profile's key">
                      <Button variant="ghost" size="sm" onClick={() => startEdit(profile)}>
                        <Pencil className="h-3 w-3" aria-label="Edit profile" />
                      </Button>
                    </Tip>
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button variant="ghost" size="sm" aria-label={`Delete profile ${profile.name}`}>
                          <Trash2 className="h-3 w-3 text-destructive" />
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Delete “{profile.name}”?</AlertDialogTitle>
                          <AlertDialogDescription>
                            The saved key is destroyed. Requests already evaluated keep working;
                            new evaluations fall back to another profile or server defaults.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction onClick={() => deleteMutation.mutate(profile.id)}>
                            Delete profile
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </span>
                </div>
                {editingId === profile.id && (
                  <div className="mt-3 grid gap-3 border-t pt-3 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <Label htmlFor={`profile-name-${profile.id}`}>Name</Label>
                      <Input
                        id={`profile-name-${profile.id}`}
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        maxLength={64}
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor={`profile-key-${profile.id}`}>New key (leave blank to keep)</Label>
                      <Input
                        id={`profile-key-${profile.id}`}
                        type="password"
                        value={editKey}
                        onChange={(e) => setEditKey(e.target.value)}
                        placeholder="••••••••"
                        autoComplete="off"
                      />
                    </div>
                    <div className="flex gap-2 sm:col-span-2">
                      <Button
                        size="sm"
                        disabled={busy || (!editName.trim() && !editKey.trim())}
                        onClick={() => updateMutation.mutate(profile.id)}
                      >
                        {updateMutation.isPending ? (
                          <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                        ) : null}
                        Save
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => setEditingId(null)}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}

        {!showAdd ? (
          <Tip label="Save a provider key under a memorable name">
            <Button variant="outline" onClick={() => setShowAdd(true)}>
              <Plus className="mr-1.5 h-4 w-4" />
              Add profile
            </Button>
          </Tip>
        ) : (
          <div className="grid gap-3 rounded-md border p-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="new-profile-name">Name</Label>
              <Input
                id="new-profile-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. work-muse"
                maxLength={64}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="new-profile-provider">Provider</Label>
              <Select
                value={provider}
                onValueChange={(v) => {
                  setProvider(v)
                  setModel('')
                }}
              >
                <SelectTrigger id="new-profile-provider">
                  <SelectValue placeholder="Select provider" />
                </SelectTrigger>
                <SelectContent>
                  {providers.map((p) => (
                    <SelectItem key={p} value={p}>
                      {p}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="new-profile-model">Model</Label>
              <Select value={model} onValueChange={setModel} disabled={!provider}>
                <SelectTrigger id="new-profile-model">
                  <SelectValue placeholder="Select model" />
                </SelectTrigger>
                <SelectContent>
                  {modelsForProvider.map((m) => (
                    <SelectItem key={m.model} value={m.model}>
                      {m.display_name || m.model}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="new-profile-key">API key</Label>
              <Input
                id="new-profile-key"
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Stored encrypted, never shown again"
                autoComplete="off"
              />
            </div>
            <div className="flex gap-2 sm:col-span-2">
              <Button
                size="sm"
                disabled={busy || !name.trim() || !provider || !model || !apiKey.trim()}
                onClick={() => createMutation.mutate()}
              >
                {createMutation.isPending ? (
                  <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                ) : (
                  <KeyRound className="mr-1 h-3 w-3" />
                )}
                Save profile
              </Button>
              <Button variant="outline" size="sm" onClick={() => setShowAdd(false)}>
                Cancel
              </Button>
            </div>
          </div>
        )}

        {error && (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

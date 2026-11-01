import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Loader2, ShieldCheck, User } from 'lucide-react'
import { api } from '@/lib/api'
import { groupByBatch, requestExcerpt, riskBadgeClass, riskLabel, statusStyles } from '@/lib/requests'
import type { AccessRequest, RequestStatus } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { EnvBadge } from '@/components/env-badge'
import { Tip } from '@/components/tip'

interface ReviewDashboardViewProps {
  onOpenRequest: (request: AccessRequest) => void
}

type QueueFilter = RequestStatus | 'all'

const FILTERS: { value: QueueFilter; label: string }[] = [
  { value: 'pending_review', label: 'Needs review' },
  { value: 'all', label: 'All' },
  { value: 'approved', label: 'Approved' },
  { value: 'changes_requested', label: 'Sent back' },
  { value: 'denied', label: 'Denied' },
  { value: 'activated', label: 'Active' },
  { value: 'cancelled', label: 'Cancelled' },
]

function timeAgo(iso: string): string {
  const seconds = Math.max(0, Math.floor((Date.now() - Date.parse(iso)) / 1000))
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

export default function ReviewDashboardView({ onOpenRequest }: ReviewDashboardViewProps) {
  const [filter, setFilter] = useState<QueueFilter>('pending_review')
  const [auditError, setAuditError] = useState<string | null>(null)

  const queueQuery = useQuery({
    queryKey: ['requests', 'queue', filter],
    queryFn: () => api.listRequests(filter === 'all' ? undefined : { status: filter }),
  })

  const auditQuery = useQuery({
    queryKey: ['audit', 'recent'],
    queryFn: () => api.readAudit({ limit: 100 }),
  })

  const openAuditRequest = async (id: number) => {
    setAuditError(null)
    try {
      onOpenRequest(await api.getRequest(id))
    } catch (err) {
      setAuditError(err instanceof Error ? err.message : 'Could not open that request.')
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h2 className="flex items-center gap-2 text-2xl font-bold tracking-tight sm:text-3xl">
          <ShieldCheck className="h-7 w-7 text-primary" aria-hidden="true" />
          Review Dashboard
        </h2>
        <p className="text-muted-foreground">
          Every request, who asked for it, and the evaluated policy — approve, deny, or send back
          with feedback.
        </p>
      </div>

      <Tabs defaultValue="queue">
        <TabsList>
          <TabsTrigger value="queue">
            Queue
            {queueQuery.data && filter === 'pending_review' && queueQuery.data.length > 0 && (
              <Badge className="ml-2 bg-warning/20 text-warning">{queueQuery.data.length}</Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="audit">Audit trail</TabsTrigger>
        </TabsList>

        <TabsContent value="queue" className="mt-4 space-y-4">
          <div className="flex flex-wrap gap-2" role="group" aria-label="Filter requests">
            {FILTERS.map((f) => (
              <Tip key={f.value} label={`Show ${f.label.toLowerCase()} requests`}>
                <Button
                  variant={filter === f.value ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setFilter(f.value)}
                >
                  {f.label}
                </Button>
              </Tip>
            ))}
          </div>

          {queueQuery.isLoading && (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading requests…
            </p>
          )}
          {queueQuery.isError && (
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-destructive">Could not load the review queue.</p>
                <Button variant="outline" size="sm" className="mt-3" onClick={() => queueQuery.refetch()}>
                  Retry
                </Button>
              </CardContent>
            </Card>
          )}
          {queueQuery.data && queueQuery.data.length === 0 && (
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">
                  {filter === 'pending_review'
                    ? 'Queue is clear — nothing waiting for review.'
                    : 'No requests with this status.'}
                </p>
              </CardContent>
            </Card>
          )}
          {queueQuery.data && queueQuery.data.length > 0 && (
            <Card>
              <CardContent className="pt-6">
                <ul className="space-y-3">
                  {groupByBatch(queueQuery.data).map((group) => (
                    <li key={group.batchId} className="space-y-2">
                      {group.rows.length > 1 && (
                        <p className="text-xs font-medium text-muted-foreground">
                          Batch #{group.batchId} · {group.rows.length} grants from {group.rows[0].requester}
                        </p>
                      )}
                      {group.rows.map((request) => {
                        const status = statusStyles[request.status]
                        return (
                          <button
                            key={request.id}
                            type="button"
                            onClick={() => onOpenRequest(request)}
                            className="block w-full rounded-md border p-3 text-left hover:border-primary/50 hover:bg-muted/50"
                            aria-label={`Review request ${request.id} from ${request.requester}`}
                          >
                            <span className="flex flex-wrap items-center gap-2">
                              <span className="font-medium">#{request.id}</span>
                              <EnvBadge environment={request.environment} />
                              <Badge className={status.badge}>{status.label}</Badge>
                              <Badge className={riskBadgeClass[request.risk] ?? riskBadgeClass.medium}>
                                {riskLabel[request.risk] ?? riskLabel.medium}
                              </Badge>
                              {request.revision > 1 && (
                                <Badge variant="outline">rev {request.revision}</Badge>
                              )}
                              <span className="ml-auto text-xs text-muted-foreground">
                                {timeAgo(request.created_at)}
                              </span>
                            </span>
                            <span className="mt-1 block truncate text-sm text-muted-foreground">
                              {requestExcerpt(request.request_text)}
                            </span>
                            <span className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
                              <User className="h-3 w-3" aria-hidden="true" />
                              {request.requester}
                              {request.reviewer && (
                                <span>
                                  · reviewed by <span className="font-medium">{request.reviewer}</span>
                                </span>
                              )}
                            </span>
                          </button>
                        )
                      })}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="audit" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>Audit trail</CardTitle>
              <CardDescription>
                Newest first, from the append-only server log. Select a request to open it.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {auditQuery.isLoading && (
                <p className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" /> Loading audit trail…
                </p>
              )}
              {auditQuery.isError && (
                <div>
                  <p className="text-sm text-destructive">Could not load the audit trail.</p>
                  <Button variant="outline" size="sm" className="mt-3" onClick={() => auditQuery.refetch()}>
                    Retry
                  </Button>
                </div>
              )}
              {auditError && (
                <p className="text-sm text-destructive" role="alert">{auditError}</p>
              )}
              {auditQuery.data && auditQuery.data.length === 0 && (
                <p className="text-sm text-muted-foreground">No audit events recorded yet.</p>
              )}
              {auditQuery.data && auditQuery.data.length > 0 && (
                <ol className="space-y-2">
                  {auditQuery.data.map((event, i) => (
                    <li key={i} className="rounded-md border p-3 text-sm">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="outline">{event.event.replace(/_/g, ' ')}</Badge>
                        {event.request_id != null ? (
                          <button
                            type="button"
                            className="font-medium text-primary hover:underline"
                            onClick={() => openAuditRequest(event.request_id as number)}
                          >
                            #{event.request_id}
                          </button>
                        ) : (
                          <span className="text-xs text-muted-foreground">account event</span>
                        )}
                        <span className="font-medium">{event.actor}</span>
                        <span className="text-muted-foreground">({event.actor_role})</span>
                        <span className="ml-auto text-xs text-muted-foreground">
                          {timeAgo(event.ts)}
                        </span>
                      </div>
                      {(event.from_status || event.to_status) && (
                        <p className="mt-1 text-xs text-muted-foreground">
                          {event.from_status ?? '—'} → {event.to_status ?? '—'}
                        </p>
                      )}
                    </li>
                  ))}
                </ol>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

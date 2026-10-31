import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Loader2, Copy, FileEdit, Plus, Radio } from 'lucide-react'
import { api } from '@/lib/api'
import { isLiveSession, requestExcerpt, reviewerDisplay, riskBadgeClass, riskLabel, statusStyles } from '@/lib/requests'
import type { AccessRequest } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tip } from '@/components/tip'

interface MyRequestsViewProps {
  onNewRequest: () => void
  onOpenRequest: (request: AccessRequest) => void
  /** Prefill the submit form; edit=true focuses it for changes. */
  onCloneRequest: (request: AccessRequest, edit: boolean) => void
}

function RequestRow({
  request,
  onOpen,
  onClone,
}: {
  request: AccessRequest
  onOpen: (request: AccessRequest) => void
  onClone: (edit: boolean) => void
}) {
  const status = statusStyles[request.status]
  return (
    <li className="flex flex-col gap-2 rounded-md border p-3 sm:flex-row sm:items-center">
      <button
        type="button"
        onClick={() => onOpen(request)}
        className="min-w-0 flex-1 text-left"
        aria-label={`Open request ${request.id}`}
      >
        <span className="flex flex-wrap items-center gap-2">
          <span className="font-medium">#{request.id}</span>
          <Badge className={status.badge}>{status.label}</Badge>
          <Badge className={riskBadgeClass[request.risk] ?? riskBadgeClass.medium}>
            {riskLabel[request.risk] ?? riskLabel.medium}
          </Badge>
          {request.revision > 1 && <Badge variant="outline">rev {request.revision}</Badge>}
        </span>
        <span className="mt-1 block truncate text-sm text-muted-foreground">
          {requestExcerpt(request.request_text)}
        </span>
        <span className="mt-1 block text-xs text-muted-foreground">
          Reviewed by {reviewerDisplay(request)}
        </span>
      </button>
      <span className="flex shrink-0 gap-2">
        <Tip label="Submit this exact request again as a new request">
          <Button variant="outline" size="sm" onClick={() => onClone(false)}>
            <Copy className="mr-1 h-3 w-3" />
            Clone
          </Button>
        </Tip>
        <Tip label="Copy this request into the submit form for editing">
          <Button variant="outline" size="sm" onClick={() => onClone(true)}>
            <FileEdit className="mr-1 h-3 w-3" />
            Clone &amp; edit
          </Button>
        </Tip>
      </span>
    </li>
  )
}

export default function MyRequestsView({ onNewRequest, onOpenRequest, onCloneRequest }: MyRequestsViewProps) {
  const query = useQuery({
    queryKey: ['requests', 'mine'],
    queryFn: () => api.listRequests({ mine: true }),
  })

  const { live, open, recent } = useMemo(() => {
    const all = query.data ?? []
    return {
      live: all.filter((r) => isLiveSession(r)),
      open: all.filter(
        (r) => r.status === 'pending_review' || r.status === 'changes_requested' || r.status === 'approved',
      ),
      recent: all.slice(0, 10),
    }
  }, [query.data])

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">My Requests</h2>
          <p className="text-muted-foreground">
            Track your access requests — live sessions, open reviews, and history.
          </p>
        </div>
        <Tip label="Describe a new access need">
          <Button onClick={onNewRequest}>
            <Plus className="mr-1 h-4 w-4" />
            New request
          </Button>
        </Tip>
      </div>

      {query.isLoading && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading your requests…
        </p>
      )}
      {query.isError && (
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-destructive">Could not load your requests.</p>
            <Button variant="outline" size="sm" className="mt-3" onClick={() => query.refetch()}>
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {query.data && (
        <>
          {live.length > 0 && (
            <Card className="border-l-4 border-l-primary">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Radio className="h-5 w-5 text-primary" aria-hidden="true" />
                  Live sessions
                </CardTitle>
                <CardDescription>Credentials are active right now.</CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {live.map((request) => (
                    <RequestRow
                      key={request.id}
                      request={request}
                      onOpen={onOpenRequest}
                      onClone={(edit) => onCloneRequest(request, edit)}
                    />
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Open requests</CardTitle>
              <CardDescription>Waiting on review, sent back, or approved and ready to activate.</CardDescription>
            </CardHeader>
            <CardContent>
              {open.length === 0 ? (
                <p className="text-sm text-muted-foreground">Nothing open — submit a request to get started.</p>
              ) : (
                <ul className="space-y-2">
                  {open.map((request) => (
                    <RequestRow
                      key={request.id}
                      request={request}
                      onOpen={onOpenRequest}
                      onClone={(edit) => onCloneRequest(request, edit)}
                    />
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Last 10 requests</CardTitle>
              <CardDescription>Clone any prior request to resubmit it, or clone &amp; edit to adjust it first.</CardDescription>
            </CardHeader>
            <CardContent>
              {recent.length === 0 ? (
                <p className="text-sm text-muted-foreground">No requests yet.</p>
              ) : (
                <ul className="space-y-2">
                  {recent.map((request) => (
                    <RequestRow
                      key={request.id}
                      request={request}
                      onOpen={onOpenRequest}
                      onClone={(edit) => onCloneRequest(request, edit)}
                    />
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}

import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Copy, FileEdit, Plus, Search, Undo2 } from 'lucide-react'
import { api } from '@/lib/api'
import {
  groupByBatch,
  isLiveSession,
  requestBucket,
  requestExcerpt,
  reviewerDisplay,
  riskBadgeClass,
  riskLabel,
  statusStyles,
  type RequestBucket,
} from '@/lib/requests'
import { formatRequestRef, matchesRequestQuery } from '@/lib/request-refs'
import type { AccessRequest } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { EnvBadge } from '@/components/env-badge'
import { Tip } from '@/components/tip'
import { useToast } from '@/hooks/use-toast'

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
  part,
  total,
  withdrawable,
  withdrawing,
  onWithdraw,
}: {
  request: AccessRequest
  onOpen: (request: AccessRequest) => void
  onClone: (edit: boolean) => void
  part?: number
  total?: number
  withdrawable?: boolean
  withdrawing?: boolean
  onWithdraw?: (request: AccessRequest) => void
}) {
  const [confirming, setConfirming] = useState(false)
  const status = statusStyles[request.status]
  const showPart = total != null && total > 1 && part != null
  return (
    <li className="flex flex-col gap-2 rounded-md border p-3 sm:flex-row sm:items-center">
      <button
        type="button"
        onClick={() => onOpen(request)}
        className="min-w-0 flex-1 text-left"
        aria-label={`Open request ${formatRequestRef(request.id)}`}
      >
        <span className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-sm font-medium">{formatRequestRef(request.id)}</span>
          {showPart && (
            <Badge variant="outline">
              Part {part} of {total}
            </Badge>
          )}
          <EnvBadge environment={request.environment} />
          <Badge className={status.badge}>{status.label}</Badge>
          <Badge className={riskBadgeClass[request.risk] ?? riskBadgeClass.medium}>
            {riskLabel[request.risk] ?? riskLabel.medium}
          </Badge>
          {isLiveSession(request) && (
            <Badge className="bg-primary/15 text-primary">Live now</Badge>
          )}
          {request.revision > 1 && <Badge variant="outline">rev {request.revision}</Badge>}
        </span>
        {request.label && (
          <span className="mt-1 block truncate text-sm font-medium">
            {request.label}
          </span>
        )}
        <span className="mt-1 block truncate text-sm text-muted-foreground">
          {requestExcerpt(request.request_text)}
        </span>
        <span className="mt-1 block text-xs text-muted-foreground">
          Reviewed by {reviewerDisplay(request)}
        </span>
      </button>
      <span className="flex shrink-0 gap-2">
        {withdrawable &&
          (confirming ? (
            <>
              <Button
                variant="destructive"
                size="sm"
                disabled={withdrawing}
                onClick={() => {
                  onWithdraw?.(request)
                  setConfirming(false)
                }}
              >
                {withdrawing ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : null}
                Confirm withdraw
              </Button>
              <Button variant="ghost" size="sm" disabled={withdrawing} onClick={() => setConfirming(false)}>
                Keep
              </Button>
            </>
          ) : (
            <Tip label="Withdraw this request (discards open requests, cancels active grants)">
              <Button variant="outline" size="sm" onClick={() => setConfirming(true)}>
                <Undo2 className="mr-1 h-3 w-3" />
                Withdraw
              </Button>
            </Tip>
          ))}
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
  const [search, setSearch] = useState('')
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const query = useQuery({
    queryKey: ['requests', 'mine'],
    queryFn: () => api.listRequests({ mine: true }),
  })

  // Withdraw from the summary: open rows are discarded, active grants are
  // cancelled (activated rows can no longer be discarded server-side).
  const withdrawMutation = useMutation({
    mutationFn: (request: AccessRequest) =>
      request.status === 'activated' ? api.cancelRequest(request.id) : api.discardRequest(request.id),
    onSuccess: (_updated, request) => {
      queryClient.invalidateQueries({ queryKey: ['requests'] })
      toast({
        title: `Withdrawn ${formatRequestRef(request.id)}`,
        description:
          request.status === 'activated' ? 'The active grant was cancelled.' : 'The request was withdrawn.',
      })
    },
    onError: (err: Error) =>
      toast({ title: 'Withdraw failed', description: err.message, variant: 'destructive' }),
  })

  const { open, active, expired, recent, matched, total } = useMemo(() => {
    const all = (query.data ?? []).filter((r) => matchesRequestQuery(r, search))
    const byBucket = (bucket: RequestBucket) =>
      groupByBatch(all.filter((r) => requestBucket(r) === bucket))
    return {
      open: byBucket('open'),
      active: byBucket('active'),
      expired: byBucket('expired'),
      recent: groupByBatch(all.slice(0, 10)),
      matched: all.length,
      total: (query.data ?? []).length,
    }
  }, [query.data, search])

  const renderGroup = (
    group: { batchId: number; rows: AccessRequest[] },
    opts?: { withdraw?: boolean },
  ) => (
    <li key={group.batchId} className="space-y-2">
      {group.rows.length > 1 && (
        <p className="text-xs font-medium text-muted-foreground">
          Split from one request · Batch #{group.batchId} · {group.rows.length} parts — low-risk parts activate now, the rest wait for review.
        </p>
      )}
      <ul className="space-y-2">
        {group.rows.map((request, i) => (
          <RequestRow
            key={request.id}
            request={request}
            onOpen={onOpenRequest}
            onClone={(edit) => onCloneRequest(request, edit)}
            part={i + 1}
            total={group.rows.length}
            withdrawable={opts?.withdraw}
            withdrawing={withdrawMutation.isPending && withdrawMutation.variables?.id === request.id}
            onWithdraw={(r) => withdrawMutation.mutate(r)}
          />
        ))}
      </ul>
    </li>
  )

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">My Requests</h2>
          <p className="text-muted-foreground">
            Track your access requests — open reviews, active grants, and history.
          </p>
        </div>
        <Tip label="Describe a new access need">
          <Button onClick={onNewRequest}>
            <Plus className="mr-1 h-4 w-4" />
            New request
          </Button>
        </Tip>
      </div>

      <div className="relative max-w-sm">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search req-00001 or text…"
          aria-label="Search my requests"
          className="pl-9"
        />
      </div>
      {search.trim() !== '' && query.data && (
        <p className="-mt-3 text-xs text-muted-foreground" role="status">
          {matched === 0
            ? `No matches for “${search.trim()}” in ${total} requests.`
            : `Showing ${matched} of ${total} requests matching “${search.trim()}”.`}
        </p>
      )}

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
          <Card>
            <CardHeader>
              <CardTitle>Open</CardTitle>
              <CardDescription>Waiting on a reviewer, or sent back for your changes.</CardDescription>
            </CardHeader>
            <CardContent>
              {open.length === 0 ? (
                <p className="text-sm text-muted-foreground">Nothing waiting — submit a request to get started.</p>
              ) : (
                <ul className="space-y-2">
                  {open.map((group) => renderGroup(group, { withdraw: true }))}
                </ul>
              )}
            </CardContent>
          </Card>

          <Card className="border-l-4 border-l-primary">
            <CardHeader>
              <CardTitle>Active</CardTitle>
              <CardDescription>Approved and usable — activate a grant when you need it. Live sessions are marked.</CardDescription>
            </CardHeader>
            <CardContent>
              {active.length === 0 ? (
                <p className="text-sm text-muted-foreground">No active grants — approved requests land here.</p>
              ) : (
                <ul className="space-y-2">
                  {active.map((group) => renderGroup(group, { withdraw: true }))}
                </ul>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Expired</CardTitle>
              <CardDescription>Lapsed, denied, discarded, or cancelled — read-only history.</CardDescription>
            </CardHeader>
            <CardContent>
              {expired.length === 0 ? (
                <p className="text-sm text-muted-foreground">Nothing expired or closed yet.</p>
              ) : (
                <ul className="space-y-2">
                  {expired.map((group) => renderGroup(group))}
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
                  {recent.map((group) => renderGroup(group))}
                </ul>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}

import { Suspense, lazy, useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  Loader2,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  ShieldAlert,
  Wand2,
  User,
  Undo2,
  Rocket,
  RotateCcw,
  Ban,
} from 'lucide-react'
import { usePolicyAgent } from '@/hooks/use-policy-agent'
import { api } from '@/lib/api'
import { reviewerDisplay, riskBadgeClass, riskLabel, statusStyles } from '@/lib/requests'
import type { AccessRequest, Credentials, ReviewDecision } from '@/types/api'
import { envOf } from '@/types/api'
import type { GuardrailFinding } from '@/types/desktop'
import { Button } from '@/components/ui/button'
import { Tip } from '@/components/tip'
import { EnvBadge } from '@/components/env-badge'
import { CopyButton } from '@/components/copy-button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
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
} from '@/components/ui/alert-dialog'

interface RequestDetailViewProps {
  request: AccessRequest
  isAdmin: boolean
  isOwner: boolean
  /** Local guardrail findings (desktop submit path; empty otherwise). */
  findings?: GuardrailFinding[]
  /** Plain-language grant summary (desktop submit path; null otherwise). */
  summary?: string | null
  onBack: () => void
  onChanged: (updated: AccessRequest) => void
  onCredentialsIssued: (credentials: Credentials) => void
  /** Owner edits a sent-back request in the submit form. */
  onResubmit: (request: AccessRequest) => void
  /** Owner reads denial feedback + AI guidance. */
  onShowGuidance: (request: AccessRequest) => void
  onApplySuggestion?: (suggestion: string) => void
}

// Static class maps — Tailwind's JIT scanner must see full class names,
// so risk colors can never be assembled at runtime.
const riskConfig = {
  low: { iconBg: 'bg-success', border: 'border-l-success', label: 'Low Risk', icon: CheckCircle2 },
  medium: { iconBg: 'bg-warning', border: 'border-l-warning', label: 'Medium Risk', icon: AlertTriangle },
  high: { iconBg: 'bg-orange-600', border: 'border-l-orange-600', label: 'High Risk', icon: AlertTriangle },
  critical: { iconBg: 'bg-destructive', border: 'border-l-destructive', label: 'Critical Risk', icon: AlertCircle },
} as const

const findingStyles = {
  critical: { badge: 'bg-destructive text-destructive-foreground', label: 'Critical' },
  high: { badge: 'bg-orange-600 text-white', label: 'High' },
  medium: { badge: 'bg-warning text-warning-foreground', label: 'Medium' },
  low: { badge: 'bg-success text-success-foreground', label: 'Low' },
} as const

const PolicyJsonViewer = lazy(() =>
  import('@/components/policy-editor').then((m) => ({ default: m.PolicyJsonViewer })),
)

function EditorFallback() {
  return (
    <div
      className="flex h-[420px] items-center justify-center rounded-md bg-muted text-sm text-muted-foreground"
      role="status"
    >
      <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
      Loading policy editor…
    </div>
  )
}

/** Lines containing IAM wildcards get editor warning decorations. */
function wildcardLineNumbers(json: string): number[] {
  const lines: number[] = []
  json.split('\n').forEach((line, i) => {
    if (/"[^"]*\*[^"]*"\s*[:,]/.test(line)) lines.push(i + 1)
  })
  return lines
}

function formatTime(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

export default function RequestDetailView({
  request,
  isAdmin,
  isOwner,
  findings = [],
  summary = null,
  onBack,
  onChanged,
  onCredentialsIssued,
  onResubmit,
  onShowGuidance,
  onApplySuggestion,
}: RequestDetailViewProps) {
  const [feedback, setFeedback] = useState('')
  const [error, setError] = useState<string | null>(null)
  const agent = usePolicyAgent()

  const policyJson = useMemo(() => JSON.stringify(request.policy, null, 2), [request.policy])
  const riskyLines = useMemo(() => wildcardLineNumbers(policyJson), [policyJson])

  const risk = riskConfig[request.risk] ?? riskConfig.medium
  const RiskIcon = risk.icon
  const status = statusStyles[request.status]

  // Admins see the audit trail for this request; owners see reviewer + feedback inline.
  const auditQuery = useQuery({
    queryKey: ['audit', request.id],
    queryFn: () => api.readAudit({ request_id: request.id, limit: 50 }),
    enabled: isAdmin,
  })

  const reviewMutation = useMutation({
    mutationFn: (input: { decision: ReviewDecision; feedback?: string }) =>
      api.reviewRequest(request.id, input),
    onSuccess: (updated, input) => {
      setError(null)
      setFeedback('')
      agent.track('request_reviewed', `Request #${request.id} ${input.decision}`, {
        requestId: request.id,
        decision: input.decision,
      })
      onChanged(updated)
    },
    onError: (err: Error) => setError(err.message),
  })

  const discardMutation = useMutation({
    mutationFn: () => api.discardRequest(request.id),
    onSuccess: (updated) => {
      setError(null)
      agent.track('request_reviewed', `Request #${request.id} withdrawn`, {
        requestId: request.id,
        decision: 'discarded',
      })
      onChanged(updated)
    },
    onError: (err: Error) => setError(err.message),
  })

  const cancelMutation = useMutation({
    mutationFn: () => api.cancelRequest(request.id),
    onSuccess: (updated) => {
      setError(null)
      agent.track('request_reviewed', `Request #${request.id} grant cancelled`, {
        requestId: request.id,
        decision: 'cancelled',
      })
      onChanged(updated)
    },
    onError: (err: Error) => setError(err.message),
  })

  const activateMutation = useMutation({
    mutationFn: () => agent.activate(request.id),
    onSuccess: (creds) => {
      setError(null)
      onCredentialsIssued(creds)
    },
    onError: (err: Error) => setError(err.message),
  })

  const busy = reviewMutation.isPending || discardMutation.isPending || activateMutation.isPending || cancelMutation.isPending

  const handleReview = (decision: ReviewDecision) => {
    if ((decision === 'deny' || decision === 'changes_requested') && !feedback.trim()) {
      setError('Feedback is required so the requester knows what to change.')
      return
    }
    reviewMutation.mutate({ decision, feedback: feedback.trim() || undefined })
  }

  const showAdminActions = isAdmin && request.status === 'pending_review'
  const reactivatable = envOf(request.environment) === 'dev'
  const showOwnerActivation =
    isOwner && (request.status === 'approved' || (request.status === 'activated' && reactivatable))
  const canDiscard =
    (isOwner || isAdmin) &&
    (request.status === 'pending_review' ||
      request.status === 'approved' ||
      request.status === 'changes_requested')
  const canCancel =
    (isOwner || isAdmin) &&
    (request.status === 'approved' || request.status === 'activated')

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* Header */}
      <div>
        <Button variant="ghost" onClick={onBack} className="mb-2">
          ← Back
        </Button>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
            Request #{request.id}
          </h2>
          <EnvBadge environment={request.environment} />
          <Badge className={status.badge}>{status.label}</Badge>
          <Badge className={riskBadgeClass[request.risk] ?? riskBadgeClass.medium}>
            {riskLabel[request.risk] ?? riskLabel.medium}
          </Badge>
          {request.revision > 1 && (
            <Badge variant="outline">Revision {request.revision}</Badge>
          )}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <User className="h-3.5 w-3.5" aria-hidden="true" />
            Requested by <span className="font-medium text-foreground">{request.requester}</span>
          </span>
          <span>
            Reviewed by{' '}
            <span className="font-medium text-foreground">{reviewerDisplay(request)}</span>
          </span>
          <span>Submitted {formatTime(request.created_at)}</span>
          {request.decided_at && <span>Decided {formatTime(request.decided_at)}</span>}
          {request.grant_expires_at && (request.status === 'approved' || request.status === 'activated') && (
            <span>Grant window ends {formatTime(request.grant_expires_at)}</span>
          )}
        </div>
      </div>

      {/* Original request */}
      <Card className="shadow-card">
        <CardHeader>
          <CardTitle>What was asked</CardTitle>
          <CardDescription>
            {request.provider}
            {request.model ? ` · ${request.model}` : ''} · {request.duration}h session
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="whitespace-pre-wrap text-sm">{request.request_text}</p>
        </CardContent>
      </Card>

      {/* Risk */}
      <Card className={`border-l-4 ${risk.border} shadow-card`}>
        <CardContent className="pt-6">
          <div className="flex flex-wrap items-center gap-3">
            <div className={`rounded-full p-2 ${risk.iconBg}`} aria-hidden="true">
              <RiskIcon className="h-5 w-5 text-white" />
            </div>
            <div>
              <h3 className="font-semibold">{risk.label}</h3>
              <p className="text-sm text-muted-foreground">
                {request.auto_approved
                  ? 'Auto-approved — activate below when you are ready to use it'
                  : 'Manual review required before activation'}
              </p>
            </div>
            <Badge variant="outline" className="ml-auto">
              Max: {request.duration}h
            </Badge>
          </div>
          {summary && (
            <p className="mt-3 rounded-md bg-muted p-3 text-sm">
              <span className="font-medium">In plain language: </span>
              {summary}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Reviewer feedback */}
      {request.feedback && (
        <Card>
          <CardHeader>
            <CardTitle>Reviewer feedback</CardTitle>
            <CardDescription>
              From {request.reviewer ?? 'reviewer'} · {formatTime(request.decided_at)}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="whitespace-pre-wrap text-sm">{request.feedback}</p>
          </CardContent>
        </Card>
      )}

      {/* Guardrail findings */}
      {findings.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldAlert className="h-5 w-5" aria-hidden="true" />
              Compliance Guardrail
            </CardTitle>
            <CardDescription>
              Local deterministic checks on the generated policy. Findings can raise the risk
              level, never lower it.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {findings.map((finding, i) => {
              const style = findingStyles[finding.severity]
              return (
                <div key={i} className="rounded-md border p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge className={style.badge}>{style.label}</Badge>
                    <span className="font-mono text-xs text-muted-foreground">{finding.location}</span>
                  </div>
                  <p className="mt-2 text-sm">{finding.message}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <p className="text-sm text-muted-foreground">{finding.suggestion}</p>
                    {onApplySuggestion && (
                      <Tip label="Send this fix back to the request form">
                        <Button
                          variant="outline"
                          size="sm"
                          className="ml-auto"
                          onClick={() => onApplySuggestion(finding.suggestion)}
                        >
                          <Wand2 className="mr-1 h-3 w-3" />
                          Revise with this fix
                        </Button>
                      </Tip>
                    )}
                  </div>
                </div>
              )
            })}
          </CardContent>
        </Card>
      )}

      {/* Policy */}
      <Card>
        <CardHeader>
          <CardTitle>Evaluated policy</CardTitle>
          <CardDescription>
            The least-privilege policy under review
            {riskyLines.length > 0 && ' — highlighted lines contain wildcards'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="json">
            <TabsList>
              <TabsTrigger value="json">JSON</TabsTrigger>
              <TabsTrigger value="explanation">Explanation</TabsTrigger>
              {isAdmin && <TabsTrigger value="audit">Audit trail</TabsTrigger>}
            </TabsList>
            <TabsContent value="json" className="mt-4">
              <div className="relative">
                <Suspense fallback={<EditorFallback />}>
                  <PolicyJsonViewer json={policyJson} riskyLines={riskyLines} />
                </Suspense>
                <CopyButton
                  value={policyJson}
                  label="Copy JSON"
                  className="absolute right-2 top-2"
                />
              </div>
            </TabsContent>
            <TabsContent value="explanation" className="mt-4 space-y-4">
              <div>
                <h4 className="font-semibold">Explanation</h4>
                <p className="text-muted-foreground">{request.explanation}</p>
              </div>
              {request.approver_note && (
                <div>
                  <h4 className="font-semibold">Approver Note</h4>
                  <p className="text-muted-foreground">{request.approver_note}</p>
                </div>
              )}
            </TabsContent>
            {isAdmin && (
              <TabsContent value="audit" className="mt-4">
                {auditQuery.isLoading && (
                  <p className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" /> Loading audit trail…
                  </p>
                )}
                {auditQuery.isError && (
                  <p className="text-sm text-destructive">Could not load the audit trail.</p>
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
                          <span className="font-medium">{event.actor}</span>
                          <span className="text-muted-foreground">({event.actor_role})</span>
                          <span className="ml-auto text-xs text-muted-foreground">
                            {formatTime(event.ts)}
                          </span>
                        </div>
                        {(event.from_status || event.to_status) && (
                          <p className="mt-1 text-xs text-muted-foreground">
                            {event.from_status ?? '—'} → {event.to_status ?? '—'}
                          </p>
                        )}
                        {typeof event.feedback === 'string' && event.feedback && (
                          <p className="mt-1 text-muted-foreground">“{event.feedback}”</p>
                        )}
                      </li>
                    ))}
                  </ol>
                )}
              </TabsContent>
            )}
          </Tabs>
        </CardContent>
      </Card>

      {/* Errors */}
      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive" role="alert">
          {error}
        </div>
      )}

      {/* Owner: activate an approved request (dev grants re-activate in-window) */}
      {showOwnerActivation && (
        <Card>
          <CardHeader>
            <CardTitle>
              {request.status === 'activated' ? 'Need fresh credentials?' : 'Ready to use it?'}
            </CardTitle>
            <CardDescription>
              {request.status === 'activated'
                ? `Dev grant — activate again for a fresh ≤12h session inside the window${request.grant_expires_at ? ` (ends ${formatTime(request.grant_expires_at)})` : ''}.`
                : `Approval creates no credentials — not even for auto-approved requests. Activate below when you are ready; sessions last up to ${request.duration}h.`}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-3 sm:flex-row">
              <Tip label="Mint temporary credentials now — the session starts immediately">
                <Button
                  onClick={() => activateMutation.mutate()}
                  disabled={busy}
                  className="flex-1"
                  size="lg"
                >
                  {activateMutation.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Activating…
                    </>
                  ) : (
                    <>
                      <Rocket className="mr-2 h-4 w-4" />
                      {request.status === 'activated' ? 'Activate fresh session' : 'Activate credentials'}
                    </>
                  )}
                </Button>
              </Tip>
              {canCancel && (
                <CancelGrantButton
                  disabled={busy}
                  pending={cancelMutation.isPending}
                  onConfirm={() => cancelMutation.mutate()}
                />
              )}
              {canDiscard && (
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="outline" size="lg" disabled={busy}>
                      <Ban className="mr-2 h-4 w-4" />
                      Discard
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Discard this request?</AlertDialogTitle>
                      <AlertDialogDescription>
                        The request will be withdrawn. No credentials will ever be issued for it.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction onClick={() => discardMutation.mutate()}>
                        Discard request
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Admin: cancel someone else's live grant */}
      {isAdmin && !isOwner && canCancel && (
        <Card>
          <CardContent className="flex flex-col gap-3 pt-6 sm:flex-row sm:items-center">
            <p className="flex-1 text-sm text-muted-foreground">
              This grant is live. Cancel it early if the access is no longer needed —
              already-issued sessions still run to their own expiry.
            </p>
            <CancelGrantButton
              disabled={busy}
              pending={cancelMutation.isPending}
              onConfirm={() => cancelMutation.mutate()}
            />
          </CardContent>
        </Card>
      )}

      {/* Owner: waiting / sent back / denied */}
      {isOwner && request.status === 'pending_review' && (
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">
              Waiting for an administrator to review. You will see their name and feedback here
              once they decide.
            </p>
            {canDiscard && (
              <Tip label="Withdraw this request — no credentials will ever be issued for it">
                <Button
                  variant="outline"
                  className="mt-3"
                  disabled={busy}
                  onClick={() => discardMutation.mutate()}
                >
                  {discardMutation.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Undo2 className="mr-2 h-4 w-4" />
                  )}
                  Withdraw request
                </Button>
              </Tip>
            )}
          </CardContent>
        </Card>
      )}

      {isOwner && request.status === 'changes_requested' && (
        <Card>
          <CardHeader>
            <CardTitle>Sent back for changes</CardTitle>
            <CardDescription>
              {request.reviewer ?? 'A reviewer'} asked for changes — edit and resubmit below.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 sm:flex-row">
            <Tip label="Edit the request text and submit it again as a new revision">
              <Button onClick={() => onResubmit(request)} className="flex-1">
                <RotateCcw className="mr-2 h-4 w-4" />
                Edit &amp; resubmit
              </Button>
            </Tip>
            {canDiscard && (
              <Tip label="Withdraw this request instead of resubmitting">
                <Button variant="outline" disabled={busy} onClick={() => discardMutation.mutate()}>
                  Discard
                </Button>
              </Tip>
            )}
          </CardContent>
        </Card>
      )}

      {isOwner && request.status === 'denied' && (
        <Card>
          <CardHeader>
            <CardTitle>Request denied</CardTitle>
            <CardDescription>
              Denied by {request.reviewer ?? 'reviewer'}. Read the feedback and AI guidance for a
              better-scoped request.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Tip label="Read AI suggestions for a better-scoped request">
              <Button onClick={() => onShowGuidance(request)} className="w-full">
                View guidance
              </Button>
            </Tip>
          </CardContent>
        </Card>
      )}

      {/* Admin review actions */}
      {showAdminActions && (
        <Card>
          <CardHeader>
            <CardTitle>Review decision</CardTitle>
            <CardDescription>
              You are reviewing {request.requester}&apos;s request. Denials and send-backs require
              feedback so they know what to change.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="review-feedback">Feedback to {request.requester}</Label>
              <Textarea
                id="review-feedback"
                placeholder="Required for deny / send back — e.g. scope to the billing bucket and resubmit…"
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                rows={3}
              />
            </div>
            <div className="flex flex-col gap-3 sm:flex-row">
              <Tip label="Approve — the requester can then activate credentials when ready">
                <Button
                  onClick={() => handleReview('approve')}
                  disabled={busy}
                  className="flex-1"
                  size="lg"
                >
                  {reviewMutation.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <CheckCircle2 className="mr-2 h-4 w-4" />
                  )}
                  Approve
                </Button>
              </Tip>
              <Tip label="Return to the requester with your feedback — they can edit and resubmit">
                <Button
                  variant="outline"
                  onClick={() => handleReview('changes_requested')}
                  disabled={busy}
                  size="lg"
                >
                  <RotateCcw className="mr-2 h-4 w-4" />
                  Send back
                </Button>
              </Tip>
              <Tip label="Deny permanently — feedback is required so they know why">
                <Button
                  variant="destructive"
                  onClick={() => handleReview('deny')}
                  disabled={busy}
                  size="lg"
                >
                  <AlertCircle className="mr-2 h-4 w-4" />
                  Deny
                </Button>
              </Tip>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function CancelGrantButton({
  disabled,
  pending,
  onConfirm,
}: {
  disabled: boolean
  pending: boolean
  onConfirm: () => void
}) {
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="outline" size="lg" disabled={disabled}>
          {pending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Ban className="mr-2 h-4 w-4" />
          )}
          Cancel grant
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Cancel this grant?</AlertDialogTitle>
          <AlertDialogDescription>
            No further credentials will be issued for it. Already-issued
            sessions stay valid until their own expiry — AWS cannot
            revoke temporary credentials early.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Keep grant</AlertDialogCancel>
          <AlertDialogAction onClick={onConfirm}>Cancel grant</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

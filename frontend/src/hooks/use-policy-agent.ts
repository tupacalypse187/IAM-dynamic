import { useCallback, useEffect, useRef } from 'react'
import { api } from '@/lib/api'
import { desktop, isDesktop } from '@/lib/desktop'
import type { AccessRequest, ConfirmedUnit, Credentials, GrantNarrative, PreviewUnit } from '@/types/api'
import type {
  AgentProgress,
  ClarifyQuestion,
  GenerateInput,
  GuardrailFinding,
} from '@/types/desktop'

/** A submitted (persisted) request plus transient local evaluation context. */
export interface SubmitOutcome {
  /** First unit of the created batch (detail navigation target). */
  request: AccessRequest
  /** Every row created by this submission (usually one). */
  batch: AccessRequest[]
  /** Local guardrail findings (desktop path; empty on web). */
  findings: GuardrailFinding[]
  /** Plain-language grant summary (desktop path; null on web). */
  summary: string | null
}

export type SubmitResult =
  | { kind: 'clarify'; questions: ClarifyQuestion[] }
  | { kind: 'split-consent'; preview: PreviewUnit[]; requestText: string; confirm: (choice: 'split' | 'full-review') => Promise<SubmitOutcome> }
  | ({ kind: 'submitted' } & SubmitOutcome)

export interface PolicyAgent {
  readonly inDesktop: boolean
  /** Evaluate (clarify-aware) and persist as a review-routed request. */
  submit: (input: GenerateInput) => Promise<SubmitResult>
  /** Dry-run split preview (web path; nothing persisted). */
  preview: (input: GenerateInput) => Promise<PreviewUnit[]>
  /** Persist previewed units after the user accepts the split or full review. */
  confirmPreview: (input: GenerateInput, requestText: string, preview: PreviewUnit[], choice: 'split' | 'full-review') => Promise<SubmitOutcome>
  /** Issue credentials for an approved request when the owner is ready. */
  activate: (id: number) => Promise<Credentials>
  /**
   * Mirror a server-side request event into the desktop audit ledger.
   * No-op in browsers (the server JSONL trail is the record there) and
   * best-effort everywhere — tracking must never break the action itself.
   */
  track: (kind: string, summary: string, details?: Record<string, unknown>) => void
  subscribeProgress: (listener: (progress: AgentProgress) => void) => () => void
}

/**
 * Unified policy pipeline. In the desktop shell every call is routed
 * through the main-process Agent_Kit over IPC (with ledger + guardrail);
 * in a browser it uses the backend REST API directly with identical UI.
 */
export function usePolicyAgent(): PolicyAgent {
  const progressRef = useRef<((p: AgentProgress) => void) | null>(null)

  useEffect(() => {
    if (!isDesktop()) return
    return desktop.onAgentProgress((p) => progressRef.current?.(p))
  }, [])

  const subscribeProgress = useCallback((listener: (progress: AgentProgress) => void) => {
    progressRef.current = listener
    return () => {
      progressRef.current = null
    }
  }, [])

  const preview = useCallback(async (input: GenerateInput): Promise<PreviewUnit[]> => {
    return api.previewRequest({
      request_text: composeWebText(input),
      provider: input.profileId ? undefined : input.provider,
      model: input.profileId ? undefined : input.model,
      duration: input.durationHours,
      environment: input.environment,
      profile_id: input.profileId,
    })
  }, [])

  const confirmPreview = useCallback(
    async (
      input: GenerateInput,
      requestText: string,
      previewUnits: PreviewUnit[],
      choice: 'split' | 'full-review',
    ): Promise<SubmitOutcome> => {
      const confirmed: ConfirmedUnit[] = previewUnits.map((u) => ({
        policy: u.policy as Record<string, unknown>,
        risk: u.risk,
        explanation: u.explanation,
        approver_note: u.approver_note,
        label: u.label,
        narrative: (u.narrative ?? {}) as Record<string, unknown>,
      }))
      const batch = await api.submitRequest({
        request_text: requestText,
        provider: input.profileId ? undefined : input.provider,
        model: input.profileId ? undefined : input.model,
        duration: input.durationHours,
        environment: input.environment,
        profile_id: input.profileId,
        full_review: choice === 'full-review',
        confirmed_units: confirmed,
      })
      return { request: batch[0], batch, findings: [], summary: null }
    },
    [],
  )

  const submit = useCallback(async (input: GenerateInput): Promise<SubmitResult> => {
    if (!isDesktop()) {
      const requestText = composeWebText(input)
      // Preview first so a split never persists as a surprise: one unit
      // persists immediately, several return a consent step (no second
      // LLM call on confirm — the previewed units are pinned).
      const previewUnits = await api.previewRequest({
        request_text: requestText,
        // A saved profile resolves provider/model server-side; sending the
        // unrelated Settings fallback alongside would only mislead.
        provider: input.profileId ? undefined : input.provider,
        model: input.profileId ? undefined : input.model,
        duration: input.durationHours,
        environment: input.environment,
        profile_id: input.profileId,
      })
      if (previewUnits.length > 1) {
        const confirm = (choice: 'split' | 'full-review') =>
          confirmPreview(input, requestText, previewUnits, choice)
        return { kind: 'split-consent', preview: previewUnits, requestText, confirm }
      }
      const batch = await api.submitRequest({
        request_text: requestText,
        provider: input.profileId ? undefined : input.provider,
        model: input.profileId ? undefined : input.model,
        duration: input.durationHours,
        environment: input.environment,
        profile_id: input.profileId,
      })
      return { kind: 'submitted', request: batch[0], batch, findings: [], summary: null }
    }
    // Desktop: clarify-aware Agent_Kit evaluation first. The main process
    // previews (dry-run), so every separable grant comes back and a split
    // goes through the same consent step as the browser — nothing persists
    // until the user chooses. Single grants persist via record without
    // re-running the LLM. The stored request_text is the exact evaluated text.
    const result = await desktop.generatePolicy(input)
    if (result.status === 'clarify') {
      return { kind: 'clarify', questions: result.questions }
    }
    const head = result.result
    const units: PreviewUnit[] = (result.units ?? [{
      policy: head.policy,
      risk: head.risk,
      explanation: head.explanation,
      approver_note: head.approver_note,
      label: '',
      narrative: {},
      duration: head.max_duration,
      auto_approved: head.auto_approved,
    }]).map((u) => ({
      policy: u.policy as Record<string, unknown>,
      risk: u.risk,
      explanation: u.explanation,
      approver_note: u.approver_note,
      label: u.label,
      narrative: (u.narrative ?? {}) as GrantNarrative,
      duration: u.duration,
      auto_approved: u.auto_approved,
    }))
    if (units.length > 1) {
      const confirm = async (choice: 'split' | 'full-review'): Promise<SubmitOutcome> => {
        const batch =
          choice === 'split'
            ? await api.recordRequest({
                request_text: result.requestText,
                provider: input.profileId ? undefined : input.provider,
                model: input.profileId ? undefined : input.model,
                duration: input.durationHours,
                environment: input.environment,
                policy: {},
                risk: 'medium',
                units: units.map((u) => ({ ...u, narrative: u.narrative as Record<string, unknown> })),
                profile_id: input.profileId,
              })
            : (
                await confirmPreview(
                  { ...input, durationHours: input.durationHours },
                  result.requestText,
                  units,
                  'full-review',
                )
              ).batch
        const outcome = { request: batch[0], batch, findings: result.findings, summary: result.summary }
        desktop
          .logAudit('request_submitted', `Request batch submitted (${batch.length} parts)`, {
            requestIds: batch.map((r) => r.id),
            choice,
          })
          .catch(() => undefined)
        return outcome
      }
      return { kind: 'split-consent', preview: units, requestText: result.requestText, confirm }
    }
    const [only] = units
    const batch = await api.recordRequest({
      request_text: result.requestText,
      provider: input.profileId ? undefined : input.provider,
      model: input.profileId ? undefined : input.model,
      duration: input.durationHours,
      environment: input.environment,
      policy: only.policy,
      risk: only.risk,
      explanation: only.explanation,
      approver_note: only.approver_note,
      label: only.label,
      narrative: only.narrative as Record<string, unknown>,
      profile_id: input.profileId,
    })
    const request = batch[0]
    if (isDesktop()) {
      desktop
        .logAudit('request_submitted', `Request #${request.id} submitted (${request.status})`, {
          requestId: request.id,
          status: request.status,
          risk: request.risk,
        })
        .catch(() => undefined)
    }
    return { kind: 'submitted', request, batch, findings: result.findings, summary: result.summary }
  }, [confirmPreview])

  const activate = useCallback(async (id: number): Promise<Credentials> => {
    if (isDesktop()) {
      const creds = await desktop.activateRequest(id)
      return {
        access_key_id: creds.access_key_id,
        secret_access_key: creds.secret_access_key,
        session_token: creds.session_token,
        expiration: creds.expiration,
        region: creds.region,
      } satisfies Credentials
    }
    return api.activateRequest(id)
  }, [])

  const track = useCallback((kind: string, summary: string, details?: Record<string, unknown>) => {
    if (!isDesktop()) return
    desktop.logAudit(kind, summary, details).catch(() => undefined)
  }, [])

  return { inDesktop: isDesktop(), submit, preview, confirmPreview, activate, track, subscribeProgress }
}

/** Browser path: fold guided fields + answers into one request string. */
function composeWebText(input: GenerateInput): string {
  const parts = [input.freeText]
  if (input.guided.task) parts.push(`Task: ${input.guided.task}`)
  if (input.guided.resources) parts.push(`Resources: ${input.guided.resources}`)
  if (input.guided.ticket) parts.push(`Ticket/justification: ${input.guided.ticket}`)
  if (input.answers) {
    for (const [field, value] of Object.entries(input.answers)) {
      if (value.trim()) parts.push(`${field}: ${value.trim()}`)
    }
  }
  return parts.filter(Boolean).join('\n')
}

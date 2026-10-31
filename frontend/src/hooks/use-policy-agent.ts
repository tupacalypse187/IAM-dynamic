import { useCallback, useEffect, useRef } from 'react'
import { api } from '@/lib/api'
import { desktop, isDesktop } from '@/lib/desktop'
import type { AccessRequest, Credentials, PolicyResponse } from '@/types/api'
import type {
  AgentProgress,
  ClarifyQuestion,
  DesktopPolicyResult,
  GenerateInput,
  GuardrailFinding,
  RiskLevel,
} from '@/types/desktop'

export type PolicyOutcome =
  | { kind: 'clarify'; questions: ClarifyQuestion[] }
  | { kind: 'policy'; data: PolicyResponse; findings: GuardrailFinding[]; summary: string | null }

/** A submitted (persisted) request plus transient local evaluation context. */
export interface SubmitOutcome {
  request: AccessRequest
  /** Local guardrail findings (desktop path; empty on web). */
  findings: GuardrailFinding[]
  /** Plain-language grant summary (desktop path; null on web). */
  summary: string | null
}

export type SubmitResult =
  | { kind: 'clarify'; questions: ClarifyQuestion[] }
  | ({ kind: 'submitted' } & SubmitOutcome)

export interface PolicyAgent {
  readonly inDesktop: boolean
  generate: (input: GenerateInput) => Promise<PolicyOutcome>
  issue: (input: { policy: Record<string, unknown>; duration: number; approved: boolean; changeCase?: string; risk: string; autoApproved: boolean }) => Promise<Credentials>
  /** Evaluate (clarify-aware) and persist as a review-routed request. */
  submit: (input: GenerateInput) => Promise<SubmitResult>
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

function toWebPolicy(result: DesktopPolicyResult): PolicyResponse {
  return {
    policy: result.policy,
    risk: result.risk,
    explanation: result.explanation,
    approver_note: result.approver_note,
    auto_approved: result.auto_approved,
    max_duration: result.max_duration,
  }
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

  const generate = useCallback(async (input: GenerateInput): Promise<PolicyOutcome> => {
    if (isDesktop()) {
      const result = await desktop.generatePolicy(input)
      if (result.status === 'clarify') {
        return { kind: 'clarify', questions: result.questions }
      }
      return {
        kind: 'policy',
        data: toWebPolicy(result.result),
        findings: result.findings,
        summary: result.summary,
      }
    }
    const data = await api.generatePolicy({
      request_text: composeWebText(input),
      provider: input.provider,
      model: input.model,
      duration: input.durationHours,
    })
    return { kind: 'policy', data, findings: [], summary: null }
  }, [])

  const issue = useCallback(
    async (input: { policy: Record<string, unknown>; duration: number; approved: boolean; changeCase?: string; risk: string; autoApproved: boolean }) => {
      if (isDesktop()) {
        const creds = await desktop.issueCredentials({
          policy: input.policy,
          durationHours: input.duration,
          approved: input.approved,
          changeCase: input.changeCase,
          // Reviewed risk label; the backend normalizes anything unexpected.
          risk: input.risk as RiskLevel,
          autoApproved: input.autoApproved,
        })
        return {
          access_key_id: creds.access_key_id,
          secret_access_key: creds.secret_access_key,
          session_token: creds.session_token,
          expiration: creds.expiration,
          region: creds.region,
        } satisfies Credentials
      }
      const { autoApproved, ...rest } = input
      return api.issueCredentials({ ...rest, change_case: input.changeCase, risk: input.risk, auto_approved: autoApproved })
    },
    [],
  )

  const submit = useCallback(async (input: GenerateInput): Promise<SubmitResult> => {
    if (!isDesktop()) {
      const request = await api.submitRequest({
        request_text: composeWebText(input),
        provider: input.provider,
        model: input.model,
        duration: input.durationHours,
      })
      return { kind: 'submitted', request, findings: [], summary: null }
    }
    // Desktop: clarify-aware Agent_Kit evaluation first, then persist the
    // evaluated result without re-running the LLM (see /api/requests/record).
    // The stored request_text is the exact text that was evaluated.
    const result = await desktop.generatePolicy(input)
    if (result.status === 'clarify') {
      return { kind: 'clarify', questions: result.questions }
    }
    const request = await api.recordRequest({
      request_text: result.requestText,
      provider: input.provider,
      model: input.model,
      duration: result.result.max_duration,
      policy: result.result.policy,
      risk: result.result.risk,
      explanation: result.result.explanation,
      approver_note: result.result.approver_note,
    })
    if (isDesktop()) {
      desktop
        .logAudit('request_submitted', `Request #${request.id} submitted (${request.status})`, {
          requestId: request.id,
          status: request.status,
          risk: request.risk,
        })
        .catch(() => undefined)
    }
    return { kind: 'submitted', request, findings: result.findings, summary: result.summary }
  }, [])

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

  return { inDesktop: isDesktop(), generate, issue, submit, activate, track, subscribeProgress }
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

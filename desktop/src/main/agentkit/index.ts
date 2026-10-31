/**
 * Agent_Kit orchestrator — Router → PolicyArchitect → AuditRisk → JITLifecycle.
 *
 * Each agent is a plain function with a narrow input/output contract so a
 * future Modal-hosted implementation (RAG compliance search, sandbox
 * simulation) can replace any stage without touching the others or the IPC
 * layer. Progress callbacks stream stage updates to the renderer over IPC.
 */

import type {
  AgentProgress,
  GenerateInput,
  GenerateResult,
  IssueInput,
  LeaseCredentials,
  LeaseStatus,
  RiskLevel,
} from '../../shared/ipc-contract'
import { applyAnswers, clarifyingQuestions, extractIntent } from './router'
import { analyzePolicy, combineRisk, summarizePlainLanguage } from './audit-risk'
import type { BackendClient } from './backend-client'
import type { Ledger } from '../ledger'

export type ProgressFn = (progress: AgentProgress) => void

export interface OrchestratorDeps {
  backend: BackendClient
  ledger: Ledger
}

const RISK_CEILING: Record<RiskLevel, number> = {
  low: 12,
  medium: 4,
  high: 2,
  critical: 1,
}

/** Maximum issuable hours for a risk level (mirrors backend guardrails). */
export function maxDurationForRisk(risk: RiskLevel): number {
  return RISK_CEILING[risk]
}

/**
 * Run the Router → PolicyArchitect → AuditRisk pipeline.
 * Returns clarifying questions when the intent is underspecified,
 * otherwise a backend-synthesized policy upgraded by the local guardrail.
 */
export async function generatePolicy(
  deps: OrchestratorDeps,
  input: GenerateInput,
  onProgress: ProgressFn = () => undefined,
): Promise<GenerateResult> {
  onProgress({ stage: 'router', message: 'Understanding your request…' })
  const intent = extractIntent(input.freeText, input.guided)
  const answers = input.answers ?? {}
  const questions = clarifyingQuestions(intent, answers)
  if (questions.length > 0 && Object.keys(answers).length === 0) {
    return { status: 'clarify', questions }
  }

  const requestText = applyAnswers(intent, answers)
  const durationHours = Math.min(input.durationHours || intent.durationHours || 2, 12)

  onProgress({ stage: 'architect', message: 'Synthesizing least-privilege policy…' })
  const backendResult = await deps.backend.generatePolicy({
    request_text: requestText,
    provider: input.provider,
    model: input.model,
    duration: durationHours,
  })

  onProgress({ stage: 'audit', message: 'Checking compliance guardrails…' })
  const { findings, risk: guardrailRisk } = analyzePolicy(backendResult.policy)
  const risk = combineRisk(backendResult.risk, guardrailRisk)
  const effectiveMax = Math.min(backendResult.max_duration, maxDurationForRisk(risk))

  const auditId = deps.ledger.append('generation', `Policy generated (${risk} risk)`, {
    provider: input.provider,
    model: input.model,
    durationHours,
    risk,
    backendRisk: backendResult.risk,
    guardrailRisk,
    findingCount: findings.length,
    requestExcerpt: requestText.slice(0, 500),
  })

  onProgress({ stage: 'done', message: 'Policy ready for review.' })
  return {
    status: 'policy',
    result: { ...backendResult, risk, max_duration: effectiveMax },
    findings,
    summary: summarizePlainLanguage(backendResult.policy, durationHours),
    auditId,
  }
}

export interface LeaseState {
  credentials: LeaseCredentials | null
  issuedAt: string | null
}

/**
 * Issue temporary credentials via the backend and track the lease.
 * Revocation deletes local credentials and records the event — note that
 * AWS STS sessions cannot be force-revoked server-side; expiry (and the
 * backend role's session policy) is the enforcement mechanism.
 */
export async function issueCredentials(
  deps: OrchestratorDeps,
  lease: LeaseState,
  input: IssueInput,
  onProgress: ProgressFn = () => undefined,
): Promise<LeaseCredentials> {
  if (input.approved !== true) {
    throw new Error('Refusing to issue credentials: the policy has not been approved.')
  }
  // Re-analyze the exact policy being issued: the renderer payload is
  // untrusted and may differ from the reviewed policy. The guardrail can
  // only raise risk, and the issued duration is clamped to its ceiling.
  const { findings, risk: guardrailRisk } = analyzePolicy(input.policy)
  const requestedDuration = input.durationHours || 1
  const durationHours = Math.min(requestedDuration, maxDurationForRisk(guardrailRisk))
  onProgress({ stage: 'done', message: 'Issuing temporary credentials…' })
  const creds = await deps.backend.issueCredentials({
    policy: input.policy,
    duration: durationHours,
    approved: true,
  })
  lease.credentials = creds
  lease.issuedAt = new Date().toISOString()
  deps.ledger.append('credentials_issued', `Temporary credentials issued (${durationHours}h)`, {
    expiration: creds.expiration,
    region: creds.region,
    approved: true,
    changeCase: input.changeCase ?? null,
    durationHours,
    requestedDurationHours: requestedDuration,
    guardrailRisk,
    findingCount: findings.length,
  })
  return creds
}

export function revokeCredentials(deps: OrchestratorDeps, lease: LeaseState): void {
  lease.credentials = null
  lease.issuedAt = null
  deps.ledger.append('revocation', 'Local credentials discarded by user', {})
}

export function leaseStatus(lease: LeaseState): LeaseStatus {
  if (!lease.credentials) {
    return { active: false, expiresAt: null, secondsRemaining: 0 }
  }
  const expiresAt = lease.credentials.expiration
  const secondsRemaining = Math.max(0, Math.floor((Date.parse(expiresAt) - Date.now()) / 1000))
  return { active: secondsRemaining > 0, expiresAt, secondsRemaining }
}

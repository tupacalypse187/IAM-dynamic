/**
 * Shared IPC contract between the Electron main process and the preload bridge.
 *
 * This file is the source of truth for channel names and payload shapes.
 * The renderer mirror lives in `frontend/src/lib/desktop.ts` — keep the two
 * in sync manually; the `DesktopApi` surface is intentionally small so drift
 * is easy to spot in review.
 */

export const IpcChannels = {
  appInfo: 'app:info',
  agentGenerate: 'agentkit:generate-policy',
  agentProgress: 'agentkit:progress',
  agentIssue: 'agentkit:issue-credentials',
  agentRevoke: 'agentkit:revoke-credentials',
  leaseStatus: 'lease:status',
  ledgerRecent: 'ledger:recent',
  ledgerExport: 'ledger:export',
  vaultSetToken: 'vault:set-token',
  vaultGetToken: 'vault:get-token',
  vaultClearToken: 'vault:clear-token',
  updaterCheck: 'updater:check',
  updaterQuitInstall: 'updater:quit-install',
  updaterEvent: 'updater:event',
  shortcutCapture: 'shortcut:capture-voice',
} as const

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical'

/** IAM policy document as produced by the backend (AWS IAM JSON). */
export type PolicyDocument = Record<string, unknown>

export interface GeneratedPolicy {
  policy: PolicyDocument
  risk: RiskLevel
  explanation: string
  approver_note: string
  auto_approved: boolean
  max_duration: number
}

export interface GuardrailFinding {
  severity: 'critical' | 'high' | 'medium' | 'low'
  location: string
  message: string
  suggestion: string
}

export interface ClarifyQuestion {
  /** Stable field key, e.g. "resources" | "actions" | "duration_hours". */
  field: string
  prompt: string
  placeholder: string
  /** Prefilled suggestion the user can accept as-is. */
  suggestion?: string
}

export interface GuidedContext {
  task: string
  resources: string
  ticket: string
}

export interface GenerateInput {
  freeText: string
  guided: GuidedContext
  provider: string
  model?: string
  durationHours: number
  /** Answers keyed by ClarifyQuestion.field from a previous clarify round. */
  answers?: Record<string, string>
}

export type GenerateResult =
  | { status: 'clarify'; questions: ClarifyQuestion[] }
  | {
      status: 'policy'
      result: GeneratedPolicy
      findings: GuardrailFinding[]
      /** Plain-language grant summary for users who don't read JSON. */
      summary: string
      auditId: number
    }

export interface AgentProgress {
  stage: 'router' | 'architect' | 'audit' | 'done'
  message: string
}

export interface LeaseCredentials {
  access_key_id: string
  secret_access_key: string
  session_token: string
  expiration: string
  region: string
}

export interface IssueInput {
  policy: PolicyDocument
  durationHours: number
  approved: boolean
  changeCase?: string
}

export interface LeaseStatus {
  active: boolean
  expiresAt: string | null
  secondsRemaining: number
}

export type AuditKind =
  | 'generation'
  | 'approval'
  | 'credentials_issued'
  | 'revocation'
  | 'update_installed'

export interface AuditEvent {
  id: number
  ts: string
  kind: AuditKind
  summary: string
  details: string
}

export type UpdaterEvent =
  | { type: 'checking' }
  | { type: 'available'; version: string }
  | { type: 'downloaded'; version: string }
  | { type: 'not-available' }
  | { type: 'error'; message: string }

export interface AppInfo {
  version: string
  platform: NodeJS.Platform
  backendUrl: string
  updatesEnabled: boolean
}

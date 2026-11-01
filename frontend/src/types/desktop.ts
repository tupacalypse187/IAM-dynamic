// Renderer-side mirror of desktop/src/shared/ipc-contract.ts.
// The desktop preload bridge is the source of truth — keep these shapes
// in sync manually. They are duplicated (not imported) because the
// renderer bundle cannot reach into desktop sources.

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical'

export type PolicyDocument = Record<string, unknown>

export interface GuardrailFinding {
  severity: 'critical' | 'high' | 'medium' | 'low'
  location: string
  message: string
  suggestion: string
}

export interface ClarifyQuestion {
  field: string
  prompt: string
  placeholder: string
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
  /** Deployment tier — caps the grant window server-side. */
  environment?: string
  answers?: Record<string, string>
  /** Saved LLM profile — its key evaluates, its id attributes the record. */
  profileId?: number
}

export interface DesktopPolicyResult {
  policy: PolicyDocument
  risk: RiskLevel
  explanation: string
  approver_note: string
  auto_approved: boolean
  max_duration: number
}

export type DesktopGenerateResult =
  | { status: 'clarify'; questions: ClarifyQuestion[] }
  | {
      status: 'policy'
      result: DesktopPolicyResult
      findings: GuardrailFinding[]
      summary: string
      auditId: number
      /** Exact evaluated text (intent + answers) — persisted verbatim on submit. */
      requestText: string
    }

export interface AgentProgress {
  stage: 'router' | 'architect' | 'audit' | 'done'
  message: string
}

export interface DesktopCredentials {
  access_key_id: string
  secret_access_key: string
  session_token: string
  expiration: string
  region: string
}

export interface LeaseStatus {
  active: boolean
  expiresAt: string | null
  secondsRemaining: number
}

export interface AuditEventView {
  id: number
  ts: string
  kind: string
  summary: string
  details: string
}

export type UpdaterEvent =
  | { type: 'checking' }
  | { type: 'available'; version: string }
  | { type: 'downloaded'; version: string }
  | { type: 'not-available' }
  | { type: 'error'; message: string }

export interface DesktopApi {
  getAppInfo: () => Promise<{ version: string; platform: string; backendUrl: string; updatesEnabled: boolean }>
  generatePolicy: (input: GenerateInput) => Promise<DesktopGenerateResult>
  onAgentProgress: (listener: (progress: AgentProgress) => void) => () => void
  issueCredentials: (input: { policy: PolicyDocument; durationHours: number; approved: boolean; changeCase?: string; risk?: RiskLevel; autoApproved?: boolean }) => Promise<DesktopCredentials>
  /** Activate an approved request: server issuance + local lease/tray/ledger. */
  activateRequest: (requestId: number) => Promise<DesktopCredentials>
  /** Mirror a server-side request event into the local audit ledger. */
  logAudit: (kind: string, summary: string, details?: Record<string, unknown>) => Promise<number>
  revokeCredentials: () => Promise<void>
  getLeaseStatus: () => Promise<LeaseStatus>
  getRecentEvents: (limit?: number) => Promise<AuditEventView[]>
  exportLedger: (format: 'markdown' | 'json') => Promise<string>
  setToken: (token: string) => Promise<void>
  clearToken: () => Promise<void>
  checkForUpdates: () => Promise<void>
  quitAndInstall: () => Promise<void>
  onUpdaterEvent: (listener: (event: UpdaterEvent) => void) => () => void
  onCaptureShortcut: (listener: () => void) => () => void
}

declare global {
  interface Window {
    desktopApi?: DesktopApi
  }
}

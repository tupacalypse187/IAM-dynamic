// API Types for IAM-Dynamic Backend

export interface ModelInfo {
  id: string
  name: string
}

export interface LLMProvider {
  id: string
  name: string
  model: string
  models: ModelInfo[]
}

export interface ProvidersResponse {
  providers: LLMProvider[]
  account_id: string
  current_provider: string
}

export interface PolicyRequest {
  request_text: string
  provider?: string
  model?: string
  duration?: number
  change_case?: string
}

export interface PolicyResponse {
  policy: Record<string, unknown>
  risk: 'low' | 'medium' | 'high' | 'critical'
  explanation: string
  approver_note: string
  auto_approved: boolean
  max_duration: number
}

export interface IssueCredentialsRequest {
  policy: Record<string, unknown>
  duration: number
  approved?: boolean
  approver?: string
  change_case?: string
}

export interface Credentials {
  access_key_id: string
  secret_access_key: string
  session_token: string
  expiration: string
  region: string
}

export type RequestStatus =
  | 'pending_review'
  | 'approved'
  | 'denied'
  | 'changes_requested'
  | 'activated'
  | 'discarded'

/** A persisted access request with its evaluated LLM response + review state. */
export interface AccessRequest {
  id: number
  requester: string
  request_text: string
  provider: string
  model: string | null
  duration: number
  policy: Record<string, unknown>
  risk: 'low' | 'medium' | 'high' | 'critical'
  explanation: string
  approver_note: string
  auto_approved: boolean
  status: RequestStatus
  reviewer: string | null
  feedback: string | null
  revision: number
  created_at: string
  updated_at: string
  decided_at: string | null
  credentials_expires_at: string | null
}

export type ReviewDecision = 'approve' | 'deny' | 'changes_requested'

/** A user's saved LLM profile — key material is never serialized. */
export interface LlmProfile {
  id: number
  username: string
  name: string
  provider: string
  model: string
  has_key: boolean
  key_hint: string
  active: boolean
  created_at: string
  updated_at: string
}

/** One admin-managed provider/model pair. */
export interface CatalogEntry {
  provider: string
  model: string
  display_name: string
  enabled: boolean
}

/** One JSONL audit trail record. Extra keys carry event metadata. */
export interface AuditEvent {
  ts: string
  event: string
  request_id: number
  actor: string
  actor_role: string
  from_status: string | null
  to_status: string | null
  [key: string]: unknown
}

export interface HealthResponse {
  status: string
  version: string
  timestamp: string
}

// API Types for IAM-Dynamic Backend

export interface LLMProvider {
  id: string
  name: string
  model: string
}

export interface ProvidersResponse {
  providers: LLMProvider[]
  account_id: string
}

export interface PolicyRequest {
  request_text: string
  provider?: string
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

export interface HealthResponse {
  status: string
  version: string
  timestamp: string
}

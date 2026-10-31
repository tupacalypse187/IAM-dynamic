/**
 * AuditRiskAgent — deterministic AST-level policy guardrail.
 *
 * Runs locally in the main process so policy content is evaluated without
 * depending on any remote call. Findings can only *raise* the backend's
 * risk assessment, never lower it: a local check may miss context, but it
 * must not overrule a more informed verdict.
 *
 * The Modal-hosted RAG compliance benchmark (CIS/NIST) plugs in behind
 * `analyzePolicy` later — same return type, richer `suggestion` strings.
 */

import type { GuardrailFinding, PolicyDocument, RiskLevel } from '../../shared/ipc-contract'

const RISK_ORDER: RiskLevel[] = ['low', 'medium', 'high', 'critical']

/** Actions that enable privilege escalation or persistence. */
const ESCALATION_ACTIONS = [
  'iam:PassRole',
  'iam:CreatePolicyVersion',
  'iam:SetDefaultPolicyVersion',
  'iam:AttachUserPolicy',
  'iam:AttachGroupPolicy',
  'iam:AttachRolePolicy',
  'iam:PutUserPolicy',
  'iam:PutGroupPolicy',
  'iam:PutRolePolicy',
  'iam:CreateAccessKey',
  'iam:CreateLoginProfile',
  'iam:UpdateAssumeRolePolicy',
  'sts:AssumeRole',
  'sts:AssumeRoleWithSAML',
  'glue:UpdateDevEndpoint',
  'lambda:UpdateFunctionCode',
]

const READ_ONLY_PREFIXES = [
  's3:Get',
  's3:List',
  's3:Describe',
  'dynamodb:GetItem',
  'dynamodb:BatchGetItem',
  'dynamodb:Query',
  'dynamodb:Scan',
  'dynamodb:Describe',
  'ec2:Describe',
  'rds:Describe',
  'logs:Get',
  'logs:Describe',
  'logs:FilterLogEvents',
  'cloudwatch:Get',
  'cloudwatch:Describe',
  'cloudwatch:List',
]

interface Statement {
  index: number
  effect: string
  actions: string[]
  resources: string[]
  notActions: string[]
  notResources: string[]
}

function asArray(value: unknown): string[] {
  if (Array.isArray(value)) return value.filter((v): v is string => typeof v === 'string')
  if (typeof value === 'string') return [value]
  return []
}

function statementsOf(policy: PolicyDocument): Statement[] {
  const raw = policy['Statement']
  const list = Array.isArray(raw) ? raw : [raw]
  return list
    .filter((s): s is Record<string, unknown> => typeof s === 'object' && s !== null)
    .map((s, index) => ({
      index,
      effect: typeof s['Effect'] === 'string' ? (s['Effect'] as string) : 'Allow',
      actions: asArray(s['Action']),
      resources: asArray(s['Resource']),
      notActions: asArray(s['NotAction']),
      notResources: asArray(s['NotResource']),
    }))
}

function isWildcard(value: string): boolean {
  return value === '*' || value.endsWith(':*') || value.includes('*')
}

/**
 * Analyze an IAM policy document and return findings plus an overall
 * risk floor. Returns `{ findings: [], risk: 'low' }` for unparseable
 * input rather than throwing — inability to parse is itself surfaced
 * as a medium finding so it cannot silently pass.
 */
export function analyzePolicy(policy: PolicyDocument): { findings: GuardrailFinding[]; risk: RiskLevel } {
  const findings: GuardrailFinding[] = []
  let risk: RiskLevel = 'low'

  const raise = (level: RiskLevel) => {
    if (RISK_ORDER.indexOf(level) > RISK_ORDER.indexOf(risk)) risk = level
  }

  let statements: Statement[]
  try {
    statements = statementsOf(policy)
  } catch {
    statements = []
  }

  if (statements.length === 0) {
    findings.push({
      severity: 'medium',
      location: 'Statement',
      message: 'Policy has no parseable statements; it cannot be verified as least-privilege.',
      suggestion: 'Regenerate the policy from a concrete resource description.',
    })
    return { findings, risk: 'medium' }
  }

  for (const stmt of statements) {
    const where = `Statement[${stmt.index}]`
    if (stmt.effect.toLowerCase() === 'deny') continue

    if (stmt.notActions.length > 0) {
      findings.push({
        severity: 'high',
        location: `${where}.NotAction`,
        message: `NotAction (${stmt.notActions.join(', ')}) inverts scope — it allows every action except those listed.`,
        suggestion: 'Replace NotAction with the explicit Action list needed for the task.',
      })
      raise('high')
    }
    if (stmt.notResources.length > 0) {
      findings.push({
        severity: 'high',
        location: `${where}.NotResource`,
        message: `NotResource (${stmt.notResources.join(', ')}) inverts scope — it allows every resource except those listed.`,
        suggestion: 'Replace NotResource with the explicit Resource ARNs from the request.',
      })
      raise('high')
    }
    if (stmt.actions.length === 0 && stmt.notActions.length === 0) {
      findings.push({
        severity: 'medium',
        location: where,
        message: 'Statement has no Action (and no NotAction); its grant cannot be verified as least-privilege.',
        suggestion: 'Add the explicit actions this task requires, or remove the statement.',
      })
      raise('medium')
    }

    for (const action of stmt.actions) {
      if (action === '*') {
        findings.push({
          severity: 'critical',
          location: `${where}.Action`,
          message: 'Full administrative wildcard (`*:*` equivalent) grants every action on every resource.',
          suggestion: 'Scope down to the specific actions named in the request.',
        })
        raise('critical')
        continue
      }
      if (action.includes('*')) {
        findings.push({
          severity: 'high',
          location: `${where}.Action (${action})`,
          message: `Wildcard action "${action}" may cover more than the requested task.`,
          suggestion: 'Replace the wildcard with the exact actions needed.',
        })
        raise('high')
      }
      const escalation = ESCALATION_ACTIONS.find(
        (e) => e.toLowerCase() === action.toLowerCase(),
      )
      if (escalation) {
        findings.push({
          severity: 'high',
          location: `${where}.Action (${action})`,
          message: `"${action}" is a known privilege-escalation primitive (can create or assume broader access).`,
          suggestion: 'Confirm this is required; otherwise remove it and re-synthesize.',
        })
        raise('high')
      }
    }

    const hasSensitiveAction = stmt.actions.some(
      (a) =>
        !READ_ONLY_PREFIXES.some((prefix) => a.toLowerCase().startsWith(prefix.toLowerCase())) &&
        a !== '*',
    )
    for (const resource of stmt.resources) {
      if (resource === '*' && hasSensitiveAction) {
        findings.push({
          severity: 'high',
          location: `${where}.Resource`,
          message: 'Wildcard resource paired with non-read actions — access is broader than one resource.',
          suggestion: 'Scope the resource down to the specific table, bucket, or ARN from the request.',
        })
        raise('high')
      } else if (resource.includes('*')) {
        findings.push({
          severity: 'medium',
          location: `${where}.Resource (${resource})`,
          message: `Partial wildcard resource "${resource}" should be verified against the real ARN.`,
          suggestion: 'Replace with the exact ARN when known.',
        })
        raise('medium')
      }
    }
  }

  return { findings, risk }
}

/** The guardrail may raise the backend risk, never lower it. */
export function combineRisk(backendRisk: RiskLevel, guardrailRisk: RiskLevel): RiskLevel {
  return RISK_ORDER.indexOf(guardrailRisk) > RISK_ORDER.indexOf(backendRisk)
    ? guardrailRisk
    : backendRisk
}

/** One-sentence plain-language summary for users who don't read JSON. */
export function summarizePlainLanguage(policy: PolicyDocument, durationHours: number): string {
  const statements = statementsOf(policy)
  const actions = [...new Set(statements.flatMap((s) => [...s.actions, ...s.notActions.map((a) => `not ${a}`)]))].slice(0, 6)
  const resources = [...new Set(statements.flatMap((s) => [...s.resources, ...s.notResources.map((r) => `not ${r}`)]))].slice(0, 4)
  const actionPart = actions.length > 0 ? actions.join(', ') : 'no actions'
  const resourcePart = resources.length > 0 ? resources.join(', ') : 'no resources'
  return `This grants ${actionPart} on ${resourcePart} for ${durationHours} hour${durationHours === 1 ? '' : 's'}.`
}

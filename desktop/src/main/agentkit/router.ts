/**
 * RouterAgent — intent extraction and dispatcher.
 *
 * Takes task-first user input (free text + optional guided fields) and
 * extracts a structured intent: provider hints, resource references,
 * requested action verbs, duration, and justification. When required fields
 * are missing it returns clarifying questions (max 3) instead of guessing.
 *
 * This module is pure TypeScript with no Node/Electron dependencies so the
 * extraction logic stays unit-testable and portable.
 */

import type { ClarifyQuestion, GuidedContext } from '../../shared/ipc-contract'

export interface Intent {
  /** Combined text actually sent to the synthesis backend. */
  requestText: string
  providerHints: string[]
  resources: string[]
  actionVerbs: string[]
  durationHours: number
  durationExplicit: boolean
  ticket: string | null
}

const DURATION_RE = /(\d+(?:\.\d+)?)\s*(minutes?|mins?|hours?|hrs?|days?)\b/i
const QUOTED_RE = /"([^"]+)"|'([^']+)'|`([^`]+)`/g
const URI_RE = /\b((?:arn:aws:[^\s,;]+)|(s3:\/\/[^\s,;]+))\b/gi
const TICKET_RE = /\b(?:incident|ticket|case|change|jira|ch-?)?\s*#?\s*(\d{2,})\b/i
const ACTION_VERBS = [
  'read',
  'readonly',
  'read-only',
  'write',
  'list',
  'get',
  'put',
  'delete',
  'create',
  'update',
  'invoke',
  'execute',
  'admin',
  'full',
  'debug',
  'inspect',
  'deploy',
  'restart',
  'scale',
  'logs',
]

const PROVIDER_KEYWORDS: Array<[RegExp, string]> = [
  [/\b(s3|bucket)\b/i, 'aws:s3'],
  [/\b(dynamodb|dynamo|table)\b/i, 'aws:dynamodb'],
  [/\b(ec2|instance|ami|ebs)\b/i, 'aws:ec2'],
  [/\b(lambda|function|serverless)\b/i, 'aws:lambda'],
  [/\b(iam|role|policy|user)\b/i, 'aws:iam'],
  [/\b(rds|aurora|postgres|mysql|database)\b/i, 'aws:rds'],
  [/\b(sqs|queue|sns|topic|eventbridge)\b/i, 'aws:messaging'],
  [/\b(cloudwatch|logs|metrics|alarm)\b/i, 'aws:cloudwatch'],
  [/\b(kubernetes|k8s|pod|deployment|clusterrole|namespace)\b/i, 'kubernetes'],
]

function toHours(value: number, unit: string): number {
  const u = unit.toLowerCase()
  if (u.startsWith('min')) return value / 60
  if (u.startsWith('day')) return value * 24
  return value
}

/**
 * Extract a structured intent from free text plus guided fields.
 * Never throws on unstructured input — worst case it returns an intent
 * with empty fields so the caller can ask clarifying questions.
 */
export function extractIntent(freeText: string, guided: GuidedContext): Intent {
  const combined = [freeText, guided.task, guided.resources, guided.ticket]
    .map((s) => s.trim())
    .filter(Boolean)
    .join('\n')

  const resources = new Set<string>()
  for (const m of combined.matchAll(QUOTED_RE)) {
    const value = (m[1] ?? m[2] ?? m[3] ?? '').trim()
    if (value) resources.add(value)
  }
  for (const m of combined.matchAll(URI_RE)) {
    if (m[1]) resources.add(m[1])
  }

  const lowered = combined.toLowerCase()
  const actionVerbs = ACTION_VERBS.filter((verb) => lowered.includes(verb))

  const providerHints = PROVIDER_KEYWORDS.filter(([re]) => re.test(combined)).map(([, hint]) => hint)

  const durationMatch = combined.match(DURATION_RE)
  const durationHours = durationMatch
    ? Math.min(12, Math.max(0.25, toHours(Number(durationMatch[1]), durationMatch[2])))
    : 2

  const ticketMatch = combined.match(TICKET_RE)
  const ticket = ticketMatch ? ticketMatch[0].trim() : guided.ticket.trim() || null

  return {
    requestText: combined,
    providerHints: [...new Set(providerHints)],
    resources: [...resources],
    actionVerbs: [...new Set(actionVerbs)],
    durationHours,
    durationExplicit: durationMatch !== null,
    ticket,
  }
}

/**
 * Decide which clarifying questions (if any) must be answered before
 * synthesis. Returns at most 3 questions, ordered by importance.
 * Answers provided from a previous round suppress re-asking.
 */
export function clarifyingQuestions(
  intent: Intent,
  answers: Record<string, string> = {},
): ClarifyQuestion[] {
  const questions: ClarifyQuestion[] = []

  if (intent.resources.length === 0 && !answers['resources']) {
    questions.push({
      field: 'resources',
      prompt: 'Which resource do you need access to?',
      placeholder: 'e.g. the "billing-reports" S3 bucket',
      suggestion: intent.providerHints[0] ? `Resources for ${intent.providerHints[0]}` : undefined,
    })
  }

  if (intent.actionVerbs.length === 0 && !answers['actions']) {
    questions.push({
      field: 'actions',
      prompt: 'What do you need to do with it?',
      placeholder: 'e.g. read-only for debugging, or list and download objects',
      suggestion: 'read-only',
    })
  }

  if (!intent.durationExplicit && !answers['duration_hours']) {
    questions.push({
      field: 'duration_hours',
      prompt: 'How long do you need access?',
      placeholder: 'e.g. 30 minutes, 2 hours',
      suggestion: '2 hours',
    })
  }

  return questions.slice(0, 3)
}

/** Fold clarification answers back into the request text for synthesis. */
export function applyAnswers(
  intent: Intent,
  answers: Record<string, string>,
): string {
  const extra: string[] = []
  if (answers['resources']) extra.push(`Resources: ${answers['resources'].trim()}`)
  if (answers['actions']) extra.push(`Required actions: ${answers['actions'].trim()}`)
  const durationAnswer = answers['duration_hours']?.trim()
  if (durationAnswer) {
    const m = durationAnswer.match(DURATION_RE)
    extra.push(
      m
        ? `Duration: ${toHours(Number(m[1]), m[2])} hours.`
        : `Duration: ${durationAnswer} (interpret as hours if ambiguous).`,
    )
  }
  if (extra.length === 0) return intent.requestText
  return `${intent.requestText}\n\nClarifications from requester:\n- ${extra.join('\n- ')}`
}

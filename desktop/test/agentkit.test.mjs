import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

// Guardrail + issuance hardening: audit-risk must flag NotAction /
// NotResource scope inversion, and issueCredentials must re-analyze the
// exact renderer-supplied policy, require approval, and clamp duration
// to the guardrail risk ceiling. Runs against compiled output.
const { analyzePolicy } = await import('../dist/main/agentkit/audit-risk.js')
const { activateRequest, generatePolicy, issueCredentials, maxDurationForRisk } = await import('../dist/main/agentkit/index.js')

function stubDeps(captured) {
  return {
    backend: {
      issueCredentials: async (args) => {
        captured.backendArgs = args
        return {
          access_key_id: 'AKIA_TEST',
          secret_access_key: 'secret',
          session_token: 'token',
          expiration: new Date(Date.now() + 3600_000).toISOString(),
          region: 'us-east-1',
        }
      },
    },
    ledger: {
      append: (kind, summary, details) => {
        captured.ledger = { kind, summary, details }
        return 1
      },
    },
  }
}

const readOnlyPolicy = {
  Version: '2012-10-17',
  Statement: [
    {
      Effect: 'Allow',
      Action: ['s3:GetObject'],
      Resource: ['arn:aws:s3:::my-bucket/reports/q3.pdf'],
    },
  ],
}

describe('analyzePolicy NotAction/NotResource', () => {
  it('flags Allow + NotAction at high severity', () => {
    const { findings, risk } = analyzePolicy({
      Version: '2012-10-17',
      Statement: [{ Effect: 'Allow', NotAction: ['iam:*'], Resource: ['*'] }],
    })
    assert.ok(findings.some((f) => f.location.includes('NotAction') && f.severity === 'high'))
    assert.equal(risk, 'high')
  })

  it('flags Allow + NotResource at high severity', () => {
    const { findings, risk } = analyzePolicy({
      Version: '2012-10-17',
      Statement: [
        { Effect: 'Allow', Action: ['s3:GetObject'], NotResource: ['arn:aws:s3:::secret/*'] },
      ],
    })
    assert.ok(findings.some((f) => f.location.includes('NotResource') && f.severity === 'high'))
    assert.equal(risk, 'high')
  })

  it('flags statements with neither Action nor NotAction as at least medium', () => {
    const { findings, risk } = analyzePolicy({
      Version: '2012-10-17',
      Statement: [{ Effect: 'Allow', Resource: ['arn:aws:s3:::my-bucket/*'] }],
    })
    assert.ok(findings.length > 0)
    assert.ok(['medium', 'high', 'critical'].includes(risk))
  })

  it('leaves a scoped read-only policy at low risk', () => {
    const { findings, risk } = analyzePolicy(readOnlyPolicy)
    assert.equal(risk, 'low')
    assert.equal(findings.length, 0)
  })
})

describe('issueCredentials', () => {
  it('throws when approved !== true and never calls the backend', async () => {
    const captured = {}
    const lease = { credentials: null, issuedAt: null }
    await assert.rejects(
      () =>
        issueCredentials(stubDeps(captured), lease, {
          policy: readOnlyPolicy,
          durationHours: 2,
          approved: false,
        }),
      /not been approved/,
    )
    assert.equal(captured.backendArgs, undefined)
    assert.equal(lease.credentials, null)
  })

  it('clamps a tampered high-risk policy to the guardrail ceiling and records it', async () => {
    const captured = {}
    const lease = { credentials: null, issuedAt: null }
    const tampered = {
      Version: '2012-10-17',
      Statement: [{ Effect: 'Allow', Action: ['s3:*'], Resource: ['*'] }],
    }
    await issueCredentials(stubDeps(captured), lease, {
      policy: tampered,
      durationHours: 12,
      approved: true,
    })
    const { risk: guardrailRisk } = analyzePolicy(tampered)
    const ceiling = maxDurationForRisk(guardrailRisk)
    assert.equal(captured.backendArgs.duration, ceiling)
    assert.ok(captured.backendArgs.duration < 12)
    assert.equal(captured.ledger.kind, 'credentials_issued')
    assert.equal(captured.ledger.details.durationHours, ceiling)
    assert.equal(captured.ledger.details.requestedDurationHours, 12)
    assert.equal(captured.ledger.details.guardrailRisk, guardrailRisk)
    assert.ok(captured.ledger.details.findingCount > 0)
    assert.ok(lease.credentials !== null)
  })

  it('leaves scoped read-only policy duration unchanged', async () => {
    const captured = {}
    const lease = { credentials: null, issuedAt: null }
    await issueCredentials(stubDeps(captured), lease, {
      policy: readOnlyPolicy,
      durationHours: 2,
      approved: true,
    })
    assert.equal(captured.backendArgs.duration, 2)
    assert.equal(captured.ledger.details.durationHours, 2)
    assert.equal(captured.ledger.details.findingCount, 0)
  })
})

describe('activateRequest', () => {
  function activateDeps(captured) {
    return {
      backend: {
        activateRequest: async (requestId) => {
          captured.requestId = requestId
          return {
            access_key_id: 'AKIA_TEST',
            secret_access_key: 'secret',
            session_token: 'token',
            expiration: new Date(Date.now() + 3600_000).toISOString(),
            region: 'us-east-1',
          }
        },
      },
      ledger: {
        append: (kind, summary, details) => {
          captured.ledger = { kind, summary, details }
          return 1
        },
      },
    }
  }

  it('activates by request id only and tracks the lease', async () => {
    const captured = {}
    const lease = { credentials: null, issuedAt: null }
    const creds = await activateRequest(activateDeps(captured), lease, 42)
    // No caller-supplied policy or approved flag reaches the backend —
    // approval is enforced server-side from the stored request.
    assert.equal(captured.requestId, 42)
    assert.equal(creds.access_key_id, 'AKIA_TEST')
    assert.ok(lease.credentials !== null)
    assert.ok(lease.issuedAt !== null)
    assert.equal(captured.ledger.kind, 'request_activated')
    assert.equal(captured.ledger.details.requestId, 42)
  })
})

describe('generatePolicy preview units', () => {
  const readUnit = {
    policy: readOnlyPolicy,
    risk: 'low',
    explanation: 'reads',
    approver_note: '',
    label: 'Read part',
    narrative: {},
    duration: 12,
    auto_approved: true,
  }
  const broadWrite = {
    Version: '2012-10-17',
    Statement: [{ Effect: 'Allow', Action: ['iam:CreateUser'], Resource: ['*'] }],
  }
  const writeUnit = {
    policy: broadWrite,
    risk: 'medium',
    explanation: 'writes',
    approver_note: '',
    label: 'Write part',
    narrative: {},
    duration: 4,
    auto_approved: false,
  }

  function previewDeps(captured, units) {
    return {
      backend: {
        previewUnits: async (args) => {
          captured.previewArgs = args
          return units
        },
      },
      ledger: {
        append: (kind, summary, details) => {
          captured.ledger = { kind, summary, details }
          return 7
        },
      },
    }
  }

  const input = {
    freeText: 'Read the reports and manage users for the audit.',
    guided: { task: '', resources: '', ticket: '' },
    provider: 'muse',
    durationHours: 2,
    answers: { resources: 'reports bucket' },
  }

  it('returns every unit so the renderer can consent to a split', async () => {
    const captured = {}
    const out = await generatePolicy(previewDeps(captured, [readUnit, writeUnit]), input)
    assert.equal(out.status, 'policy')
    assert.equal(out.units.length, 2)
    assert.deepEqual(
      out.units.map((u) => u.label),
      ['Read part', 'Write part']
    )
    assert.ok(captured.previewArgs.request_text.length > 0)
    assert.equal(captured.ledger.details.unitCount, 2)
    // The legacy single-grant shape still carries the first unit only.
    assert.equal(out.result.total_units, 2)
  })

  it('raises per-unit guardrail risk without lowering the evaluated risk', async () => {
    const captured = {}
    const out = await generatePolicy(previewDeps(captured, [readUnit, writeUnit]), input)
    // iam:CreateUser on * is not read-only-scoped: guardrail must raise medium.
    const write = out.units.find((u) => u.label === 'Write part')
    assert.ok(['high', 'critical'].includes(write.risk))
    // The scoped read stays low.
    assert.equal(out.units[0].risk, 'low')
  })

  it('throws when the preview returns no grants', async () => {
    const captured = {}
    await assert.rejects(() => generatePolicy(previewDeps(captured, []), input))
  })
})

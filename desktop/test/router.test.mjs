import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

// Regression tests for extractIntent() verb matching: verbs must match on
// word boundaries so "get" does not fire inside "target"/"budget" and "put"
// does not fire inside "input"/"output" (which wrongly suppressed the
// actions clarifying question). Runs against compiled output.
const { clarifyingQuestions, extractIntent } = await import(
  '../dist/main/agentkit/router.js'
)

const BLANK = { task: '', resources: '', ticket: '' }

describe('extractIntent action verbs are word-boundary aware', () => {
  it('"target budget output" yields no action verbs', () => {
    const intent = extractIntent('target budget output', BLANK)
    assert.deepEqual(intent.actionVerbs, [])
  })

  it('"input" and "output" do not match "put"', () => {
    const intent = extractIntent('process the input and output files', BLANK)
    assert.ok(!intent.actionVerbs.includes('put'), intent.actionVerbs.join(','))
  })

  it('"read the logs" still yields read and logs', () => {
    const intent = extractIntent('read the logs', BLANK)
    assert.ok(intent.actionVerbs.includes('read'))
    assert.ok(intent.actionVerbs.includes('logs'))
  })

  it('"read-only" still matches as a hyphenated verb', () => {
    const intent = extractIntent('need read-only access', BLANK)
    assert.ok(intent.actionVerbs.includes('read-only'), intent.actionVerbs.join(','))
  })

  it('"readonly" still matches as a whole token', () => {
    const intent = extractIntent('need readonly access', BLANK)
    assert.ok(intent.actionVerbs.includes('readonly'), intent.actionVerbs.join(','))
  })

  it('verb surrounded by punctuation still matches', () => {
    const intent = extractIntent('please, list objects!', BLANK)
    assert.ok(intent.actionVerbs.includes('list'))
  })
})

describe('clarifyingQuestions actions prompt', () => {
  it('asks the actions question when verbs are only substrings', () => {
    const intent = extractIntent('target budget output', BLANK)
    const fields = clarifyingQuestions(intent).map((q) => q.field)
    assert.ok(fields.includes('actions'))
  })

  it('suppresses the actions question when real verbs are present', () => {
    const intent = extractIntent('read the logs', BLANK)
    const fields = clarifyingQuestions(intent).map((q) => q.field)
    assert.ok(!fields.includes('actions'))
  })
})

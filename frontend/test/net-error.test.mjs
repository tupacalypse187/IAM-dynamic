// Focused regression test for the login "Failed to fetch" complaint:
// network failures must name the server and the next step, never leak
// the raw fetch TypeError. Runs on the stock Node runner, no new deps:
//   npm test
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { describeUnreachable } from '../src/lib/net-error.ts'

describe('describeUnreachable', () => {
  it('names the configured server URL', () => {
    const message = describeUnreachable('http://localhost:8000')
    assert.match(message, /http:\/\/localhost:8000/)
    assert.match(message, /backend is running/)
    assert.doesNotMatch(message, /Failed to fetch/i)
  })

  it('reads sensibly when no base URL is configured', () => {
    const message = describeUnreachable(undefined)
    assert.match(message, /^Cannot reach the server\./)
    assert.match(message, /backend is running/)
  })

  it('treats an empty string like an unset base URL', () => {
    assert.equal(describeUnreachable(''), describeUnreachable(undefined))
  })
})

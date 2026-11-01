import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import { formatRequestRef, matchesRequestQuery } from '../src/lib/request-refs.ts'

function req(overrides = {}) {
  return {
    id: 7,
    requester: 'bob',
    reviewer: 'chad',
    request_text: 'Read-only access to the billing-bucket for invoicing',
    ...overrides,
  }
}

describe('request-refs', () => {
  it('formats zero-padded refs', () => {
    assert.equal(formatRequestRef(7), 'req-00007')
    assert.equal(formatRequestRef(123456), 'req-123456')
  })

  it('matches text, requester, and reviewer', () => {
    assert.equal(matchesRequestQuery(req(), 'billing'), true)
    assert.equal(matchesRequestQuery(req(), 'BOB'), true)
    assert.equal(matchesRequestQuery(req(), 'chad'), true)
    assert.equal(matchesRequestQuery(req(), 'nope'), false)
  })

  it('matches id spellings with or without the req prefix', () => {
    for (const q of ['7', '00007', 'req-7', 'req-00007', 'REQ-00007']) {
      assert.equal(matchesRequestQuery(req(), q), true)
    }
    assert.equal(matchesRequestQuery(req(), '8'), false)
    assert.equal(matchesRequestQuery(req(), 'req-'), false)
  })

  it('matches everything on a blank query', () => {
    assert.equal(matchesRequestQuery(req(), '   '), true)
  })
})

import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

// The helper is TypeScript with a type-only import; strip-types handles it,
// and the @/ alias is resolved by mapping to the relative source path.
import {
  isLiveSession,
  isOpen,
  isTerminal,
  requestExcerpt,
  reviewerDisplay,
} from '../src/lib/requests.ts'

describe('request status helpers', () => {
  it('marks terminal states', () => {
    assert.equal(isTerminal('denied'), true)
    assert.equal(isTerminal('activated'), true)
    assert.equal(isTerminal('discarded'), true)
    assert.equal(isTerminal('approved'), false)
    assert.equal(isTerminal('pending_review'), false)
  })

  it('marks open states awaiting someone', () => {
    assert.equal(isOpen('pending_review'), true)
    assert.equal(isOpen('changes_requested'), true)
    assert.equal(isOpen('approved'), true)
    assert.equal(isOpen('denied'), false)
  })

  it('names the automated system when no human reviewed', () => {
    assert.equal(
      reviewerDisplay({ reviewer: null, auto_approved: true, status: 'approved' }),
      'Automated system',
    )
    assert.equal(
      reviewerDisplay({ reviewer: 'boss', auto_approved: false, status: 'approved' }),
      'boss',
    )
    assert.equal(
      reviewerDisplay({ reviewer: null, auto_approved: false, status: 'pending_review' }),
      'Awaiting reviewer',
    )
  })

  it('detects live vs expired sessions', () => {
    const live = { status: 'activated', credentials_expires_at: new Date(Date.now() + 3600_000).toISOString() }
    const expired = { status: 'activated', credentials_expires_at: new Date(Date.now() - 1000).toISOString() }
    const approved = { status: 'approved', credentials_expires_at: null }
    assert.equal(isLiveSession(live), true)
    assert.equal(isLiveSession(expired), false)
    assert.equal(isLiveSession(approved), false)
  })

  it('excerpts long request text to one line', () => {
    assert.equal(requestExcerpt('short text'), 'short text')
    assert.equal(requestExcerpt('a\nb  c'), 'a b c')
    const long = `x${'y'.repeat(200)}`
    assert.ok(requestExcerpt(long).length <= 120)
    assert.ok(requestExcerpt(long).endsWith('…'))
  })
})

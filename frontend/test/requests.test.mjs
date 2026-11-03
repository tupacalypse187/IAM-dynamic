import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

// The helper is TypeScript with a type-only import; strip-types handles it,
// and the @/ alias is resolved by mapping to the relative source path.
import {
  groupByBatch,
  isLiveSession,
  isOpen,
  isTerminal,
  requestBucket,
  requestExcerpt,
  reviewerDisplay,
} from '../src/lib/requests.ts'

function row(overrides = {}) {
  return {
    id: 1,
    status: 'pending_review',
    grant_expires_at: null,
    ...overrides,
  }
}

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

  it('treats cancelled grants as terminal and closed', () => {
    assert.equal(isTerminal('cancelled'), true)
    assert.equal(isOpen('cancelled'), false)
  })

  it('groups batch units under their shared batch id, newest first', () => {
    const rows = [
      { id: 7, batch_id: 7 },
      { id: 9, batch_id: 8 },
      { id: 8, batch_id: 8 },
    ]
    const groups = groupByBatch(rows)
    assert.equal(groups.length, 2)
    assert.equal(groups[0].batchId, 8)
    assert.deepEqual(groups[0].rows.map((r) => r.id), [9, 8])
    assert.equal(groups[1].batchId, 7)
  })

  it('stands null batch ids alone under their own id', () => {
    const groups = groupByBatch([{ id: 3, batch_id: null }])
    assert.equal(groups.length, 1)
    assert.equal(groups[0].batchId, 3)
  })
})

describe('request buckets', () => {
  const now = Date.parse('2026-11-03T12:00:00Z')

  it('opens reviews and send-backs, never approved grants', () => {
    assert.equal(requestBucket(row({ status: 'pending_review' }), now), 'open')
    assert.equal(requestBucket(row({ status: 'changes_requested' }), now), 'open')
    assert.equal(requestBucket(row({ status: 'approved' }), now), 'active')
  })

  it('keeps usable grants active and lapses only past windows', () => {
    const future = '2026-11-04T00:00:00Z'
    const past = '2026-11-02T00:00:00Z'
    assert.equal(requestBucket(row({ status: 'approved' }), now), 'active')
    assert.equal(requestBucket(row({ status: 'approved', grant_expires_at: future }), now), 'active')
    assert.equal(requestBucket(row({ status: 'approved', grant_expires_at: past }), now), 'expired')
    assert.equal(
      requestBucket(row({ status: 'activated', grant_expires_at: future }), now),
      'active'
    )
    assert.equal(
      requestBucket(row({ status: 'activated', grant_expires_at: past }), now),
      'expired'
    )
  })

  it('expires terminal states', () => {
    for (const status of ['denied', 'discarded', 'cancelled']) {
      assert.equal(requestBucket(row({ status }), now), 'expired')
    }
  })
})

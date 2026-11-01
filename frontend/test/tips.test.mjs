import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import { TIPS, tipFor } from '../src/lib/tips.ts'

describe('tips', () => {
  it('serves a non-empty tip for any date', () => {
    assert.ok(TIPS.length >= 5)
    assert.ok(tipFor(new Date('2026-11-01T12:00:00Z')).length > 0)
  })

  it('is deterministic per day and rotates across days', () => {
    const a = tipFor(new Date('2026-11-01T00:00:00Z'))
    const b = tipFor(new Date('2026-11-01T23:59:59Z'))
    const c = tipFor(new Date('2026-11-02T00:00:00Z'))
    assert.equal(a, b)
    assert.notEqual(a, c)
    assert.ok(TIPS.includes(a) && TIPS.includes(c))
  })
})

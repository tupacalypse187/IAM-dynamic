// Focused regression test for the macOS "smooshed top bar / can't drag"
// complaint: the frameless hiddenInset window puts traffic lights over the
// top-left of the UI, so the renderer must detect macOS-desktop to reserve a
// drag strip — while browsers (no preload bridge) stay untouched.
// Runs on the stock Node runner, no new deps:
//   npm test
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { isMacDesktop } from '../src/lib/desktop.ts'

describe('isMacDesktop', () => {
  it('is false with no preload bridge (browser)', () => {
    assert.equal(isMacDesktop(undefined, 'MacIntel'), false)
  })

  it('is false on non-macOS even with a bridge', () => {
    assert.equal(isMacDesktop({}, 'Win32'), false)
    assert.equal(isMacDesktop({}, ''), false)
  })

  it('is true with a bridge on macOS platform strings', () => {
    assert.equal(isMacDesktop({}, 'MacIntel'), true)
    assert.equal(isMacDesktop({}, 'macOS'), true)
  })
})

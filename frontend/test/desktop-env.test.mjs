// Focused regression test for the macOS "smooshed top bar / can't drag"
// complaint: the frameless hiddenInset window puts traffic lights over the
// top-left of the UI, so the renderer must detect macOS-desktop to reserve a
// drag strip — while browsers (no preload bridge) stay untouched.
// Runs on the stock Node runner, no new deps:
//   npm test
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { isMacDesktop, isMacPlatformString, queryPlatform, resolvePlatform } from '../src/lib/desktop.ts'

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

  it('accepts the main-process darwin platform string', () => {
    assert.equal(isMacDesktop({}, 'darwin'), true)
    assert.equal(isMacPlatformString('darwin'), true)
    assert.equal(isMacPlatformString(null), false)
  })
})

describe('queryPlatform', () => {
  it('reads the main-process platform injection', () => {
    assert.equal(queryPlatform('?platform=darwin'), 'darwin')
    assert.equal(queryPlatform('?platform=win32'), 'win32')
  })

  it('returns null when absent (browsers, tests)', () => {
    assert.equal(queryPlatform(''), null)
    assert.equal(queryPlatform('?other=1'), null)
    assert.equal(queryPlatform(), null)
  })
})

describe('resolvePlatform', () => {
  it('falls through an empty userAgentData platform to navigator.platform', () => {
    // Packaged Electron exposes userAgentData with an EMPTY low-entropy
    // platform (""). A ?? chain keeps "" and macOS goes undetected — the
    // traffic lights then smoosh the sidebar. This is that regression.
    assert.equal(resolvePlatform('', 'MacIntel'), 'MacIntel')
  })

  it('prefers a real userAgentData platform when present', () => {
    assert.equal(resolvePlatform('macOS', 'MacIntel'), 'macOS')
  })

  it('returns empty when nothing is known', () => {
    assert.equal(resolvePlatform(undefined, undefined), '')
    assert.equal(resolvePlatform('', ''), '')
  })
})

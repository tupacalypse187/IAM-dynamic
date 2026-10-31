import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { DEFAULT_PREFS, loadPrefs, savePrefs } from '../src/lib/prefs.ts'

function memStore(initial) {
  const data = { ...initial }
  return {
    getItem: (k) => (k in data ? data[k] : null),
    setItem: (k, v) => {
      data[k] = String(v)
    },
  }
}

describe('prefs', () => {
  it('returns defaults with empty storage', () => {
    assert.deepEqual(loadPrefs(memStore({})), DEFAULT_PREFS)
  })

  it('returns defaults for corrupt or non-object payloads', () => {
    assert.deepEqual(loadPrefs(memStore({ 'iam-prefs-v1': 'not-json' })), DEFAULT_PREFS)
    assert.deepEqual(loadPrefs(memStore({ 'iam-prefs-v1': '[]' })), DEFAULT_PREFS)
  })

  it('merges stored values over defaults and ignores wrong types', () => {
    const stored = loadPrefs(
      memStore({ 'iam-prefs-v1': JSON.stringify({ tooltips: false, tourAutoplay: 'yes' }) }),
    )
    assert.equal(stored.tooltips, false)
    assert.equal(stored.tourAutoplay, DEFAULT_PREFS.tourAutoplay)
    assert.equal(stored.sidebarCollapsed, DEFAULT_PREFS.sidebarCollapsed)
  })

  it('round-trips a partial update', () => {
    const store = memStore({})
    const next = savePrefs({ sidebarCollapsed: true }, store)
    assert.equal(next.sidebarCollapsed, true)
    assert.deepEqual(loadPrefs(store), next)
  })
})

import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import {
  clearViewAsSession,
  loadViewAsSession,
  saveViewAsSession,
} from '../src/lib/view-as.ts'

function memoryStore(initial) {
  const data = { ...(initial ?? {}) }
  return {
    getItem: (k) => (k in data ? data[k] : null),
    setItem: (k, v) => {
      data[k] = v
    },
    removeItem: (k) => {
      delete data[k]
    },
  }
}

const SESSION = { username: 'alice', adminToken: 'admintoken', adminName: 'boss' }

describe('view-as session persistence', () => {
  it('round-trips a session', () => {
    const store = memoryStore()
    saveViewAsSession(SESSION, store)
    assert.deepEqual(loadViewAsSession(store), SESSION)
  })

  it('returns null when nothing is stored', () => {
    assert.equal(loadViewAsSession(memoryStore()), null)
  })

  it('rejects malformed sessions', () => {
    assert.equal(
      loadViewAsSession(memoryStore({ 'iam-view-as': '{"username":"alice"}' })),
      null,
    )
    assert.equal(
      loadViewAsSession(memoryStore({ 'iam-view-as': 'not json' })),
      null,
    )
  })

  it('clears the session on exit', () => {
    const store = memoryStore()
    saveViewAsSession(SESSION, store)
    clearViewAsSession(store)
    assert.equal(loadViewAsSession(store), null)
  })
})

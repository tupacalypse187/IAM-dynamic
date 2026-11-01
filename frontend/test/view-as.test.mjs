import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import {
  clearAdminStash,
  clearViewAsSession,
  isViewAsToken,
  loadAdminStash,
  loadViewAsSession,
  saveAdminStash,
  saveViewAsSession,
} from '../src/lib/view-as.ts'

function fakeJwt(payload) {
  const b64 = Buffer.from(JSON.stringify(payload)).toString('base64url')
  return `header.${b64}.signature`
}

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

  it('round-trips the admin stash for fresh boots', () => {
    const store = memoryStore()
    const stash = { adminToken: 'admintoken', adminName: 'boss', username: 'alice' }
    saveAdminStash(stash, store)
    assert.deepEqual(loadAdminStash(store), stash)
    clearAdminStash(store)
    assert.equal(loadAdminStash(store), null)
  })

  it('detects view-as tokens by claim', () => {
    assert.equal(isViewAsToken(fakeJwt({ sub: 'alice', impersonated_from: 'boss' })), true)
    assert.equal(isViewAsToken(fakeJwt({ sub: 'alice' })), false)
    assert.equal(isViewAsToken(null), false)
    assert.equal(isViewAsToken('not-a-token'), false)
  })
})

import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

// Regression test for the packaged-app blue screen: dev mode must come
// from app.isPackaged, never NODE_ENV (electron-builder leaves NODE_ENV
// unset in releases, which once made every build load the dev server URL).
// Runs against compiled output: `npm test` builds first, so no extra deps.
const { resolveDevMode, loadConfig } = await import('../dist/main/config.js')

describe('resolveDevMode', () => {
  it('packaged app is never dev mode', () => {
    assert.equal(resolveDevMode(true), false)
  })

  it('unpackaged app defaults to dev mode', () => {
    assert.equal(resolveDevMode(false), true)
  })

  it('IAM_DESKTOP_DEV=1 forces dev mode even when packaged', () => {
    assert.equal(resolveDevMode(true, { IAM_DESKTOP_DEV: '1' }), true)
  })

  it('empty override does not force dev mode', () => {
    assert.equal(resolveDevMode(true, { IAM_DESKTOP_DEV: '' }), false)
  })
})

describe('loadConfig', () => {
  it('packaged config points at production defaults', () => {
    const config = loadConfig(true)
    assert.equal(config.isDev, false)
    assert.equal(config.backendUrl, 'http://localhost:8000')
    assert.equal(config.updateFeedUrl, null)
  })

  it('strips trailing slashes from the backend URL', () => {
    process.env.IAM_DESKTOP_BACKEND_URL = 'https://api.example.com///'
    try {
      assert.equal(loadConfig(true).backendUrl, 'https://api.example.com')
    } finally {
      delete process.env.IAM_DESKTOP_BACKEND_URL
    }
  })
})

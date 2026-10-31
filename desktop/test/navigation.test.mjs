import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

// Navigation sandbox for the app window: renderer links must never navigate
// the window itself to an external page (which would keep the preload
// desktopApi bridge, incl. vault token access), and shell.openExternal must
// only ever receive http(s) URLs — never file:, data:, or custom schemes.
// Runs against compiled output: `npm test` builds first, so no extra deps.
const { DEV_URL, isAllowedExternalUrl, isInternalNavigationUrl } = await import(
  '../dist/main/navigation.js'
)

describe('isAllowedExternalUrl', () => {
  it('allows http and https links', () => {
    assert.equal(isAllowedExternalUrl('https://example.com/docs'), true)
    assert.equal(isAllowedExternalUrl('http://example.com/'), true)
  })

  it('denies file, data, and custom-scheme URLs', () => {
    assert.equal(isAllowedExternalUrl('file:///etc/passwd'), false)
    assert.equal(isAllowedExternalUrl('data:text/html,<h1>x</h1>'), false)
    assert.equal(isAllowedExternalUrl('javascript:alert(1)'), false)
    assert.equal(isAllowedExternalUrl('myapp://open?x=1'), false)
  })

  it('denies malformed URLs', () => {
    assert.equal(isAllowedExternalUrl('not a url'), false)
    assert.equal(isAllowedExternalUrl(''), false)
  })
})

describe('isInternalNavigationUrl', () => {
  it('allows the dev server URL and same-origin paths', () => {
    assert.equal(isInternalNavigationUrl(DEV_URL), true)
    assert.equal(isInternalNavigationUrl(`${DEV_URL}/`), true)
    assert.equal(isInternalNavigationUrl(`${DEV_URL}/index.html`), true)
  })

  it('denies lookalike origins that merely prefix-match the dev URL', () => {
    assert.equal(isInternalNavigationUrl(`${DEV_URL}.evil.com/`), false)
    assert.equal(isInternalNavigationUrl('http://localhost:3001/'), false)
  })

  it('allows the packaged file:// bundle index, incl. query/hash variants', () => {
    assert.equal(isInternalNavigationUrl('file:///app/resources/frontend-dist/index.html'), true)
    assert.equal(
      isInternalNavigationUrl('file:///C:/app/resources/frontend-dist/index.html#/request'),
      true,
    )
  })

  it('denies other file:// URLs', () => {
    assert.equal(isInternalNavigationUrl('file:///etc/passwd'), false)
    assert.equal(isInternalNavigationUrl('file:///app/resources/other/page.html'), false)
  })

  it('denies external http(s) pages (caller re-opens those in the browser)', () => {
    assert.equal(isInternalNavigationUrl('https://example.com/'), false)
    assert.equal(isInternalNavigationUrl('http://evil.local/'), false)
  })

  it('denies data: URLs other than the app error page', () => {
    assert.equal(isInternalNavigationUrl('data:text/html,<h1>Could not load the app</h1>'), true)
    assert.equal(isInternalNavigationUrl('data:text/javascript,alert(1)'), false)
  })
})

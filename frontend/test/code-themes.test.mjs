import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import {
  CODE_THEMES,
  CUSTOM_MONACO_THEMES,
  MATCH_CODE_THEME,
  resolveCodeTheme,
} from '../src/lib/code-themes.ts'

describe('code-themes', () => {
  it('resolves match to the stock theme for the app mode', () => {
    assert.equal(resolveCodeTheme('match', true), 'vs-dark')
    assert.equal(resolveCodeTheme('match', false), 'vs')
  })

  it('keeps an explicit known theme regardless of app mode', () => {
    assert.equal(resolveCodeTheme('iam-one-dark', false), 'iam-one-dark')
    assert.equal(resolveCodeTheme('iam-github-light', true), 'iam-github-light')
  })

  it('falls back to match behavior for unknown or empty prefs', () => {
    assert.equal(resolveCodeTheme('nope', true), 'vs-dark')
    assert.equal(resolveCodeTheme('', false), 'vs')
  })

  it('ships theme data for every custom id in the catalog', () => {
    const ids = new Set(CODE_THEMES.map((t) => t.id))
    assert.equal(ids.size, CODE_THEMES.length)
    assert.ok(ids.has(MATCH_CODE_THEME))
    for (const t of CODE_THEMES) {
      if (t.id === MATCH_CODE_THEME || t.id === 'vs' || t.id === 'vs-dark') continue
      const data = CUSTOM_MONACO_THEMES[t.id]
      assert.ok(data, `missing theme data for ${t.id}`)
      assert.ok(data.colors['editor.background'], `no background for ${t.id}`)
      assert.ok(
        data.rules.some((r) => r.token === 'string.key'),
        `no key color for ${t.id}`,
      )
    }
  })
})

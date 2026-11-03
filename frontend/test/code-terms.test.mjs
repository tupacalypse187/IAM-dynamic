import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import { highlightTechnicalTerms } from '../src/lib/code-terms.ts'

describe('highlightTechnicalTerms', () => {
  it('wraps IAM actions in code spans', () => {
    assert.equal(
      highlightTechnicalTerms('Grants s3:ListAllMyBuckets, s3:ListBucket and s3:GetObject.'),
      'Grants `s3:ListAllMyBuckets`, `s3:ListBucket` and `s3:GetObject`.',
    )
  })

  it('wraps ARNs including wildcards', () => {
    assert.equal(
      highlightTechnicalTerms('narrow to arn:aws:s3:::billing-bucket/* please'),
      'narrow to `arn:aws:s3:::billing-bucket/*` please',
    )
  })

  it('leaves plain English and existing code spans alone', () => {
    assert.equal(
      highlightTechnicalTerms('Read-only with no write, delete, or permissions changes.'),
      'Read-only with no write, delete, or permissions changes.',
    )
    assert.equal(
      highlightTechnicalTerms('Use `s3:GetObject` here'),
      'Use `s3:GetObject` here',
    )
    assert.equal(highlightTechnicalTerms('Note: verify scope'), 'Note: verify scope')
  })

  it('passes through text without colons untouched', () => {
    assert.equal(highlightTechnicalTerms('plain words'), 'plain words')
  })

  it('strips quotes the model leaves around code spans', () => {
    assert.equal(
      highlightTechnicalTerms(
        "Grants `'s3:ListAllMyBuckets`', `'s3:ListBucket`' and `'s3:GetObject`'.",
      ),
      'Grants `s3:ListAllMyBuckets`, `s3:ListBucket` and `s3:GetObject`.',
    )
    assert.equal(
      highlightTechnicalTerms('See `"arn:aws:s3:::billing-bucket/*"` for scope'),
      'See `arn:aws:s3:::billing-bucket/*` for scope',
    )
    assert.equal(
      highlightTechnicalTerms("'quoted prose' stays 'as is' with s3:GetObject wrapped"),
      "'quoted prose' stays 'as is' with `s3:GetObject` wrapped",
    )
  })

  it('normalizes typographic quotes around terms', () => {
    assert.equal(
      highlightTechnicalTerms('Grants \u2018`s3:GetObject`\u2019 today'),
      'Grants `s3:GetObject` today',
    )
  })

  it('strips quotes around bare terms (no backticks)', () => {
    assert.equal(highlightTechnicalTerms("'s3:GetObject'"), '`s3:GetObject`')
    assert.equal(
      highlightTechnicalTerms('"arn:aws:s3:::b/*"'),
      '`arn:aws:s3:::b/*`',
    )
    assert.equal(
      highlightTechnicalTerms('Grants \u2018s3:GetObject\u2019 today'),
      'Grants `s3:GetObject` today',
    )
    assert.equal(
      highlightTechnicalTerms('Grants \u201cs3:GetObject\u201d today'),
      'Grants `s3:GetObject` today',
    )
    assert.equal(
      highlightTechnicalTerms("See ('s3:GetObject') now"),
      'See (`s3:GetObject`) now',
    )
    assert.equal(
      highlightTechnicalTerms("See 's3:GetObject', 's3:ListBucket'; now."),
      'See `s3:GetObject`, `s3:ListBucket`; now.',
    )
    assert.equal(
      highlightTechnicalTerms('Scope "arn:aws:s3:::b/*".'),
      'Scope `arn:aws:s3:::b/*`.',
    )
    assert.equal(
      highlightTechnicalTerms("Mixed 's3:GetObject' and s3:ListBucket here"),
      'Mixed `s3:GetObject` and `s3:ListBucket` here',
    )
  })

  it('strips straight quotes outside a complete code span', () => {
    assert.equal(
      highlightTechnicalTerms('Grants \'`s3:GetObject`\' today'),
      'Grants `s3:GetObject` today',
    )
    assert.equal(
      highlightTechnicalTerms('See "`arn:aws:s3:::b/*`" now'),
      'See `arn:aws:s3:::b/*` now',
    )
  })
})

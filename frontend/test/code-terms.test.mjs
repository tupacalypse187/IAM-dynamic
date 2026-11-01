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
})

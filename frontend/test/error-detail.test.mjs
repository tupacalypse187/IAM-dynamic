// Focused regression test for 422 "[object Object]" error messages:
// FastAPI returns `detail` as an ARRAY of { loc, msg } objects for
// validation failures, which must render as joined messages, never
// "[object Object]". Runs on the stock Node runner, no new deps:
//   npm test
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { formatErrorDetail } from '../src/lib/net-error.ts'

describe('formatErrorDetail', () => {
  it('passes a string detail through unchanged', () => {
    assert.equal(formatErrorDetail('Invalid credentials', 'fallback'), 'Invalid credentials')
  })

  it('joins 422 array items by msg with "; " and field prefixes', () => {
    const detail = [
      { loc: ['body', 'duration'], msg: 'Input should be less than or equal to 12', type: 'less_than_equal' },
      { loc: ['body', 'request_text'], msg: 'Field required', type: 'missing' },
    ]
    assert.equal(
      formatErrorDetail(detail, 'fallback'),
      'duration: Input should be less than or equal to 12; request_text: Field required',
    )
  })

  it('never renders "[object Object]" for array details', () => {
    const message = formatErrorDetail(
      [{ loc: ['body', 'x'], msg: 'bad', type: 't' }],
      'fallback',
    )
    assert.doesNotMatch(message, /\[object Object\]/)
  })

  it('omits the loc prefix when loc is body-only, and falls back when empty', () => {
    assert.equal(formatErrorDetail([{ loc: ['body'], msg: 'oops' }], 'fallback'), 'oops')
    assert.equal(formatErrorDetail([], 'fallback'), 'fallback')
    assert.equal(formatErrorDetail(undefined, 'Request failed: 422'), 'Request failed: 422')
    assert.equal(formatErrorDetail('', 'Request failed: 500'), 'Request failed: 500')
  })
})

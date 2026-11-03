/**
 * electron-builder beforePack hook — refuse to pack a stale renderer.
 *
 * predist always rebuilds + stages the renderer, but a direct
 * electron-builder run can bundle an old frontend-dist/ (this shipped
 * before: the packaged app silently lagged the browser with no consent
 * dialog, no split banner, no part chips). Failing here is cheap; finding
 * out from a user is not.
 *
 * Usable two ways:
 *   - electron-builder `beforePack` (receives context, ignored)
 *   - `npm run verify-fresh` for a manual check
 *
 * The check: the staged bundle must contain the current HEAD short sha.
 * build-renderer.mjs bakes `VITE_BUILD_ID = "<sha> · <stamp>"`, so a
 * missing sha means the bundle predates the checkout — rebuild first.
 */
const { execSync } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')

const DESKTOP_ROOT = path.join(__dirname, '..')

function checkFresh(projectDir) {
  const dist = path.join(projectDir, 'frontend-dist')
  const index = path.join(dist, 'index.html')
  if (!fs.existsSync(index)) {
    throw new Error(
      'verify-fresh-renderer: frontend-dist/ is missing — run `npm run copy-renderer` first.'
    )
  }
  let sha
  try {
    sha = execSync('git rev-parse --short HEAD', { cwd: projectDir, encoding: 'utf8' }).trim()
  } catch {
    throw new Error('verify-fresh-renderer: cannot read git HEAD — is this a git checkout?')
  }
  const assets = path.join(dist, 'assets')
  let bundles = []
  try {
    bundles = fs.readdirSync(assets).filter((f) => f.endsWith('.js'))
  } catch {
    throw new Error('verify-fresh-renderer: frontend-dist/assets/ is missing — rebuild the renderer.')
  }
  const haystack = bundles.map((f) => fs.readFileSync(path.join(assets, f), 'utf8')).join('\n')
  if (!haystack.includes(sha)) {
    throw new Error(
      `verify-fresh-renderer: staged renderer predates ${sha} — run \`npm run predist\` (or predist:<platform>) before packaging.`
    )
  }
  return sha
}

exports.default = async function verifyFreshRendererHook() {
  const sha = checkFresh(DESKTOP_ROOT)
  // eslint-disable-next-line no-console
  console.log(`verify-fresh-renderer: staged renderer matches ${sha}.`)
}

if (require.main === module) {
  try {
    const sha = checkFresh(DESKTOP_ROOT)
    // eslint-disable-next-line no-console
    console.log(`verify-fresh-renderer: staged renderer matches ${sha}.`)
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error(err.message)
    process.exit(1)
  }
}

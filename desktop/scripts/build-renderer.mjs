/**
 * Build the renderer for packaging with a guaranteed API base URL.
 *
 * Vite bakes VITE_API_BASE_URL in at build time; a packaged app loading
 * over file:// has no same-origin fallback, so an unset value means every
 * request fails with "Failed to fetch". Default to local dev backend;
 * release builds override via the environment (CodeBuild project setting).
 */
import { execSync, spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

process.env['VITE_API_BASE_URL'] ??= 'http://localhost:8000'

/** Bake a build marker (commit + UTC time) so About can prove which build is running. */
try {
  const sha = execSync('git rev-parse --short HEAD', { encoding: 'utf8' }).trim()
  const stamp = new Date().toISOString().replace('T', ' ').slice(0, 16) + 'Z'
  process.env['VITE_BUILD_ID'] ??= `${sha} · ${stamp}`
} catch {
  process.env['VITE_BUILD_ID'] ??= 'local'
}

const frontendDir = fileURLToPath(new URL('../../frontend', import.meta.url))
const result = spawnSync('npm', ['run', 'build'], {
  cwd: frontendDir,
  stdio: 'inherit',
  shell: true,
  env: process.env,
})
process.exit(result.status ?? 1)

/**
 * Build the renderer for packaging with a guaranteed API base URL.
 *
 * Vite bakes VITE_API_BASE_URL in at build time; a packaged app loading
 * over file:// has no same-origin fallback, so an unset value means every
 * request fails with "Failed to fetch". Default to local dev backend;
 * release builds override via the environment (CodeBuild project setting).
 */
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

process.env['VITE_API_BASE_URL'] ??= 'http://localhost:8000'

const frontendDir = fileURLToPath(new URL('../../frontend', import.meta.url))
const result = spawnSync('npm', ['run', 'build'], {
  cwd: frontendDir,
  stdio: 'inherit',
  shell: true,
  env: process.env,
})
process.exit(result.status ?? 1)

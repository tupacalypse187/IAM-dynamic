/**
 * Build marker baked at renderer build time (desktop/scripts/build-renderer.mjs).
 * Shown in Settings → About so a running app can prove which build it is.
 * Falls back to 'local' under `npm run dev` and plain node test runs.
 */
export const BUILD_ID: string =
  typeof import.meta.env?.VITE_BUILD_ID === 'string' && import.meta.env.VITE_BUILD_ID !== ''
    ? import.meta.env.VITE_BUILD_ID
    : 'local'

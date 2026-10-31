/**
 * OS-native credential vault.
 *
 * JWT session tokens are stored in Keychain (macOS) / Credential Manager
 * (Windows) / Secret Service (Linux) via keytar — never in plaintext
 * files or localStorage. AWS temporary credentials are intentionally NOT
 * persisted: they live only in main-process memory for the lease duration
 * and are dropped on revoke or quit.
 *
 * keytar is loaded lazily so a missing native binding degrades to a
 * clear error instead of crashing startup.
 */

const SERVICE_NAME = 'iam-dynamic-desktop'
const TOKEN_ACCOUNT = 'backend-jwt'

type KeytarModule = typeof import('keytar')

let keytarPromise: Promise<KeytarModule | null> | null = null

function loadKeytar(): Promise<KeytarModule | null> {
  if (!keytarPromise) {
    keytarPromise = import('keytar').then(
      (mod) => mod,
      () => null,
    )
  }
  return keytarPromise
}

async function requireKeytar(): Promise<KeytarModule> {
  const mod = await loadKeytar()
  if (!mod) {
    throw new Error(
      'OS credential store is unavailable (keytar failed to load). ' +
        'Sign-in sessions cannot be persisted on this machine.',
    )
  }
  return mod
}

export const vault = {
  setToken: async (token: string): Promise<void> => {
    const keytar = await requireKeytar()
    await keytar.setPassword(SERVICE_NAME, TOKEN_ACCOUNT, token)
  },

  getToken: async (): Promise<string | null> => {
    const keytar = await loadKeytar()
    if (!keytar) return null
    return keytar.getPassword(SERVICE_NAME, TOKEN_ACCOUNT)
  },

  clearToken: async (): Promise<void> => {
    const keytar = await loadKeytar()
    if (!keytar) return
    await keytar.deletePassword(SERVICE_NAME, TOKEN_ACCOUNT)
  },
}

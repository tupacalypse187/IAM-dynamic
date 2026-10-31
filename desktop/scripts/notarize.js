/**
 * electron-builder afterSign hook — Apple notarization.
 *
 * Runs only when APPLE_ID, APPLE_APP_SPECIFIC_PASSWORD, and APPLE_TEAM_ID
 * are all set; otherwise it logs and skips so local unsigned/ad-hoc
 * builds keep working without credentials on the machine.
 */
const { notarize } = require('@electron/notarize')

exports.default = async function notarizeApp(context) {
  const { electronPlatformName, appOutDir } = context
  if (electronPlatformName !== 'darwin') return

  const appleId = process.env.APPLE_ID
  const appleIdPassword = process.env.APPLE_APP_SPECIFIC_PASSWORD
  const teamId = process.env.APPLE_TEAM_ID
  if (!appleId || !appleIdPassword || !teamId) {
    // eslint-disable-next-line no-console
    console.log('Skipping notarization: APPLE_ID / APPLE_APP_SPECIFIC_PASSWORD / APPLE_TEAM_ID not all set.')
    return
  }

  const appName = context.packager.appInfo.productFilename
  // eslint-disable-next-line no-console
  console.log(`Notarizing ${appName}…`)
  await notarize({
    appPath: `${appOutDir}/${appName}.app`,
    appleId,
    appleIdPassword,
    teamId,
  })
}

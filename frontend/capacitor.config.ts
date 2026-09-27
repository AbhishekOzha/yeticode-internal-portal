import type { CapacitorConfig } from '@capacitor/cli'

// Local development: set CAP_DEV_URL (see `yarn mobile:ios` / `yarn mobile:android`) and the
// app opens the running Vite dev site instead of the built files, with live reload. It stays
// on "localhost", so the microphone (calls, voice messages) is allowed.
const devUrl = process.env.CAP_DEV_URL

const config: CapacitorConfig = {
  appId: 'com.yeticode.portal',
  appName: 'Yeticode Portal',
  webDir: 'dist',
  ...(devUrl ? { server: { url: devUrl, cleartext: true } } : {}),
}

export default config

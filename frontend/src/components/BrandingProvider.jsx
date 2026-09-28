import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { BrandingContext, DEFAULT_BRANDING } from '../branding'

// Loads the company name and logo (public, so the sign-in page has them too)
// and keeps the browser tab's title and icon in step.
export function BrandingProvider({ children }) {
  const [branding, setBranding] = useState(DEFAULT_BRANDING)

  useEffect(() => {
    api
      .branding()
      .then(setBranding)
      .catch(() => {}) // The built-in mark and name are a fine fallback.
  }, [])

  useEffect(() => {
    document.title = branding.name
    const icon = document.querySelector("link[rel='icon']")
    if (!icon) return
    if (branding.logo) {
      icon.removeAttribute('type')
      icon.href = branding.logo
    } else {
      icon.type = 'image/svg+xml'
      icon.href = '/favicon.svg'
    }
  }, [branding])

  const value = useMemo(() => ({ branding, setBranding }), [branding])
  return <BrandingContext.Provider value={value}>{children}</BrandingContext.Provider>
}

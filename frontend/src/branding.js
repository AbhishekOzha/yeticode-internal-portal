import { createContext, useContext } from 'react'

export const DEFAULT_BRANDING = { name: 'Yeticode Innovations', tagline: 'Staff portal', logo: null }

export const BrandingContext = createContext({ branding: DEFAULT_BRANDING, setBranding: () => {} })

export function useBranding() {
  return useContext(BrandingContext)
}

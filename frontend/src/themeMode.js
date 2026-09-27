import { createContext, useContext } from 'react'

export const ThemeModeContext = createContext({ dark: false, toggle: () => {} })

export function useThemeMode() {
  return useContext(ThemeModeContext)
}

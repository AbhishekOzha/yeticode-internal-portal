import { useEffect, useMemo, useState } from 'react'
import { ThemeModeContext } from './themeMode'
import { App as AntApp, ConfigProvider, theme as antTheme } from 'antd'
import { BRAND } from './colors'

const STORAGE_KEY = 'yeticode-theme'

function readStoredMode() {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

function systemPrefersDark() {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
}

export function ThemeProvider({ children }) {
  const [dark, setDark] = useState(() => {
    const stored = readStoredMode()
    return stored ? stored === 'dark' : systemPrefersDark()
  })

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? 'dark' : 'light'
  }, [dark])

  const value = useMemo(
    () => ({
      dark,
      toggle: () =>
        setDark((d) => {
          try {
            localStorage.setItem(STORAGE_KEY, d ? 'light' : 'dark')
          } catch {
            // Storage can be unavailable (private mode); the toggle still works.
          }
          return !d
        }),
    }),
    [dark],
  )

  return (
    <ThemeModeContext.Provider value={value}>
      <ConfigProvider
        theme={{
          algorithm: dark ? antTheme.darkAlgorithm : antTheme.defaultAlgorithm,
          token: {
            colorPrimary: BRAND.primary,
            colorInfo: BRAND.primary,
            borderRadius: 10,
            fontFamily: "'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
            colorBgLayout: dark ? '#0b1020' : '#f4f6fb',
            colorBgContainer: dark ? '#131a2e' : '#ffffff',
          },
          components: {
            Layout: {
              siderBg: '#0f1733',
              headerBg: dark ? '#131a2e' : '#ffffff',
              headerHeight: 68,
              headerPadding: '0 28px',
            },
            Menu: {
              darkItemBg: '#0f1733',
              darkItemSelectedBg: 'rgba(92, 124, 250, 0.22)',
              darkItemSelectedColor: '#ffffff',
              darkItemColor: 'rgba(226, 232, 255, 0.72)',
              itemBorderRadius: 8,
              itemHeight: 44,
            },
            Card: { headerFontSize: 15 },
            Table: { headerBg: dark ? '#182139' : '#f7f8fc', rowHoverBg: dark ? '#18213a' : '#f6f8ff' },
          },
        }}
      >
        <AntApp>{children}</AntApp>
      </ConfigProvider>
    </ThemeModeContext.Provider>
  )
}

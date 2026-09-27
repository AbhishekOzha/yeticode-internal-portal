import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { BrandingProvider } from './components/BrandingProvider'
import { ThemeProvider } from './theme'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ThemeProvider>
      <BrandingProvider>
        <App />
      </BrandingProvider>
    </ThemeProvider>
  </StrictMode>,
)

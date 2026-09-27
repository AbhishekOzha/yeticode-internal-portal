// Brand mark: two snow-capped peaks inside a rounded tile.
export function LogoMark({ size = 36 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" role="img" aria-label="Yeticode Innovations">
      <defs>
        <linearGradient id="yc-tile" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#5c7cfa" />
          <stop offset="1" stopColor="#22a6c9" />
        </linearGradient>
      </defs>
      <rect width="40" height="40" rx="11" fill="url(#yc-tile)" />
      <path d="M6 30 L16 13 L22 23 L26 17 L34 30 Z" fill="#ffffff" fillOpacity="0.92" />
      <path d="M16 13 L19.2 18.4 L17.4 17.4 L16 19.2 L14.4 17.6 L12.9 18.3 Z" fill="#1e2a78" fillOpacity="0.55" />
    </svg>
  )
}

export function Logo({ collapsed = false, light = true }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <LogoMark />
      {!collapsed && (
        <div style={{ lineHeight: 1.1, color: light ? '#fff' : 'inherit' }}>
          <div style={{ fontWeight: 700, fontSize: 17, letterSpacing: '-0.01em' }}>Yeticode</div>
          <div style={{ fontSize: 11, opacity: 0.65, letterSpacing: '0.14em', textTransform: 'uppercase' }}>
            Innovations
          </div>
        </div>
      )}
    </div>
  )
}

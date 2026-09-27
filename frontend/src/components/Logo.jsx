import { useBranding } from '../branding'

// The uploaded company logo, or the built-in mark: two snow-capped peaks inside a rounded tile.
export function LogoMark({ size = 36 }) {
  const { branding } = useBranding()
  if (branding.logo) {
    return (
      <img
        src={branding.logo}
        alt={branding.name}
        width={size}
        height={size}
        style={{ borderRadius: size * 0.28, objectFit: 'contain', background: '#fff', flexShrink: 0 }}
      />
    )
  }
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" role="img" aria-label={branding.name} style={{ flexShrink: 0 }}>
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

// First word large, the rest small and spaced, e.g. "Yeticode / INNOVATIONS".
export function Logo({ collapsed = false, light = true }) {
  const { branding } = useBranding()
  const [first, ...rest] = branding.name.trim().split(/\s+/)
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
      <LogoMark />
      {!collapsed && (
        <div style={{ lineHeight: 1.1, color: light ? '#fff' : 'inherit', minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 17, letterSpacing: '-0.01em' }}>{first}</div>
          {rest.length > 0 && (
            <div
              style={{
                fontSize: 11,
                opacity: 0.65,
                letterSpacing: '0.14em',
                textTransform: 'uppercase',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {rest.join(' ')}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

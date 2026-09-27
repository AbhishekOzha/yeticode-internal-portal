export const BRAND = {
  primary: '#3451d1',
  ink: '#0f172a',
  gradient: 'linear-gradient(135deg, #1e2a78 0%, #3451d1 55%, #22a6c9 100%)',
}

// One colour per unit, used for tags, avatars and accents everywhere.
export const UNIT_COLORS = {
  web: { color: '#3451d1', tag: 'geekblue', soft: 'rgba(52, 81, 209, 0.12)' },
  training: { color: '#0f9d76', tag: 'green', soft: 'rgba(15, 157, 118, 0.12)' },
  content: { color: '#8b3fd9', tag: 'purple', soft: 'rgba(139, 63, 217, 0.12)' },
  all: { color: '#c47f00', tag: 'gold', soft: 'rgba(196, 127, 0, 0.14)' },
}

export function unitColor(code) {
  return UNIT_COLORS[code] ?? UNIT_COLORS.all
}

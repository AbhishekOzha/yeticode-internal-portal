const AVATAR_COLORS = ['#3451d1', '#0f9d76', '#8b3fd9', '#d9480f', '#0b7285', '#c2255c', '#5f3dc4', '#2b8a3e']

export function initials(name) {
  const parts = (name || '?').trim().split(/[\s@._-]+/).filter(Boolean)
  return ((parts[0]?.[0] ?? '?') + (parts.length > 1 ? parts[1][0] : '')).toUpperCase()
}

export function colorFor(text) {
  let hash = 0
  for (const ch of text || '') hash = (hash * 31 + ch.charCodeAt(0)) >>> 0
  return AVATAR_COLORS[hash % AVATAR_COLORS.length]
}

export function displayName(person) {
  return person.full_name || `${person.first_name ?? ''} ${person.last_name ?? ''}`.trim() || person.email || person.username
}

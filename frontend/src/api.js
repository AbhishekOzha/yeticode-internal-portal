function getCookie(name) {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : null
}

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `Request failed (${status})`)
    this.status = status
  }
}

async function request(path, { method = 'GET', body } = {}) {
  const headers = { Accept: 'application/json' }
  if (method !== 'GET') {
    headers['Content-Type'] = 'application/json'
    headers['X-CSRFToken'] = getCookie('csrftoken') ?? ''
  }
  const response = await fetch(`/api${path}`, {
    method,
    headers,
    credentials: 'same-origin',
    body: body ? JSON.stringify(body) : undefined,
  })
  if (response.status === 204) return null
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new ApiError(response.status, data.detail)
  return data
}

export const api = {
  ensureCsrf: () => request('/auth/csrf/'),
  me: () => request('/auth/me/'),
  login: (username, password) =>
    request('/auth/login/', { method: 'POST', body: { username, password } }),
  logout: () => request('/auth/logout/', { method: 'POST' }),
  unitMembers: () => request('/unit/members/'),
}

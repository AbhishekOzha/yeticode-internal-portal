function getCookie(name) {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : null
}

// Turns a DRF error body ({"detail": ...} or {"field": ["msg"]}) into readable text.
function describeError(data) {
  if (!data || typeof data !== 'object') return ''
  if (data.detail) return data.detail
  return Object.entries(data)
    .map(([field, messages]) => {
      const text = [].concat(messages).join(' ')
      return field === 'non_field_errors' ? text : `${field.replaceAll('_', ' ')}: ${text}`
    })
    .join(' ')
}

export class ApiError extends Error {
  constructor(status, data) {
    super(describeError(data) || `Request failed (${status})`)
    this.status = status
    this.data = data
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
  if (!response.ok) throw new ApiError(response.status, data)
  return data
}

export const api = {
  ensureCsrf: () => request('/auth/csrf/'),
  me: () => request('/auth/me/'),
  login: (username, password) =>
    request('/auth/login/', { method: 'POST', body: { username, password } }),
  logout: () => request('/auth/logout/', { method: 'POST' }),
  unitMembers: () => request('/unit/members/'),
  companyMembers: () => request('/company/members/'),

  listUsers: () => request('/manage/users/'),
  createUser: (data) => request('/manage/users/', { method: 'POST', body: data }),
  updateUser: (id, data) => request(`/manage/users/${id}/`, { method: 'PATCH', body: data }),
  listRoles: () => request('/manage/roles/'),
  updateRole: (id, data) => request(`/manage/roles/${id}/`, { method: 'PATCH', body: data }),
  listCapabilities: () => request('/manage/capabilities/'),
}

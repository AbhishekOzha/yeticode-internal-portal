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

// A FormData body is sent as multipart (for file uploads); anything else as JSON.
async function request(path, { method = 'GET', body } = {}) {
  const headers = { Accept: 'application/json' }
  const multipart = body instanceof FormData
  if (method !== 'GET') {
    if (!multipart) headers['Content-Type'] = 'application/json'
    headers['X-CSRFToken'] = getCookie('csrftoken') ?? ''
  }
  const response = await fetch(`/api${path}`, {
    method,
    headers,
    credentials: 'same-origin',
    body: body ? (multipart ? body : JSON.stringify(body)) : undefined,
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
  branding: () => request('/branding/'),
  updateProfile: (data) => request('/profile/', { method: 'PATCH', body: data }),
  unitMembers: () => request('/unit/members/'),
  companyMembers: () => request('/company/members/'),

  listUsers: () => request('/manage/users/'),
  createUser: (data) => request('/manage/users/', { method: 'POST', body: data }),
  updateUser: (id, data) => request(`/manage/users/${id}/`, { method: 'PATCH', body: data }),
  listRoles: () => request('/manage/roles/'),
  updateRole: (id, data) => request(`/manage/roles/${id}/`, { method: 'PATCH', body: data }),
  listCapabilities: () => request('/manage/capabilities/'),
  payrollStaff: (month) => request(`/payroll/staff/?month=${month}`),
  updateStaffPay: (id, month, data) => request(`/payroll/staff/${id}/?month=${month}`, { method: 'PATCH', body: data }),
  dailyLog: (id, month) => request(`/payroll/staff/${id}/daily/?month=${month}`),
  saveDailyLog: (id, month, days) =>
    request(`/payroll/staff/${id}/daily/?month=${month}`, { method: 'PUT', body: { days } }),
  payrollExtras: (month) => request(`/payroll/extras/?month=${month}`),
  addPayExtra: (data) => request('/payroll/extras/', { method: 'POST', body: data }),
  deletePayExtra: (id) => request(`/payroll/extras/${id}/`, { method: 'DELETE' }),
  companySettings: () => request('/manage/company/'),
  updateCompanySettings: (data) => request('/manage/company/', { method: 'PATCH', body: data }),
}

// Wraps a single file in FormData for an upload field such as `avatar` or `logo`.
export function fileForm(field, file) {
  const data = new FormData()
  data.append(field, file)
  return data
}

export const teamApi = {
  officeHours: () => request('/team/office-hours/'),
  saveOfficeHours: (id, data) => request(`/team/office-hours/${id}/`, { method: 'PUT', body: data }),
  clearOfficeHours: (id) => request(`/team/office-hours/${id}/`, { method: 'DELETE' }),
  myOfficeHours: () => request('/team/office-hours/me/'),
  chatContacts: () => request('/chat/contacts/'),
  chatMessages: (withId, { after, before } = {}) => {
    const params = new URLSearchParams({ with: withId })
    if (after) params.set('after', after)
    if (before) params.set('before', before)
    return request(`/chat/messages/?${params}`)
  },
  sendChat: (to, body) => request('/chat/messages/', { method: 'POST', body: { to: to === 'team' ? null : Number(to), body } }),
  sendVoice: (to, blob, duration, extension) => {
    const data = new FormData()
    if (to !== 'team') data.append('to', to)
    data.append('audio', blob, `voice.${extension}`)
    data.append('duration', String(Math.round(duration)))
    return request('/chat/messages/', { method: 'POST', body: data })
  },
  sendFile: (to, file, body = '') => {
    const data = new FormData()
    if (to !== 'team') data.append('to', to)
    data.append('file', file, file.name)
    if (body) data.append('body', body)
    return request('/chat/messages/', { method: 'POST', body: data })
  },
  markChatRead: (withId, lastId) => request('/chat/read/', { method: 'POST', body: { with: withId, last_id: lastId } }),
  reviewPeople: (month) => request(`/team/reviews/people/?month=${month}`),
  writeReview: (data) => request('/team/reviews/', { method: 'POST', body: data }),
  withdrawReview: (id) => request(`/team/reviews/${id}/`, { method: 'DELETE' }),
  reviewSummary: (month) => request(`/team/reviews/summary/?month=${month}`),
  chatUpdates: (after) => request(`/chat/updates/${after ? `?after=${after}` : ''}`),
}

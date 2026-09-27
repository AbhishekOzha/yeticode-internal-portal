// Payroll covers the Academic Content Writing unit only.
export const PAYROLL_UNIT = 'content'

export function canManagePayroll(user) {
  return user.is_super_admin || (user.unit?.code === PAYROLL_UNIT && user.capabilities.includes('manage_payroll'))
}

export const EXTRA_KINDS = {
  words: { label: 'Extra task (words)', short: 'Words', color: 'purple', unit: 'words' },
  hours: { label: 'Extra task (hours)', short: 'Hours', color: 'geekblue', unit: 'hours' },
  performance: { label: 'Performance', short: 'Performance', color: 'green' },
  effort: { label: 'Effort', short: 'Effort', color: 'gold' },
}

export function npr(value) {
  if (value === null || value === undefined || value === '') return '—'
  return `NPR ${Number(value).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}

export function count(value) {
  return Number(value).toLocaleString('en-IN', { maximumFractionDigits: 2 })
}

// Same formula as the server: 3,000 words at "6,000 words = NPR 1,000" is NPR 500.
export function rateAmount(quantity, perQuantity, perAmount) {
  const q = Number(quantity)
  const per = Number(perQuantity)
  const amount = Number(perAmount)
  if (!q || !per || Number.isNaN(amount)) return null
  return Math.round(((q * amount) / per) * 100) / 100
}

// Today's date as YYYY-MM-DD in the browser's time zone (not UTC).
export function todayISO() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

export function currentMonth() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

export function shiftMonth(month, delta) {
  const [year, m] = month.split('-').map(Number)
  const date = new Date(year, m - 1 + delta, 1)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
}

export function monthLabel(month) {
  const [year, m] = month.split('-').map(Number)
  return new Date(year, m - 1, 1).toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
}

export function monthBounds(month) {
  const [year, m] = month.split('-').map(Number)
  const last = new Date(year, m, 0).getDate()
  return { min: `${month}-01`, max: `${month}-${String(last).padStart(2, '0')}` }
}

// Every day of a month as YYYY-MM-DD strings.
export function daysOf(month) {
  const { max } = monthBounds(month)
  const last = Number(max.slice(-2))
  return Array.from({ length: last }, (_, i) => `${month}-${String(i + 1).padStart(2, '0')}`)
}

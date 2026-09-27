import { createContext, useContext } from 'react'

// Office hours and team chat are for the Academic Content Writing unit only.
export const TEAM_UNIT = 'content'
const MANAGER_CAPABILITIES = ['manage_payroll', 'manage_employee_records', 'manage_unit_users']

export function inTeam(user) {
  return !user.is_super_admin && user.unit?.code === TEAM_UNIT
}

export function canManageOfficeHours(user) {
  return user.is_super_admin || (inTeam(user) && MANAGER_CAPABILITIES.some((c) => user.capabilities.includes(c)))
}

// Super Admins, and the unit's HR and Production Manager, read colleague reviews.
export function canReadReviews(user) {
  return (
    user.is_super_admin ||
    (inTeam(user) && ['manage_employee_records', 'manage_unit_users'].some((c) => user.capabilities.includes(c)))
  )
}

// Python weekday numbers: Monday = 0. Listed Sunday first, as the office week starts on Sunday.
export const WEEKDAYS = [
  { value: 6, label: 'Sun' },
  { value: 0, label: 'Mon' },
  { value: 1, label: 'Tue' },
  { value: 2, label: 'Wed' },
  { value: 3, label: 'Thu' },
  { value: 4, label: 'Fri' },
  { value: 5, label: 'Sat' },
]
export const DEFAULT_WORK_DAYS = [6, 0, 1, 2, 3, 4]

export const SHIFT_PRESETS = [
  { key: '07-15', label: '7 AM – 3 PM', start: '07:00', end: '15:00' },
  { key: '09-17', label: '9 AM – 5 PM', start: '09:00', end: '17:00' },
  { key: '10-18', label: '10 AM – 6 PM', start: '10:00', end: '18:00' },
]

// Reminders before the shift starts, and before it ends.
export const START_REMINDERS = [30, 15, 5]
export const END_REMINDER = 5

export function toMinutes(hhmm) {
  const [h, m] = hhmm.split(':').map(Number)
  return h * 60 + m
}

export function formatTime(hhmm) {
  const [h, m] = hhmm.split(':').map(Number)
  return new Date(2000, 0, 1, h, m).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
}

export function shiftLabel(hours) {
  return `${formatTime(hours.start_time)} – ${formatTime(hours.end_time)}`
}

export function daysLabel(days) {
  const set = new Set(days)
  if (set.size === 7) return 'Every day'
  if (set.size === 6 && !set.has(5)) return 'Sun – Fri'
  if (set.size === 5 && !set.has(5) && !set.has(6)) return 'Mon – Fri'
  return WEEKDAYS.filter((d) => set.has(d.value)).map((d) => d.label).join(', ')
}

// The current date, weekday (Monday = 0) and minute of the day in the office's time zone.
export function nowIn(timeZone) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-US', {
      timeZone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      weekday: 'short',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
    })
      .formatToParts(new Date())
      .map((p) => [p.type, p.value]),
  )
  const weekday = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].indexOf(parts.weekday)
  return {
    date: `${parts.year}-${parts.month}-${parts.day}`,
    weekday,
    minutes: Number(parts.hour) * 60 + Number(parts.minute),
  }
}

// Shared chat state: unread counts from the poller, and which conversation is on screen.
export const ChatContext = createContext({
  enabled: false,
  unread: {},
  totalUnread: 0,
  version: 0,
  active: null,
  setActive: () => {},
  refresh: () => {},
})

export function useChat() {
  return useContext(ChatContext)
}

// 'team' for the team room, otherwise the colleague's id as a string.
export function conversationOf(message, meId) {
  if (message.recipient === null) return 'team'
  return String(message.sender === meId ? message.recipient : message.sender)
}

export function formatDuration(seconds) {
  const s = Math.max(0, Math.round(seconds || 0))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

// What a message says in previews and notifications.
export function messageText(message) {
  if (message.body) return message.body
  if (message.audio) return `🎤 Voice message${message.audio_duration ? ` (${formatDuration(message.audio_duration)})` : ''}`
  return ''
}

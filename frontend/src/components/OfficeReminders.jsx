import { useEffect, useState } from 'react'
import { App } from 'antd'
import { teamApi } from '../api'
import { desktopNotify, firstTimeToday } from '../notify'
import { END_REMINDER, START_REMINDERS, formatTime, inTeam, nowIn, toMinutes } from '../team'

const CHECK_MS = 20000
const RELOAD_MS = 10 * 60 * 1000

// Reminds the signed-in person 30, 15 and 5 minutes before their shift starts
// and 5 minutes before it ends, while the app is open in a browser tab.
export function OfficeReminders({ user }) {
  const enabled = inTeam(user)
  const { notification } = App.useApp()
  const [shift, setShift] = useState(null)

  useEffect(() => {
    if (!enabled) return
    const load = () =>
      teamApi
        .myOfficeHours()
        .then(setShift)
        .catch(() => {})
    load()
    const timer = setInterval(load, RELOAD_MS)
    return () => clearInterval(timer)
  }, [enabled])

  useEffect(() => {
    const hours = shift?.office_hours
    if (!hours || !hours.reminders) return
    const start = toMinutes(hours.start_time)
    const end = toMinutes(hours.end_time)
    const reminders = [
      ...START_REMINDERS.map((before) => ({
        key: `start-${before}`,
        at: start - before,
        title: `Office starts in ${before} minutes`,
        body: `Your shift starts at ${formatTime(hours.start_time)}.`,
      })),
      {
        key: `end-${END_REMINDER}`,
        at: end - END_REMINDER,
        title: `Your shift ends in ${END_REMINDER} minutes`,
        body: `Log-out time is ${formatTime(hours.end_time)}. Time to wrap up.`,
      },
    ]

    const check = () => {
      const now = nowIn(shift.time_zone)
      if (!hours.work_days.includes(now.weekday)) return
      for (const r of reminders) {
        // Fire during the reminder's minute (or up to a minute late if the tab was asleep).
        if (now.minutes < r.at || now.minutes > r.at + 1) continue
        if (!firstTimeToday(`${user.id}-${now.date}-${r.key}-${hours.start_time}-${hours.end_time}`)) continue
        notification.info({ key: r.key, title: r.title, description: r.body, placement: 'topRight', duration: 20 })
        desktopNotify(r.title, { body: r.body, tag: `office-${r.key}` })
      }
    }
    check()
    const timer = setInterval(check, CHECK_MS)
    return () => clearInterval(timer)
  }, [shift, notification, user.id])

  return null
}

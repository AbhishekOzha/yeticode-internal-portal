// Desktop notifications, when the browser supports them and the person allowed them.
export function notificationsSupported() {
  return typeof window !== 'undefined' && 'Notification' in window
}

export function notificationPermission() {
  return notificationsSupported() ? Notification.permission : 'unsupported'
}

export async function requestNotifications() {
  if (!notificationsSupported()) return 'unsupported'
  return Notification.requestPermission()
}

export function desktopNotify(title, { body, icon, tag, onClick } = {}) {
  if (notificationPermission() !== 'granted') return
  try {
    const n = new Notification(title, { body, icon: icon || undefined, tag })
    n.onclick = () => {
      window.focus()
      onClick?.()
      n.close()
    }
  } catch {
    // Some browsers only allow notifications from a service worker; the in-app message still shows.
  }
}

// Remembers a reminder was shown today, so a reload or a second tab doesn't repeat it.
export function firstTimeToday(key) {
  const storageKey = `yc-reminded-${key}`
  try {
    if (localStorage.getItem(storageKey)) return false
    localStorage.setItem(storageKey, '1')
  } catch {
    // Without storage the reminder may repeat in another tab; that's acceptable.
  }
  return true
}

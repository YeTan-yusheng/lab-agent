import { ref } from 'vue'
import { getToken } from '@/utils/auth'
import { getNotificationUnreadCount } from '@/api/notification'

const unreadCount = ref(0)
let pollTimer = null
let subscribers = 0

async function refresh() {
  if (!getToken()) {
    unreadCount.value = 0
    return
  }

  try {
    const res = await getNotificationUnreadCount()
    if (res.code === 200) {
      unreadCount.value = res.data?.count ?? 0
    }
  } catch {}
}

function tick() {
  if (typeof document !== 'undefined' && document.hidden) return
  refresh()
}

export function useNotificationCount() {
  const startPolling = () => {
    subscribers += 1
    if (pollTimer) return
    pollTimer = setInterval(tick, 60_000)
    refresh()
  }

  const stopPolling = () => {
    subscribers = Math.max(0, subscribers - 1)
    if (subscribers === 0 && pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  return { unreadCount, refresh, startPolling, stopPolling }
}

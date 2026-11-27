import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  getToken: vi.fn(),
  getNotificationUnreadCount: vi.fn()
}))

vi.mock('@/utils/auth', () => ({
  getToken: mocks.getToken
}))

vi.mock('@/api/notification', () => ({
  getNotificationUnreadCount: mocks.getNotificationUnreadCount
}))

import { useNotificationCount } from '@/composables/useNotificationCount'

describe('useNotificationCount', () => {
  beforeEach(() => {
    mocks.getToken.mockReset()
    mocks.getNotificationUnreadCount.mockReset()
    vi.useRealTimers()
  })

  it('没有 token 时不请求并清零', async () => {
    mocks.getToken.mockReturnValue(null)
    const { unreadCount, refresh } = useNotificationCount()
    unreadCount.value = 3

    await refresh()

    expect(unreadCount.value).toBe(0)
    expect(mocks.getNotificationUnreadCount).not.toHaveBeenCalled()
  })

  it('加载未读数量', async () => {
    mocks.getToken.mockReturnValue('token')
    mocks.getNotificationUnreadCount.mockResolvedValue({
      code: 200,
      data: { count: 4 }
    })
    const { unreadCount, refresh } = useNotificationCount()

    await refresh()

    expect(unreadCount.value).toBe(4)
  })

  it('请求失败保留旧值且不抛错', async () => {
    mocks.getToken.mockReturnValue('token')
    mocks.getNotificationUnreadCount.mockRejectedValue(new Error('network'))
    const { unreadCount, refresh } = useNotificationCount()
    unreadCount.value = 5

    await expect(refresh()).resolves.toBeUndefined()
    expect(unreadCount.value).toBe(5)
  })

  it('startPolling 立即刷新并按 60 秒轮询，stopPolling 停止', async () => {
    vi.useFakeTimers()
    mocks.getToken.mockReturnValue('token')
    mocks.getNotificationUnreadCount.mockResolvedValue({
      code: 200,
      data: { count: 2 }
    })
    const { startPolling, stopPolling } = useNotificationCount()

    startPolling()
    await Promise.resolve()
    await Promise.resolve()
    expect(mocks.getNotificationUnreadCount).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(60_000)
    expect(mocks.getNotificationUnreadCount).toHaveBeenCalledTimes(2)

    stopPolling()
    await vi.advanceTimersByTimeAsync(60_000)
    expect(mocks.getNotificationUnreadCount).toHaveBeenCalledTimes(2)
  })
})
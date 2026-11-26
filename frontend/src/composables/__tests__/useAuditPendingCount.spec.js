import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  can: vi.fn(),
  getAuditPendingCountApi: vi.fn()
}))

vi.mock('@/utils/user', () => ({
  useUser: () => ({ can: mocks.can })
}))

vi.mock('@/api/reservation', () => ({
  getAuditPendingCountApi: mocks.getAuditPendingCountApi
}))

import { useAuditPendingCount } from '@/composables/useAuditPendingCount'

describe('useAuditPendingCount', () => {
  beforeEach(() => {
    mocks.can.mockReset()
    mocks.getAuditPendingCountApi.mockReset()
  })

  it('不做无审核能力用户的请求', async () => {
    mocks.can.mockReturnValue(false)
    const { pendingCount, refresh } = useAuditPendingCount()

    await refresh()

    expect(pendingCount.value).toBe(0)
    expect(mocks.getAuditPendingCountApi).not.toHaveBeenCalled()
  })

  it('加载审核人的待审核角标', async () => {
    mocks.can.mockReturnValue(true)
    mocks.getAuditPendingCountApi.mockResolvedValue({
      code: 200,
      data: { count: 3 }
    })
    const { pendingCount, refresh } = useAuditPendingCount()

    await refresh()

    expect(pendingCount.value).toBe(3)
    expect(mocks.getAuditPendingCountApi).toHaveBeenCalledTimes(1)
  })

  it('请求失败不抛错', async () => {
    mocks.can.mockReturnValue(true)
    mocks.getAuditPendingCountApi.mockRejectedValue(new Error('network'))
    const { pendingCount, refresh } = useAuditPendingCount()

    await expect(refresh()).resolves.toBeUndefined()
    expect(pendingCount.value).toBe(3)
  })
})
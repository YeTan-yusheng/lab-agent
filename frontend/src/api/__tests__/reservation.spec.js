import { beforeEach, describe, expect, it, vi } from 'vitest'

const { requestMock } = vi.hoisted(() => ({
  requestMock: vi.fn()
}))

vi.mock('@/utils/request', () => ({
  default: requestMock
}))

import {
  auditReservationApi,
  cancelReservationApi,
  getAuditHistoryApi,
  getAuditPendingCountApi,
  getReservationHistoryApi
} from '@/api/reservation'

describe('reservation API 协议', () => {
  beforeEach(() => {
    requestMock.mockReset()
    requestMock.mockResolvedValue({ code: 200 })
  })

  it('取消接口支持空 body 和强制取消参数', async () => {
    await cancelReservationApi(7)
    expect(requestMock).toHaveBeenLastCalledWith({
      url: '/api/reservation/7/cancel',
      method: 'put',
      data: {}
    })

    await cancelReservationApi(7, { force: true, reason: '设备故障' })
    expect(requestMock).toHaveBeenLastCalledWith({
      url: '/api/reservation/7/cancel',
      method: 'put',
      data: { force: true, reason: '设备故障' }
    })
  })

  it('审核接口发送拒绝原因和自审标记', async () => {
    await auditReservationApi(9, {
      status: 2,
      reject_reason: '不符合要求',
      self_audit: false
    })

    expect(requestMock).toHaveBeenLastCalledWith({
      url: '/api/reservation/9/audit',
      method: 'put',
      data: {
        status: 2,
        reject_reason: '不符合要求',
        self_audit: false
      }
    })
  })

  it('审核接口兼容旧的 status 数字参数', async () => {
    await auditReservationApi(9, 1)

    expect(requestMock).toHaveBeenLastCalledWith({
      url: '/api/reservation/9/audit',
      method: 'put',
      data: { status: 1 }
    })
  })

  it('提供历史与待审核数量接口', async () => {
    await getReservationHistoryApi(3)
    expect(requestMock).toHaveBeenLastCalledWith({
      url: '/api/reservation/3/history',
      method: 'get'
    })

    await getAuditPendingCountApi()
    expect(requestMock).toHaveBeenLastCalledWith({
      url: '/api/reservation/audit/pending-count',
      method: 'get'
    })
  })

  it('提供跨预约审计历史接口', async () => {
    const params = { page: 1, page_size: 10, action: 'approve' }
    await getAuditHistoryApi(params)

    expect(requestMock).toHaveBeenLastCalledWith({
      url: '/api/reservation/audit/history',
      method: 'get',
      params
    })
  })
})

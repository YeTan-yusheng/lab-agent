import { beforeEach, describe, expect, it, vi } from 'vitest'

const { requestMock } = vi.hoisted(() => ({
  requestMock: vi.fn()
}))

vi.mock('@/utils/request', () => ({
  default: requestMock
}))

import {
  getNotificationList,
  getNotificationUnreadCount,
  markAllNotificationsRead,
  markNotificationRead
} from '@/api/notification'

describe('notification API 协议', () => {
  beforeEach(() => {
    requestMock.mockReset()
    requestMock.mockResolvedValue({ code: 200 })
  })

  it('列表使用分页和已读筛选参数', async () => {
    await getNotificationList({ page: 1, page_size: 10, is_read: false })

    expect(requestMock).toHaveBeenLastCalledWith({
      url: '/api/notification/list',
      method: 'get',
      params: { page: 1, page_size: 10, is_read: false }
    })
  })

  it('未读数接口路径正确', async () => {
    await getNotificationUnreadCount()

    expect(requestMock).toHaveBeenLastCalledWith({
      url: '/api/notification/unread-count',
      method: 'get'
    })
  })

  it('单条已读使用 PUT 和通知 ID', async () => {
    await markNotificationRead(7)

    expect(requestMock).toHaveBeenLastCalledWith({
      url: '/api/notification/7/read',
      method: 'put'
    })
  })

  it('全部已读接口路径正确', async () => {
    await markAllNotificationsRead()

    expect(requestMock).toHaveBeenLastCalledWith({
      url: '/api/notification/read-all',
      method: 'put'
    })
  })
})
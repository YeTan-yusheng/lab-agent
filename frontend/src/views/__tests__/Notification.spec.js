import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { findButton, resourceStubs } from './resourceStubs'

const mocks = vi.hoisted(() => ({
  getNotificationList: vi.fn(),
  markNotificationRead: vi.fn(),
  markAllNotificationsRead: vi.fn(),
  refresh: vi.fn(),
  push: vi.fn(),
  messageSuccess: vi.fn(),
  canAudit: vi.fn()
}))

vi.mock('@/api/notification', () => ({
  getNotificationList: mocks.getNotificationList,
  markNotificationRead: mocks.markNotificationRead,
  markAllNotificationsRead: mocks.markAllNotificationsRead
}))

vi.mock('@/composables/useNotificationCount', async () => {
  const { ref } = await import('vue')
  return {
    useNotificationCount: () => ({
      unreadCount: ref(2),
      refresh: mocks.refresh
    })
  }
})

vi.mock('@/utils/user', () => ({
  useUser: () => ({ can: mocks.canAudit })
}))

vi.mock('@/router', () => ({
  default: { push: mocks.push }
}))

vi.mock('element-plus', () => ({
  ElMessage: { success: mocks.messageSuccess }
}))

import Notification from '@/views/Notification.vue'

const unread = {
  id: 1,
  type: 'reservation_approved',
  title: '预约已通过',
  content: '你预约的实验室已通过。',
  reservation_id: 12,
  is_read: false,
  read_at: null,
  create_time: '2026-11-26T10:00:00'
}

const read = {
  id: 2,
  type: 'reservation_rejected',
  title: '预约已拒绝',
  content: '你预约的实验室已被拒绝。',
  reservation_id: null,
  is_read: true,
  read_at: '2026-11-26T11:00:00',
  create_time: '2026-11-26T09:00:00'
}

async function mountPage() {
  const wrapper = mount(Notification, {
    global: {
      stubs: resourceStubs,
      directives: { loading: {} }
    }
  })
  await flushPromises()
  return wrapper
}

describe('Notification', () => {
  beforeEach(() => {
    mocks.getNotificationList.mockReset()
    mocks.markNotificationRead.mockReset()
    mocks.markAllNotificationsRead.mockReset()
    mocks.refresh.mockReset()
    mocks.push.mockReset()
    mocks.messageSuccess.mockReset()
    mocks.canAudit.mockReset()
    mocks.canAudit.mockReturnValue(false)

    mocks.getNotificationList.mockResolvedValue({
      code: 200,
      data: { list: [{ ...unread, is_read: false }, read], total: 2 }
    })
    mocks.markNotificationRead.mockResolvedValue({ code: 200 })
    mocks.markAllNotificationsRead.mockResolvedValue({ code: 200 })
  })

  it('loads all notifications and renders unread state', async () => {
    const wrapper = await mountPage()

    expect(mocks.getNotificationList).toHaveBeenCalledWith(
      expect.objectContaining({ page: 1, page_size: 10, is_read: null })
    )
    expect(wrapper.text()).toContain('预约已通过')
    expect(wrapper.text()).toContain('你预约的实验室已通过。')
    expect(wrapper.text()).toContain('未读：2')
  })

  it('marks one notification as read and reloads', async () => {
    const wrapper = await mountPage()

    await findButton(wrapper, '标记已读').trigger('click')
    await flushPromises()

    expect(mocks.markNotificationRead).toHaveBeenCalledWith(1)
    expect(mocks.messageSuccess).toHaveBeenCalledWith('已标记为已读')
    expect(mocks.getNotificationList).toHaveBeenCalledTimes(2)
    expect(mocks.refresh).toHaveBeenCalled()
  })

  it('marks all notifications as read', async () => {
    const wrapper = await mountPage()

    await findButton(wrapper, '全部已读').trigger('click')
    await flushPromises()

    expect(mocks.markAllNotificationsRead).toHaveBeenCalledTimes(1)
    expect(mocks.messageSuccess).toHaveBeenCalledWith('全部通知已读')
    expect(mocks.getNotificationList).toHaveBeenCalledTimes(2)
    expect(mocks.refresh).toHaveBeenCalled()
  })

  it('filters unread notifications', async () => {
    const wrapper = await mountPage()

    await findButton(wrapper, '未读').trigger('click')
    await flushPromises()

    expect(mocks.getNotificationList).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 1, is_read: false })
    )
  })

  it('marks as read and jumps to my reservations for a result notification', async () => {
    const wrapper = await mountPage()

    await findButton(wrapper, '查看我的预约').trigger('click')
    await flushPromises()

    expect(mocks.markNotificationRead).toHaveBeenCalledWith(1)
    expect(mocks.refresh).toHaveBeenCalled()
    expect(mocks.push).toHaveBeenCalledWith('/manager/my-reservation')
  })

  it('sends admins to audit for submitted reservations', async () => {
    mocks.canAudit.mockReturnValue(true)
    mocks.getNotificationList.mockResolvedValue({
      code: 200,
      data: {
        list: [
          {
            ...unread,
            is_read: false,
            type: 'reservation_submitted',
            title: '新的待审核预约',
            content: '有一条新的预约待审核。'
          }
        ],
        total: 1
      }
    })
    const wrapper = await mountPage()

    await findButton(wrapper, '去审核').trigger('click')
    await flushPromises()

    expect(mocks.markNotificationRead).toHaveBeenCalledWith(1)
    expect(mocks.push).toHaveBeenCalledWith('/manager/audit-reservation')
  })

  })
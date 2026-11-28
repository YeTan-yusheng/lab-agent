import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { findButton, resourceStubs } from './resourceStubs'

const mocks = vi.hoisted(() => ({
  getAuditHistoryApi: vi.fn()
}))

vi.mock('@/api/reservation', () => ({
  getAuditHistoryApi: mocks.getAuditHistoryApi
}))

import ReservationAudit from '@/views/ReservationAudit.vue'

const rows = [
  {
    id: 3,
    reservation_id: 12,
    action: 'reject',
    from_status: 0,
    to_status: 2,
    reason: '设备维护',
    actor_name: '管理员',
    request_id: 'req-reject',
    create_time: '2026-11-26T10:00:00',
    owner_name: '学生一',
    lab_name: '审计实验室',
    date: '2099-02-01',
    start_time: '09:00',
    end_time: '10:00'
  },
  {
    id: 2,
    reservation_id: 12,
    action: 'approve',
    from_status: 0,
    to_status: 1,
    reason: null,
    actor_name: '管理员',
    request_id: 'req-approve',
    create_time: '2026-11-26T09:00:00',
    owner_name: '学生一',
    lab_name: '审计实验室',
    date: '2099-02-01',
    start_time: '09:00',
    end_time: '10:00'
  }
]

async function mountPage() {
  const wrapper = mount(ReservationAudit, {
    global: {
      stubs: resourceStubs,
      directives: { loading: {} }
    }
  })
  await flushPromises()
  return wrapper
}

describe('ReservationAudit', () => {
  beforeEach(() => {
    mocks.getAuditHistoryApi.mockReset()
    mocks.getAuditHistoryApi.mockResolvedValue({
      code: 200,
      data: { list: rows, total: 2 }
    })
  })

  it('loads audit history with default filters', async () => {
    const wrapper = await mountPage()

    expect(mocks.getAuditHistoryApi).toHaveBeenCalledWith(
      expect.objectContaining({
        page: 1,
        page_size: 10,
        reservation_id: null,
        user_id: null,
        action: null,
        date_from: null,
        date_to: null
      })
    )
    expect(wrapper.text()).toContain('审计实验室')
    expect(wrapper.text()).toContain('学生一')
    expect(wrapper.text()).toContain('设备维护')
    expect(wrapper.text()).toContain('req-reject')
  })

  it('sends reservation id filter and resets to first page', async () => {
    const wrapper = await mountPage()

    await wrapper.findAll('input')[0].setValue('12')
    await findButton(wrapper, '查询').trigger('click')
    await flushPromises()

    expect(mocks.getAuditHistoryApi).toHaveBeenLastCalledWith(
      expect.objectContaining({ reservation_id: 12, page: 1 })
    )
  })
})
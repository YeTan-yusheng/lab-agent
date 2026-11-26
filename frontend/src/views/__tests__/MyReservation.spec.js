import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { findButton, resourceStubs } from './resourceStubs'

const mocks = vi.hoisted(() => ({
  getReservationPageList: vi.fn(),
  cancelReservationApi: vi.fn(),
  getReservationHistoryApi: vi.fn(),
  messageSuccess: vi.fn(),
  messageWarning: vi.fn(),
  messageError: vi.fn(),
  confirm: vi.fn()
}))

vi.mock('@/api/reservation', () => ({
  getReservationPageList: mocks.getReservationPageList,
  cancelReservationApi: mocks.cancelReservationApi,
  getReservationHistoryApi: mocks.getReservationHistoryApi
}))

vi.mock('element-plus', () => ({
  ElMessage: {
    success: mocks.messageSuccess,
    warning: mocks.messageWarning,
    error: mocks.messageError
  },
  ElMessageBox: { confirm: mocks.confirm }
}))

import MyReservation from '@/views/MyReservation.vue'

const baseRow = {
  lab_name: '测试实验室',
  type: '设备',
  equipment_name: '测试设备',
  user_id: 1,
  start_time: '10:00',
  end_time: '11:00'
}

const rows = [
  { ...baseRow, id: 1, status: 0, date: '2099-01-01' },
  { ...baseRow, id: 2, status: 1, date: '2099-01-02' },
  { ...baseRow, id: 3, status: 1, date: '2020-01-01' },
  {
    ...baseRow,
    id: 4,
    status: 4,
    date: '2020-01-01',
    cancel_reason: '未及时审核'
  }
]

async function mountPage() {
  const wrapper = mount(MyReservation, {
    global: {
      stubs: resourceStubs,
      directives: { loading: {} }
    }
  })
  await flushPromises()
  return wrapper
}

describe('MyReservation', () => {
  beforeEach(() => {
    mocks.getReservationPageList.mockResolvedValue({
      code: 200,
      data: { list: rows, total: rows.length }
    })
    mocks.cancelReservationApi.mockResolvedValue({ code: 200, data: {} })
    mocks.getReservationHistoryApi.mockResolvedValue({
      code: 200,
      data: [
        {
          id: 1,
          action: 'submit',
          from_status: null,
          to_status: 0,
          reason: null,
          actor_name: '学生一',
          create_time: '2026-11-24T10:00:00'
        }
      ]
    })
    mocks.confirm.mockResolvedValue()
  })

  it('shows status 4, reasons and cancellation availability', async () => {
    const wrapper = await mountPage()

    expect(wrapper.text()).toContain('已过期')
    expect(wrapper.text()).toContain('取消：未及时审核')

    const cancelButtons = wrapper
      .findAll('button')
      .filter((button) => button.text() === '取消')
    expect(cancelButtons).toHaveLength(3)
    expect(cancelButtons[0].attributes('disabled')).toBeUndefined()
    expect(cancelButtons[1].attributes('disabled')).toBeUndefined()
    expect(cancelButtons[2].attributes('disabled')).toBeDefined()
    expect(cancelButtons[2].attributes('title')).toContain('12 小时')
  })

  it('cancels a pending reservation and reloads the list', async () => {
    const wrapper = await mountPage()
    const cancelButton = findButton(wrapper, '取消')

    await cancelButton.trigger('click')
    await flushPromises()

    expect(mocks.cancelReservationApi).toHaveBeenCalledWith(1)
    expect(mocks.messageSuccess).toHaveBeenCalled()
    expect(mocks.getReservationPageList).toHaveBeenCalledTimes(2)
  })

  it('opens the history drawer', async () => {
    const wrapper = await mountPage()

    await findButton(wrapper, '历史').trigger('click')
    await flushPromises()

    expect(mocks.getReservationHistoryApi).toHaveBeenCalledWith(1)
    expect(wrapper.find('.drawer').exists()).toBe(true)
    expect(wrapper.text()).toContain('提交')
    expect(wrapper.text()).toContain('操作人：学生一')
  })
})
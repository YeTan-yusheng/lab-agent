import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { findButton, resourceStubs } from './resourceStubs'

const mocks = vi.hoisted(() => ({
  getReservationPageList: vi.fn(),
  auditReservationApi: vi.fn(),
  cancelReservationApi: vi.fn(),
  getReservationHistoryApi: vi.fn(),
  getAuditPendingCountApi: vi.fn(),
  getLabPageList: vi.fn(),
  messageSuccess: vi.fn(),
  messageWarning: vi.fn(),
  messageError: vi.fn()
}))

vi.mock('@/api/reservation', () => ({
  getReservationPageList: mocks.getReservationPageList,
  auditReservationApi: mocks.auditReservationApi,
  cancelReservationApi: mocks.cancelReservationApi,
  getReservationHistoryApi: mocks.getReservationHistoryApi,
  getAuditPendingCountApi: mocks.getAuditPendingCountApi
}))

vi.mock('@/api/lab', () => ({
  getLabPageList: mocks.getLabPageList
}))

vi.mock('@/utils/user', async () => {
  const { ref } = await import('vue')
  const userInfo = ref({ id: 2, name: '教师管理员' })
  return {
    useUser: () => ({
      userInfo,
      can: (capability) => capability === 'audit_reservation'
    })
  }
})

vi.mock('element-plus', () => ({
  ElMessage: {
    success: mocks.messageSuccess,
    warning: mocks.messageWarning,
    error: mocks.messageError
  }
}))

import AuditReservation from '@/views/AuditReservation.vue'

const baseRow = {
  lab_name: '测试实验室',
  type: '实验室',
  equipment_name: null,
  date: '2099-01-01',
  start_time: '10:00',
  end_time: '11:00'
}

const otherPending = {
  ...baseRow,
  id: 1,
  user_id: 1,
  user_name: '学生一',
  status: 0
}
const ownPending = {
  ...baseRow,
  id: 2,
  user_id: 2,
  user_name: '教师管理员',
  status: 0
}
const approved = {
  ...baseRow,
  id: 3,
  user_id: 1,
  user_name: '学生一',
  status: 1
}
const expired = {
  ...baseRow,
  id: 4,
  user_id: 1,
  user_name: '学生一',
  status: 4,
  cancel_reason: '待审核超时'
}
const started = {
  ...baseRow,
  id: 5,
  user_id: 1,
  user_name: '学生一',
  status: 0,
  date: '2020-01-01'
}

async function mountPage() {
  const wrapper = mount(AuditReservation, {
    global: {
      stubs: resourceStubs,
      directives: { loading: {} }
    }
  })
  await flushPromises()
  return wrapper
}

function buttonsByText(wrapper, text) {
  return wrapper.findAll('button').filter((button) => button.text() === text)
}

describe('AuditReservation', () => {
  beforeEach(() => {
    mocks.getReservationPageList.mockResolvedValue({
      code: 200,
      data: {
        list: [otherPending, ownPending, approved, expired, started],
        total: 5
      }
    })
    mocks.getLabPageList.mockResolvedValue({
      code: 200,
      data: { list: [{ id: 1, name: '测试实验室' }], total: 1 }
    })
    mocks.getAuditPendingCountApi.mockResolvedValue({
      code: 200,
      data: { count: 2 }
    })
    mocks.auditReservationApi.mockResolvedValue({ code: 200, data: {} })
    mocks.cancelReservationApi.mockResolvedValue({ code: 200, data: {} })
    mocks.getReservationHistoryApi.mockResolvedValue({
      code: 200,
      data: [
        {
          id: 1,
          action: 'approve',
          from_status: 0,
          to_status: 1,
          reason: null,
          actor_name: '管理员',
          create_time: '2026-11-24T10:00:00'
        }
      ]
    })
  })

  it('loads the list with default filters and shows the pending badge', async () => {
    const wrapper = await mountPage()

    expect(mocks.getReservationPageList).toHaveBeenCalledWith(
      expect.objectContaining({ status: null })
    )
    expect(wrapper.text()).toContain('待审核数量：2')
    expect(wrapper.text()).toContain('已过期')
    expect(wrapper.text()).toContain('取消：待审核超时')

    // 已开始的待审核预约不再显示强制取消
    expect(buttonsByText(wrapper, '强制取消')).toHaveLength(3)
  })

  it('requires self-audit when approving own reservation', async () => {
    const wrapper = await mountPage()
    const approveButtons = buttonsByText(wrapper, '通过')

    await approveButtons[1].trigger('click')
    await findButton(wrapper, '确认').trigger('click')
    await flushPromises()

    expect(mocks.messageWarning).toHaveBeenCalledWith(
      '本人预约必须显式开启自审'
    )
    expect(mocks.auditReservationApi).not.toHaveBeenCalled()

    await wrapper.find('.dialog input[type="checkbox"]').setValue(true)
    await findButton(wrapper, '确认').trigger('click')
    await flushPromises()

    expect(mocks.auditReservationApi).toHaveBeenCalledWith(2, {
      status: 1,
      self_audit: true
    })
    expect(mocks.messageSuccess).toHaveBeenCalled()
  })

  it('requires and sends a reject reason', async () => {
    const wrapper = await mountPage()
    await buttonsByText(wrapper, '拒绝')[0].trigger('click')

    await findButton(wrapper, '确认').trigger('click')
    expect(mocks.messageWarning).toHaveBeenCalledWith('请填写拒绝原因')

    await wrapper
      .find('input[placeholder="请填写拒绝原因"]')
      .setValue('不符合开放要求')
    await findButton(wrapper, '确认').trigger('click')
    await flushPromises()

    expect(mocks.auditReservationApi).toHaveBeenCalledWith(1, {
      status: 2,
      self_audit: false,
      reject_reason: '不符合开放要求'
    })
  })

  it('sends force cancel reason', async () => {
    const wrapper = await mountPage()
    await buttonsByText(wrapper, '强制取消')[0].trigger('click')

    await findButton(wrapper, '确认强制取消').trigger('click')
    expect(mocks.messageWarning).toHaveBeenCalledWith('请填写强制取消原因')

    await wrapper
      .find('input[placeholder="请填写强制取消原因"]')
      .setValue('实验室临时关闭')
    await findButton(wrapper, '确认强制取消').trigger('click')
    await flushPromises()

    expect(mocks.cancelReservationApi).toHaveBeenCalledWith(1, {
      force: true,
      reason: '实验室临时关闭'
    })
  })

  it('opens history for a row', async () => {
    const wrapper = await mountPage()

    await buttonsByText(wrapper, '历史')[0].trigger('click')
    await flushPromises()

    expect(mocks.getReservationHistoryApi).toHaveBeenCalledWith(1)
    expect(wrapper.find('.drawer').exists()).toBe(true)
    expect(wrapper.text()).toContain('通过')
    expect(wrapper.text()).toContain('操作人：管理员')
  })
})
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { findButton, resourceStubs } from '../../views/__tests__/resourceStubs'

const mocks = vi.hoisted(() => ({
  getDayAvailabilityApi: vi.fn(),
  createReservationApi: vi.fn(),
  messageSuccess: vi.fn()
}))

vi.mock('@/api/reservation', () => ({
  getDayAvailabilityApi: mocks.getDayAvailabilityApi,
  createReservationApi: mocks.createReservationApi
}))

vi.mock('element-plus', () => ({
  ElMessage: {
    success: mocks.messageSuccess,
    error: vi.fn(),
    warning: vi.fn()
  }
}))

import ReserveDialog from '@/components/ReserveDialog.vue'

const dayRanges = [
  { start: '08:00', end: '10:00' },
  { start: '11:00', end: '18:00' }
]

function dayResponse(ranges = dayRanges, message = null) {
  return {
    code: 200,
    data: {
      open_time: '08:00',
      close_time: '18:00',
      current_time: '16:10',
      message,
      ranges
    }
  }
}

async function mountDialog() {
  const wrapper = mount(ReserveDialog, {
    props: {
      visible: true,
      labId: 1,
      labName: '测试实验室',
      equipmentId: 1,
      equipmentName: '测试设备'
    },
    global: {
      stubs: resourceStubs,
      directives: { loading: {} }
    }
  })
  await flushPromises()
  return wrapper
}

async function selectDate(wrapper, date = '2099-01-01') {
  await wrapper.find('input[placeholder="请选择日期"]').setValue(date)
  await flushPromises()
  await flushPromises()
}

function optionValues(select) {
  return select.findAll('option').map((option) => option.element.value)
}

describe('ReserveDialog 按天可用性', () => {
  beforeEach(() => {
    mocks.getDayAvailabilityApi.mockResolvedValue(dayResponse())
    mocks.createReservationApi.mockResolvedValue({ code: 200, data: {} })
  })

  it('选择日期后加载时间轴，开始时间只包含绿色区间', async () => {
    const wrapper = await mountDialog()
    await selectDate(wrapper)

    expect(mocks.getDayAvailabilityApi).toHaveBeenCalledWith({
      lab_id: 1,
      equipment_id: 1,
      date: '2099-01-01'
    })
    expect(wrapper.find('.timeline-range').exists()).toBe(true)

    const selects = wrapper.findAll('select')
    const starts = optionValues(selects[0])
    expect(starts).toContain('08:00')
    expect(starts).toContain('11:00')
    expect(starts).not.toContain('10:00')
    expect(starts).not.toContain('10:30')
  })

  it('结束时间只能选择同一绿色区间内的时间', async () => {
    const wrapper = await mountDialog()
    await selectDate(wrapper)

    const selects = wrapper.findAll('select')
    await selects[0].setValue('08:00')
    await flushPromises()

    const ends = optionValues(selects[1])
    expect(ends).toContain('08:30')
    expect(ends).toContain('10:00')
    expect(ends).not.toContain('10:30')
  })

  it('选择绿色区间后提交并发送创建请求', async () => {
    const wrapper = await mountDialog()
    await selectDate(wrapper)

    const selects = wrapper.findAll('select')
    await selects[0].setValue('11:00')
    await flushPromises()
    await selects[1].setValue('12:00')
    await flushPromises()

    const submit = findButton(wrapper, '确定')
    expect(submit.attributes('disabled')).toBeUndefined()

    await submit.trigger('click')
    await flushPromises()

    expect(mocks.createReservationApi).toHaveBeenCalledWith({
      lab_id: 1,
      equipment_id: 1,
      date: '2099-01-01',
      start_time: '11:00',
      end_time: '12:00',
      remark: ''
    })
    expect(mocks.messageSuccess).toHaveBeenCalled()
  })

  it('全天不可用时没有可选时间并禁用提交', async () => {
    mocks.getDayAvailabilityApi.mockResolvedValue(dayResponse([], '实验室闭馆'))
    const wrapper = await mountDialog()
    await selectDate(wrapper)

    expect(wrapper.text()).toContain('实验室闭馆')
    expect(optionValues(wrapper.findAll('select')[0])).toEqual([])
    expect(findButton(wrapper, '确定').attributes('disabled')).toBeDefined()
  })

  it('切换日期会清空旧的起止时间', async () => {
    const wrapper = await mountDialog()
    await selectDate(wrapper)

    const selects = wrapper.findAll('select')
    await selects[0].setValue('11:00')
    await flushPromises()
    await selects[1].setValue('12:00')
    await flushPromises()

    await selectDate(wrapper, '2099-01-02')

    expect(wrapper.findAll('select')[0].element.value).toBe('')
    expect(wrapper.findAll('select')[1].element.value).toBe('')
  })

  it('旧日期请求晚返回时不覆盖新日期的结果', async () => {
    let resolveFirst
    mocks.getDayAvailabilityApi
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveFirst = resolve
          })
      )
      .mockResolvedValueOnce(dayResponse([{ start: '08:00', end: '09:00' }]))

    const wrapper = await mountDialog()
    await selectDate(wrapper, '2099-01-01')
    await selectDate(wrapper, '2099-01-02')

    resolveFirst(dayResponse([{ start: '13:00', end: '14:00' }]))
    await flushPromises()
    await flushPromises()

    const starts = optionValues(wrapper.findAll('select')[0])
    expect(starts).toContain('08:00')
    expect(starts).not.toContain('13:00')
  })

  it('创建返回 409 时保持弹窗并显示冲突', async () => {
    mocks.createReservationApi.mockRejectedValue({
      code: 409,
      message: '该时段已被预约'
    })
    const wrapper = await mountDialog()
    await selectDate(wrapper)

    const selects = wrapper.findAll('select')
    await selects[0].setValue('11:00')
    await flushPromises()
    await selects[1].setValue('12:00')
    await flushPromises()

    await findButton(wrapper, '确定').trigger('click')
    await flushPromises()
    await flushPromises()

    expect(wrapper.text()).toContain('该时段已被预约')
    expect(wrapper.find('.dialog').exists()).toBe(true)
    expect(mocks.messageSuccess).not.toHaveBeenCalled()
  })

  it('创建返回 422 时保持弹窗并显示参数错误', async () => {
    mocks.createReservationApi.mockRejectedValue({
      code: 422,
      message: '预约参数有误'
    })
    const wrapper = await mountDialog()
    await selectDate(wrapper)

    const selects = wrapper.findAll('select')
    await selects[0].setValue('11:00')
    await flushPromises()
    await selects[1].setValue('12:00')
    await flushPromises()

    await findButton(wrapper, '确定').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('预约参数有误')
    expect(wrapper.find('.dialog').exists()).toBe(true)
  })

  it('按天可用性网络失败时禁止提交', async () => {
    mocks.getDayAvailabilityApi.mockRejectedValue({ message: '网络异常' })
    const wrapper = await mountDialog()
    await selectDate(wrapper)

    expect(wrapper.text()).toContain('网络异常')
    expect(findButton(wrapper, '确定').attributes('disabled')).toBeDefined()
  })
})
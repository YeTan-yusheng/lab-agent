import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Capability } from '@/utils/permissions'
import { todayString } from '@/utils/todayTime'
import { findButton, resourceStubs } from './resourceStubs'

const mocks = vi.hoisted(() => ({
  getEquipmentPageList: vi.fn(),
  getLab: vi.fn(),
  can: vi.fn(),
  routerPush: vi.fn(),
  messageError: vi.fn(),
  routeState: { route: null }
}))

vi.mock('@/api/equipment', () => ({
  getEquipmentPageList: mocks.getEquipmentPageList
}))
vi.mock('@/api/lab', () => ({ getLab: mocks.getLab }))
vi.mock('@/utils/user', () => ({ useUser: () => ({ can: mocks.can }) }))
vi.mock('element-plus', () => ({
  ElMessage: {
    success: vi.fn(),
    warning: vi.fn(),
    error: mocks.messageError
  }
}))
vi.mock('@/components/ReserveDialog.vue', () => ({
  default: {
    name: 'ReserveDialog',
    props: ['visible', 'labId', 'labName', 'equipmentId', 'equipmentName'],
    template: '<div class="reserve-dialog" />'
  }
}))
vi.mock('vue-router', async () => {
  const { reactive } = await import('vue')
  mocks.routeState.route = reactive({ query: { lab_id: '1' } })
  return {
    useRoute: () => mocks.routeState.route,
    useRouter: () => ({ push: mocks.routerPush })
  }
})

import LabEquipment from '@/views/LabEquipment.vue'

const dateOffset = (offset) => {
  const date = new Date()
  date.setDate(date.getDate() + offset)
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

const equipment = {
  id: 1,
  lab_id: 1,
  name: '设备 A',
  spec: 'S-1',
  quantity: 2,
  status: 1,
  img: ''
}

const labDetail = {
  id: 1,
  name: '实验室 A',
  description: '实验室简介',
  location: 'A101',
  capacity: 20,
  open_time: '08:00',
  close_time: '18:00',
  status: 1,
  closed_days: [
    { date: dateOffset(-1), reason: '过去闭馆' },
    { date: todayString(), reason: '今日闭馆' },
    { date: dateOffset(1), reason: '明天闭馆' },
    { date: dateOffset(2), reason: '后天闭馆' },
    { date: dateOffset(3), reason: '大后天闭馆' }
  ]
}

async function mountPage() {
  const wrapper = mount(LabEquipment, {
    global: {
      stubs: resourceStubs,
      directives: { loading: {} }
    }
  })
  await flushPromises()
  await flushPromises()
  return wrapper
}

describe('LabEquipment 实验室设备浏览页', () => {
  beforeEach(() => {
    mocks.routeState.route.query.lab_id = '1'
    mocks.can.mockImplementation(
      (capability) =>
        capability === Capability.BOOK_LAB || capability === Capability.BOOK_EQUIPMENT
    )
    mocks.getLab.mockResolvedValue({ code: 200, data: labDetail })
    mocks.getEquipmentPageList.mockResolvedValue({
      code: 200,
      data: { list: [equipment], total: 1 }
    })
    mocks.routerPush.mockReset()
    mocks.messageError.mockReset()
  })

  it('有效 lab_id 会加载实验室和对应设备', async () => {
    const wrapper = await mountPage()

    expect(mocks.getLab).toHaveBeenCalledWith(1)
    expect(mocks.getEquipmentPageList).toHaveBeenCalledWith(
      expect.objectContaining({ lab_id: 1, page: 1, page_size: 10 })
    )
    expect(wrapper.text()).toContain('实验室 A')
  })

  it('缺少或非法 lab_id 不请求数据并返回列表页', async () => {
    mocks.routeState.route.query.lab_id = 'abc'

    await mountPage()

    expect(mocks.getLab).not.toHaveBeenCalled()
    expect(mocks.getEquipmentPageList).not.toHaveBeenCalled()
    expect(mocks.routerPush).toHaveBeenCalledWith('/manager/lablist')
  })

  it('近期闭馆只展示今天及之后，过去日期不展示', async () => {
    const wrapper = await mountPage()

    expect(wrapper.text()).toContain(todayString())
    expect(wrapper.text()).toContain(dateOffset(1))
    expect(wrapper.text()).toContain(dateOffset(2))
    expect(wrapper.text()).not.toContain('过去闭馆')
  })

  it('今日闭馆时实验室和设备的预约按钮都禁用', async () => {
    const wrapper = await mountPage()

    expect(wrapper.text()).toContain('今日闭馆')
    expect(findButton(wrapper, '预约实验室').attributes('disabled')).toBeDefined()
    expect(findButton(wrapper, '预约').attributes('disabled')).toBeDefined()
  })

  it('维修设备的预约按钮禁用并显示维修', async () => {
    mocks.getEquipmentPageList.mockResolvedValue({
      code: 200,
      data: { list: [{ ...equipment, status: 0 }], total: 1 }
    })
    const wrapper = await mountPage()

    expect(wrapper.text()).toContain('维修')
    expect(findButton(wrapper, '预约').attributes('disabled')).toBeDefined()
  })

  it('路由 lab_id 变化后重新加载对应实验室', async () => {
    const wrapper = await mountPage()

    mocks.routeState.route.query.lab_id = '2'
    await flushPromises()
    await flushPromises()

    expect(mocks.getLab).toHaveBeenLastCalledWith(2)
    expect(mocks.getEquipmentPageList.mock.calls.at(-1)[0]).toEqual(
      expect.objectContaining({ lab_id: 2, page: 1 })
    )
    expect(wrapper.text()).toContain('实验室 A')
  })
})
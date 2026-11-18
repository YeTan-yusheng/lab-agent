import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Capability } from '@/utils/permissions'
import { todayString } from '@/utils/todayTime'
import { findButton, resourceStubs } from './resourceStubs'

const mocks = vi.hoisted(() => ({
  getLabPageList: vi.fn(),
  can: vi.fn(),
  routerPush: vi.fn()
}))

vi.mock('@/api/lab', () => ({ getLabPageList: mocks.getLabPageList }))
vi.mock('@/router', () => ({ default: { push: mocks.routerPush } }))
vi.mock('@/utils/user', () => ({ useUser: () => ({ can: mocks.can }) }))
vi.mock('@/components/ReserveDialog.vue', () => ({
  default: {
    name: 'ReserveDialog',
    props: ['visible', 'labId', 'labName'],
    template: '<div class="reserve-dialog" />'
  }
}))

import LabList from '@/views/LabList.vue'

const dateOffset = (offset) => {
  const date = new Date()
  date.setDate(date.getDate() + offset)
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

const openLab = {
  id: 1,
  name: '开放实验室',
  location: 'A101',
  capacity: 20,
  open_time: '08:00',
  close_time: '18:00',
  status: 1,
  upcoming_closed_days: [{ date: dateOffset(10), reason: '设备检修' }]
}

const closedLab = {
  id: 2,
  name: '关闭实验室',
  location: 'B201',
  capacity: 10,
  open_time: '08:00',
  close_time: '18:00',
  status: 0,
  upcoming_closed_days: []
}

async function mountPage() {
  const wrapper = mount(LabList, {
    global: {
      stubs: resourceStubs,
      directives: { loading: {} }
    }
  })
  await flushPromises()
  return wrapper
}

describe('LabList 实验室浏览页', () => {
  beforeEach(() => {
    mocks.can.mockImplementation((capability) => capability === Capability.BOOK_LAB)
    mocks.getLabPageList.mockResolvedValue({
      code: 200,
      data: { list: [openLab, closedLab], total: 2 }
    })
    mocks.routerPush.mockReset()
  })

  it('默认请求全部实验室并展示开放和关闭状态', async () => {
    const wrapper = await mountPage()

    expect(mocks.getLabPageList).toHaveBeenCalledWith(
      expect.objectContaining({ page: 1, page_size: 8, status: null })
    )
    expect(wrapper.text()).toContain('开放中')
    expect(wrapper.text()).toContain('已关闭')
    expect(wrapper.text()).toContain('开放实验室')
    expect(wrapper.text()).toContain('关闭实验室')
  })

  it('状态筛选变化后重置页码并传递状态', async () => {
    const wrapper = await mountPage()

    await wrapper.find('select').setValue('0')
    await flushPromises()

    const params = mocks.getLabPageList.mock.calls.at(-1)[0]
    expect(params.status).toBe(0)
    expect(params.page).toBe(1)
  })

  it('学生看不到实验室预约按钮，但能看到查看设备', async () => {
    mocks.can.mockReturnValue(false)
    const wrapper = await mountPage()

    expect(findButton(wrapper, '预约')).toBeUndefined()
    expect(findButton(wrapper, '查看设备')).toBeTruthy()
  })

  it('关闭实验室的预约按钮禁用', async () => {
    const wrapper = await mountPage()
    const reserveButtons = wrapper.findAll('button').filter((button) => button.text() === '预约')

    expect(reserveButtons).toHaveLength(2)
    expect(reserveButtons[0].attributes('disabled')).toBeUndefined()
    expect(reserveButtons[1].attributes('disabled')).toBeDefined()
  })

  it('当天闭馆显示今日闭馆并禁用预约', async () => {
    mocks.getLabPageList.mockResolvedValue({
      code: 200,
      data: {
        list: [
          {
            ...openLab,
            upcoming_closed_days: [{ date: todayString(), reason: '临时闭馆' }]
          }
        ],
        total: 1
      }
    })
    const wrapper = await mountPage()

    expect(wrapper.text()).toContain('今日闭馆')
    expect(findButton(wrapper, '预约').attributes('disabled')).toBeDefined()
  })

  it('展示近期闭馆日期和原因', async () => {
    const wrapper = await mountPage()

    expect(wrapper.text()).toContain(dateOffset(10))
    expect(wrapper.text()).toContain('设备检修')
  })

  it('空列表显示空状态', async () => {
    mocks.getLabPageList.mockResolvedValue({
      code: 200,
      data: { list: [], total: 0 }
    })
    const wrapper = await mountPage()

    expect(wrapper.text()).toContain('暂无数据')
  })

  it('查看设备跳转到对应实验室', async () => {
    const wrapper = await mountPage()

    await findButton(wrapper, '查看设备').trigger('click')

    expect(mocks.routerPush).toHaveBeenCalledWith({
      path: '/manager/lab-equipment',
      query: { lab_id: openLab.id }
    })
  })
})
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { findButton, findDialog, resourceStubs } from './resourceStubs'

const mocks = vi.hoisted(() => ({
  getLabPageList: vi.fn(),
  getLab: vi.fn(),
  createLabApi: vi.fn(),
  updateLabApi: vi.fn(),
  deleteLabApi: vi.fn(),
  getLabClosedDays: vi.fn(),
  updateLabClosedDayApi: vi.fn(),
  deleteLabClosedDay: vi.fn(),
  uploadFileApi: vi.fn(),
  can: vi.fn(),
  messageSuccess: vi.fn(),
  messageWarning: vi.fn(),
  messageError: vi.fn(),
  confirm: vi.fn()
}))

vi.mock('@/api/lab', () => ({
  getLabPageList: mocks.getLabPageList,
  getLab: mocks.getLab,
  createLabApi: mocks.createLabApi,
  updateLabApi: mocks.updateLabApi,
  deleteLabApi: mocks.deleteLabApi,
  getLabClosedDays: mocks.getLabClosedDays,
  updateLabClosedDayApi: mocks.updateLabClosedDayApi,
  deleteLabClosedDay: mocks.deleteLabClosedDay
}))

vi.mock('@/api/file', () => ({ uploadFileApi: mocks.uploadFileApi }))

vi.mock('@/utils/user', () => ({
  useUser: () => ({ can: mocks.can })
}))

vi.mock('element-plus', () => ({
  ElMessage: {
    success: mocks.messageSuccess,
    warning: mocks.messageWarning,
    error: mocks.messageError
  },
  ElMessageBox: { confirm: mocks.confirm }
}))

import Lab from '@/views/Lab.vue'

const labRow = {
  id: 1,
  name: '测试实验室',
  location: '综合楼101',
  capacity: 20,
  open_time: '08:00',
  close_time: '18:00',
  description: '简介',
  img: '',
  status: 1
}

const labDetail = {
  ...labRow,
  closed_days: []
}

const closedDay = {
  lab_id: 1,
  date: '2099-12-30',
  reason: '闭馆'
}

async function mountPage() {
  const wrapper = mount(Lab, {
    global: {
      stubs: resourceStubs,
      directives: { loading: {} }
    }
  })
  await flushPromises()
  return wrapper
}

async function openLabEdit(wrapper) {
  await findButton(wrapper, '编辑').trigger('click')
  await flushPromises()
}

async function openClosedDayDialog(wrapper) {
  await findButton(wrapper, '新增/更新闭馆日').trigger('click')
  await flushPromises()
  return findDialog(wrapper)
}

describe('Lab 实验室管理页', () => {
  beforeEach(() => {
    mocks.can.mockReturnValue(true)
    mocks.getLabPageList.mockResolvedValue({
      code: 200,
      data: { list: [labRow], total: 1 }
    })
    mocks.getLab.mockResolvedValue({ code: 200, data: labDetail })
    mocks.createLabApi.mockResolvedValue({ code: 200, data: labRow })
    mocks.updateLabApi.mockResolvedValue({ code: 200, data: labRow })
    mocks.deleteLabApi.mockResolvedValue({ code: 200 })
    mocks.getLabClosedDays.mockResolvedValue({ code: 200, data: [closedDay] })
    mocks.updateLabClosedDayApi.mockResolvedValue({ code: 200, data: closedDay })
    mocks.deleteLabClosedDay.mockResolvedValue({ code: 200 })
    mocks.uploadFileApi.mockResolvedValue({ code: 200, data: { url: '/cover.png' } })
    mocks.confirm.mockResolvedValue('confirm')
  })

  it('状态筛选把 0 传给列表接口并把页码重置为 1', async () => {
    const wrapper = await mountPage()

    await wrapper.find('select').setValue('0')
    await flushPromises()

    const params = mocks.getLabPageList.mock.calls.at(-1)[0]
    expect(params.status).toBe(0)
    expect(params.page).toBe(1)
  })

  it('编辑保存发送完整 payload，不发送 id，空可选字段转 null', async () => {
    const wrapper = await mountPage()

    await openLabEdit(wrapper)

    const dialog = findDialog(wrapper)
    await dialog.find('input[placeholder="请输入实验室名称"]').setValue(' 新实验室 ')
    await dialog.find('input[placeholder="请输入位置"]').setValue('')
    await dialog.find('input[placeholder="请输入简介"]').setValue('')
    await findButton(dialog, '确定').trigger('click')
    await flushPromises()

    expect(mocks.getLab).toHaveBeenCalledWith(1)
    expect(mocks.updateLabApi).toHaveBeenCalledTimes(1)

    const [id, payload] = mocks.updateLabApi.mock.calls[0]
    expect(id).toBe(1)
    expect(payload).toEqual({
      name: '新实验室',
      location: null,
      capacity: 20,
      open_time: '08:00',
      close_time: '18:00',
      description: null,
      img: null,
      status: 1
    })
    expect(payload).not.toHaveProperty('id')
    expect(mocks.getLabPageList).toHaveBeenCalledTimes(2)
  })

  it('保存返回 409 时保持弹窗且不提示成功', async () => {
    mocks.updateLabApi.mockRejectedValue({ code: 409, message: '实验室已存在' })
    const wrapper = await mountPage()

    await openLabEdit(wrapper)
    const dialog = findDialog(wrapper)
    await findButton(dialog, '确定').trigger('click')
    await flushPromises()

    expect(findDialog(wrapper).exists()).toBe(true)
    expect(mocks.messageSuccess).not.toHaveBeenCalled()
  })

  it('非管理员看不到新增、编辑、删除和闭馆日操作', async () => {
    mocks.can.mockReturnValue(false)
    const wrapper = await mountPage()

    expect(findButton(wrapper, '新增')).toBeUndefined()
    expect(findButton(wrapper, '新增/更新闭馆日')).toBeUndefined()
    expect(findButton(wrapper, '编辑')).toBeUndefined()
    expect(findButton(wrapper, '删除')).toBeUndefined()
  })

  it('闭馆日弹窗加载列表并新增闭馆日', async () => {
    const wrapper = await mountPage()

    const dialog = await openClosedDayDialog(wrapper)

    expect(mocks.getLabClosedDays).toHaveBeenCalledWith(1)
    expect(dialog.text()).toContain('闭馆日 - 测试实验室')

    await dialog.find('input[placeholder="选择闭馆日期"]').setValue('2099-12-31')
    await dialog.find('input[placeholder="闭馆原因（可选）"]').setValue('元旦闭馆')
    await findButton(dialog, '新增').trigger('click')
    await flushPromises()

    expect(mocks.updateLabClosedDayApi).toHaveBeenCalledWith(1, {
      date: '2099-12-31',
      reason: '元旦闭馆'
    })
    expect(mocks.getLabClosedDays).toHaveBeenCalledTimes(2)
  })

  it('选择已有闭馆日后锁定日期，只更新原因', async () => {
    const wrapper = await mountPage()

    const dialog = await openClosedDayDialog(wrapper)
    await findButton(dialog, '编辑').trigger('click')

    const dateInput = dialog.find('input[placeholder="选择闭馆日期"]')
    expect(dateInput.element.value).toBe('2099-12-30')
    expect(dateInput.element.disabled).toBe(true)
    expect(findButton(dialog, '保存修改')).toBeTruthy()

    await dialog.find('input[placeholder="闭馆原因（可选）"]').setValue('新原因')
    await findButton(dialog, '保存修改').trigger('click')
    await flushPromises()

    expect(mocks.updateLabClosedDayApi).toHaveBeenCalledWith(1, {
      date: '2099-12-30',
      reason: '新原因'
    })
  })

  it('删除闭馆日调用 DELETE 并刷新列表', async () => {
    const wrapper = await mountPage()

    const dialog = await openClosedDayDialog(wrapper)
    await findButton(dialog, '删除').trigger('click')
    await flushPromises()
    await flushPromises()

    expect(mocks.confirm).toHaveBeenCalledTimes(1)
    expect(mocks.deleteLabClosedDay).toHaveBeenCalledWith(1, '2099-12-30')
    expect(mocks.getLabClosedDays).toHaveBeenCalledTimes(2)
  })
})
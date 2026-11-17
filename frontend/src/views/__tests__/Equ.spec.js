import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { findButton, findDialog, resourceStubs } from './resourceStubs'

const mocks = vi.hoisted(() => ({
  getEquipmentPageList: vi.fn(),
  getEquipment: vi.fn(),
  createEquipmentApi: vi.fn(),
  updateEquipmentApi: vi.fn(),
  deleteEquipmentApi: vi.fn(),
  getLabPageList: vi.fn(),
  uploadFileApi: vi.fn(),
  can: vi.fn(),
  messageSuccess: vi.fn(),
  messageWarning: vi.fn(),
  messageError: vi.fn(),
  confirm: vi.fn()
}))

vi.mock('@/api/equipment', () => ({
  getEquipmentPageList: mocks.getEquipmentPageList,
  getEquipment: mocks.getEquipment,
  createEquipmentApi: mocks.createEquipmentApi,
  updateEquipmentApi: mocks.updateEquipmentApi,
  deleteEquipmentApi: mocks.deleteEquipmentApi
}))

vi.mock('@/api/lab', () => ({ getLabPageList: mocks.getLabPageList }))

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

import Equ from '@/views/Equ.vue'

const labRow = {
  id: 1,
  name: '实验室 A',
  status: 1
}

const equipmentRow = {
  id: 1,
  lab_id: 1,
  lab_name: '实验室 A',
  name: '设备 A',
  description: '说明',
  img: '',
  spec: 'S-1',
  quantity: 2,
  status: 1
}

const equipmentDetail = {
  ...equipmentRow,
  lab_status: 1
}

async function mountPage() {
  const wrapper = mount(Equ, {
    global: {
      stubs: resourceStubs,
      directives: { loading: {} }
    }
  })
  await flushPromises()
  return wrapper
}

async function openEdit(wrapper) {
  await findButton(wrapper, '编辑').trigger('click')
  await flushPromises()
}

describe('Equ 设备管理页', () => {
  beforeEach(() => {
    mocks.can.mockReturnValue(true)
    mocks.getLabPageList.mockResolvedValue({
      code: 200,
      data: { list: [labRow], total: 1 }
    })
    mocks.getEquipmentPageList.mockResolvedValue({
      code: 200,
      data: { list: [equipmentRow], total: 1 }
    })
    mocks.getEquipment.mockResolvedValue({ code: 200, data: equipmentDetail })
    mocks.createEquipmentApi.mockResolvedValue({ code: 200, data: equipmentRow })
    mocks.updateEquipmentApi.mockResolvedValue({ code: 200, data: equipmentRow })
    mocks.deleteEquipmentApi.mockResolvedValue({ code: 200 })
    mocks.uploadFileApi.mockResolvedValue({ code: 200, data: { url: '/equipment.png' } })
    mocks.confirm.mockResolvedValue('confirm')
  })

  it('实验室和状态筛选参数正确传给列表接口', async () => {
    const wrapper = await mountPage()
    const selects = wrapper.findAll('select')

    await selects[0].setValue('1')
    await flushPromises()
    expect(mocks.getEquipmentPageList.mock.calls.at(-1)[0].lab_id).toBe(1)

    await selects[1].setValue('0')
    await flushPromises()
    const params = mocks.getEquipmentPageList.mock.calls.at(-1)[0]
    expect(params.lab_id).toBe(1)
    expect(params.status).toBe(0)
  })

  it('编辑先请求详情，保存发送完整 payload、不含 id，空字段转 null', async () => {
    const wrapper = await mountPage()

    await openEdit(wrapper)

    expect(mocks.getEquipment).toHaveBeenCalledWith(1)

    const dialog = findDialog(wrapper)
    await dialog.find('input[placeholder="请输入设备名称"]').setValue('新设备')
    await dialog.find('input[placeholder="请输入说明"]').setValue('')
    await dialog.find('input[placeholder="例如 RTX4090 24G"]').setValue('')
    await findButton(dialog, '确定').trigger('click')
    await flushPromises()

    expect(mocks.updateEquipmentApi).toHaveBeenCalledTimes(1)
    const [id, payload] = mocks.updateEquipmentApi.mock.calls[0]
    expect(id).toBe(1)
    expect(payload).toEqual({
      lab_id: 1,
      name: '新设备',
      description: null,
      img: null,
      spec: null,
      quantity: 2,
      status: 1
    })
    expect(payload).not.toHaveProperty('id')
    expect(mocks.getEquipmentPageList).toHaveBeenCalledTimes(2)
  })

  it('保存返回 409 时保持弹窗且不提示成功', async () => {
    mocks.updateEquipmentApi.mockRejectedValue({ code: 409, message: '同名设备' })
    const wrapper = await mountPage()

    await openEdit(wrapper)
    const dialog = findDialog(wrapper)
    await findButton(dialog, '确定').trigger('click')
    await flushPromises()

    expect(findDialog(wrapper).exists()).toBe(true)
    expect(mocks.messageSuccess).not.toHaveBeenCalled()
  })

  it('删除设备返回 409 时不刷新列表', async () => {
    mocks.deleteEquipmentApi.mockRejectedValue({
      code: 409,
      message: '设备下存在预约，无法删除'
    })
    const wrapper = await mountPage()
    const before = mocks.getEquipmentPageList.mock.calls.length

    await findButton(wrapper, '删除').trigger('click')
    await flushPromises()
    await flushPromises()

    expect(mocks.deleteEquipmentApi).toHaveBeenCalledWith(1)
    expect(mocks.getEquipmentPageList.mock.calls.length).toBe(before)
  })

  it('非管理员看不到新增、编辑和删除按钮', async () => {
    mocks.can.mockReturnValue(false)
    const wrapper = await mountPage()

    expect(findButton(wrapper, '新增')).toBeUndefined()
    expect(findButton(wrapper, '编辑')).toBeUndefined()
    expect(findButton(wrapper, '删除')).toBeUndefined()
  })
})
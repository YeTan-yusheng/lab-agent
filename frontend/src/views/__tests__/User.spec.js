import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const {
  createUserApi,
  updateUserApi,
  updateUserRolesApi,
  getUserPageList,
  deleteUserApi,
  getUserDetailApi
} = vi.hoisted(() => ({
  createUserApi: vi.fn(),
  updateUserApi: vi.fn(),
  updateUserRolesApi: vi.fn(),
  getUserPageList: vi.fn(),
  deleteUserApi: vi.fn(),
  getUserDetailApi: vi.fn()
}))

vi.mock('@/api/user', () => ({
  createUserApi,
  updateUserApi,
  updateUserRolesApi,
  getUserPageList,
  deleteUserApi,
  getUserDetailApi
}))

vi.mock('@/utils/user', async () => {
  const { ref } = await import('vue')
  const userInfo = ref({
    id: 1,
    username: 'admin01',
    capabilities: ['manage_users']
  })
  return {
    useUser: () => ({ userInfo, can: () => true })
  }
})

import User from '@/views/User.vue'

const ElTableStub = {
  props: ['data'],
  provide() {
    return { getTableData: () => this.data }
  },
  template: '<div><slot /></div>'
}

const ElTableColumnStub = {
  inject: ['getTableData'],
  props: ['prop', 'label', 'width'],
  template:
    '<div><div v-for="row in getTableData()" :key="row.id"><slot :row="row" /></div></div>'
}

const stubs = {
  'el-card': {
    template: '<div><slot name="header" /><slot /></div>'
  },
  'el-table': ElTableStub,
  'el-table-column': ElTableColumnStub,
  'el-pagination': { template: '<div />' },
  'el-dialog': {
    props: ['modelValue', 'title', 'width'],
    template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>'
  },
  'el-form': {
    methods: {
      validate: () => Promise.resolve(true)
    },
    template: '<form><slot /></form>'
  },
  'el-form-item': { template: '<div><slot /></div>' },
  'el-input': {
    props: ['modelValue', 'disabled', 'type', 'showPassword', 'placeholder'],
    emits: ['update:modelValue'],
    template: '<input :type="type || \'text\'" :value="modelValue" />'
  },
  'el-select': {
    props: ['modelValue', 'disabled'],
    emits: ['update:modelValue'],
    template:
      '<select :value="modelValue" :disabled="disabled" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>'
  },
  'el-option': {
    props: ['label', 'value'],
    template: '<option :value="value">{{ label }}</option>'
  },
  'el-radio-group': { template: '<div><slot /></div>' },
  'el-radio': { template: '<div />' },
  'el-tag': { template: '<span><slot /></span>' },
  'el-button': {
    emits: ['click'],
    template: '<button type="button" @click="$emit(\'click\')"><slot /></button>'
  }
}

const teacherAdminRow = {
  id: 4,
  username: 'teacher_admin01',
  name: '教师管理员',
  role: 'admin',
  email: 'ta@example.com',
  phone: '13800000000',
  avatar: '',
  status: 1
}

const teacherAdminDetail = {
  ...teacherAdminRow,
  roles: ['teacher', 'admin'],
  display_name: '教师/管理员'
}

async function mountPage() {
  const wrapper = mount(User, {
    global: {
      stubs,
      directives: { loading: {} }
    }
  })
  await flushPromises()
  return wrapper
}

function findButton(wrapper, text) {
  return wrapper.findAll('button').find((button) => button.text() === text)
}

async function openEdit(wrapper) {
  await findButton(wrapper, '编辑').trigger('click')
  await flushPromises()
  await nextTick()
}

describe('User 用户管理页', () => {
  beforeEach(() => {
    createUserApi.mockReset()
    updateUserApi.mockReset()
    updateUserRolesApi.mockReset()
    getUserPageList.mockReset()
    deleteUserApi.mockReset()
    getUserDetailApi.mockReset()

    getUserPageList.mockResolvedValue({
      code: 200,
      data: { list: [teacherAdminRow], total: 1 }
    })
    getUserDetailApi.mockResolvedValue({ code: 200, data: teacherAdminDetail })
    createUserApi.mockResolvedValue({ code: 200, data: {} })
    updateUserApi.mockResolvedValue({ code: 200, data: {} })
    updateUserRolesApi.mockResolvedValue({ code: 200, data: {} })
  })

  it('新增管理员时发送 roles 数组，不发送 roleKey', async () => {
    const wrapper = await mountPage()

    await findButton(wrapper, '新增').trigger('click')
    await nextTick()

    await wrapper.find('select').setValue('admin')
    await findButton(wrapper, '确定').trigger('click')
    await flushPromises()

    expect(createUserApi).toHaveBeenCalledTimes(1)
    const payload = createUserApi.mock.calls[0][0]

    expect(payload.roles).toEqual(['admin'])
    expect(payload).not.toHaveProperty('roleKey')
  })

  it('新增学生时发送 roles: ["student"]', async () => {
    const wrapper = await mountPage()

    await findButton(wrapper, '新增').trigger('click')
    await nextTick()
    await findButton(wrapper, '确定').trigger('click')
    await flushPromises()

    expect(createUserApi.mock.calls[0][0].roles).toEqual(['student'])
  })

  it('编辑用户先请求详情并回显教师+管理员组合', async () => {
    const wrapper = await mountPage()

    await openEdit(wrapper)

    expect(getUserDetailApi).toHaveBeenCalledWith(teacherAdminRow.id)
    expect(wrapper.find('select').element.value).toBe('teacher_admin')
  })

  it('编辑用户时隐藏密码框', async () => {
    const wrapper = await mountPage()

    await openEdit(wrapper)

    expect(wrapper.find('input[type="password"]').exists()).toBe(false)
  })

  it('只改资料时不调用角色接口', async () => {
    const wrapper = await mountPage()

    await openEdit(wrapper)
    await findButton(wrapper, '确定').trigger('click')
    await flushPromises()

    expect(updateUserApi).toHaveBeenCalledTimes(1)
    const profilePayload = updateUserApi.mock.calls[0][1]
    expect(profilePayload).not.toHaveProperty('roles')
    expect(profilePayload).not.toHaveProperty('roleKey')
    expect(updateUserRolesApi).not.toHaveBeenCalled()
  })

  it('修改角色时单独调用 /roles 接口', async () => {
    const wrapper = await mountPage()

    await openEdit(wrapper)
    await wrapper.find('select').setValue('teacher')
    await findButton(wrapper, '确定').trigger('click')
    await flushPromises()

    expect(updateUserApi).toHaveBeenCalledTimes(1)
    expect(updateUserRolesApi).toHaveBeenCalledWith(teacherAdminRow.id, ['teacher'])
  })

  it('编辑自己时禁用角色下拉并跳过角色接口', async () => {
    getUserPageList.mockResolvedValue({
      code: 200,
      data: {
        list: [{ ...teacherAdminRow, id: 1, username: 'admin01' }],
        total: 1
      }
    })
    getUserDetailApi.mockResolvedValue({
      code: 200,
      data: { ...teacherAdminDetail, id: 1, username: 'admin01' }
    })
    const wrapper = await mountPage()

    await openEdit(wrapper)

    expect(wrapper.find('select').element.disabled).toBe(true)

    await findButton(wrapper, '确定').trigger('click')
    await flushPromises()

    expect(updateUserRolesApi).not.toHaveBeenCalled()
  })

  it('用户列表教师角色显示为教师', async () => {
    getUserPageList.mockResolvedValue({
      code: 200,
      data: {
        list: [{ ...teacherAdminRow, id: 2, username: 'teacher01', role: 'teacher' }],
        total: 1
      }
    })
    const wrapper = await mountPage()

    expect(wrapper.text()).toContain('教师')
    expect(wrapper.text()).not.toContain('学生')
  })

  it('角色更新失败时不提示成功、不关闭弹窗', async () => {
    updateUserRolesApi.mockRejectedValue({ code: 500, message: '更新失败' })
    const wrapper = await mountPage()

    await openEdit(wrapper)
    await wrapper.find('select').setValue('teacher')
    await findButton(wrapper, '确定').trigger('click')
    await flushPromises()

    expect(wrapper.find('select').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('操作成功')
  })
})
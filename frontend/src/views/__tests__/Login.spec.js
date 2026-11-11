import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const {
  loginApiMock,
  saveLoginDataMock,
  replaceMock,
  pushMock,
  successMessageMock,
  errorMessageMock,
  validateMock,
  routeMock
} = vi.hoisted(() => ({
  loginApiMock: vi.fn(),
  saveLoginDataMock: vi.fn(),
  replaceMock: vi.fn(),
  pushMock: vi.fn(),
  successMessageMock: vi.fn(),
  errorMessageMock: vi.fn(),
  validateMock: vi.fn(),
  routeMock: { query: {} }
}))

vi.mock('@/api/auth', () => ({
  loginApi: loginApiMock
}))

vi.mock('@/utils/user', () => ({
  useUser: () => ({ saveLoginData: saveLoginDataMock })
}))

vi.mock('@/router', () => ({
  default: { replace: replaceMock, push: pushMock }
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeMock
}))

vi.mock('element-plus', () => ({
  ElMessage: { success: successMessageMock, error: errorMessageMock }
}))

import Login from '@/views/Login.vue'

const ElFormStub = {
  name: 'ElForm',
  methods: {
    validate: () => validateMock()
  },
  template: '<form><slot /></form>'
}

const stubs = {
  'el-form': ElFormStub,
  'el-form-item': { template: '<div><slot /></div>' },
  'el-input': {
    props: ['modelValue', 'type', 'size', 'placeholder', 'prefixIcon'],
    emits: ['update:modelValue'],
    template: '<input :value="modelValue" />'
  },
  'el-button': {
    emits: ['click'],
    template: '<button type="button" @click="$emit(\'click\')"><slot /></button>'
  },
  'router-link': { template: '<a><slot /></a>' }
}

const loginResponse = {
  code: 200,
  message: '登录成功',
  data: {
    token: 'token-1',
    user: {
      id: 1,
      username: 'student01',
      name: '学生一',
      roles: ['student'],
      capabilities: ['book_equipment', 'use_ai'],
      primary_role: 'student',
      display_name: '学生'
    }
  }
}

async function mountAndSubmit() {
  const wrapper = mount(Login, {
    global: { stubs }
  })
  await wrapper.find('button').trigger('click')
  await flushPromises()
  return wrapper
}

describe('Login', () => {
  beforeEach(() => {
    loginApiMock.mockReset()
    saveLoginDataMock.mockReset()
    replaceMock.mockReset()
    pushMock.mockReset()
    successMessageMock.mockReset()
    errorMessageMock.mockReset()
    validateMock.mockReset()
    validateMock.mockResolvedValue(true)
    routeMock.query = {}
    loginApiMock.mockResolvedValue(loginResponse)
  })

  it('登录成功后先保存登录态，再跳转 redirect', async () => {
    routeMock.query = { redirect: '/manager/user' }

    await mountAndSubmit()

    expect(loginApiMock).toHaveBeenCalledTimes(1)
    expect(saveLoginDataMock).toHaveBeenCalledWith(loginResponse.data)
    expect(replaceMock).toHaveBeenCalledWith('/manager/user')
    expect(pushMock).not.toHaveBeenCalled()
    expect(successMessageMock).toHaveBeenCalledWith('登录成功')
    expect(saveLoginDataMock.mock.invocationCallOrder[0]).toBeLessThan(
      replaceMock.mock.invocationCallOrder[0]
    )
  })

  it('没有 redirect 时回首页', async () => {
    await mountAndSubmit()

    expect(replaceMock).toHaveBeenCalledWith('/manager/home')
    expect(pushMock).not.toHaveBeenCalled()
  })

  it('拒绝站外 redirect', async () => {
    routeMock.query = { redirect: 'https://evil.example.com' }

    await mountAndSubmit()

    expect(replaceMock).toHaveBeenCalledWith('/manager/home')
  })

  it('拒绝 // 开头的 redirect', async () => {
    routeMock.query = { redirect: '//evil.example.com' }

    await mountAndSubmit()

    expect(replaceMock).toHaveBeenCalledWith('/manager/home')
  })

  it('表单校验失败时不调用登录接口', async () => {
    validateMock.mockResolvedValue(false)

    await mountAndSubmit()

    expect(loginApiMock).not.toHaveBeenCalled()
    expect(saveLoginDataMock).not.toHaveBeenCalled()
    expect(replaceMock).not.toHaveBeenCalled()
  })

  it('登录失败时不保存登录态、不跳转', async () => {
    loginApiMock.mockRejectedValue({ code: 401, message: '账号或密码错误' })

    await mountAndSubmit()

    expect(loginApiMock).toHaveBeenCalledTimes(1)
    expect(saveLoginDataMock).not.toHaveBeenCalled()
    expect(replaceMock).not.toHaveBeenCalled()
    expect(pushMock).not.toHaveBeenCalled()
  })
})
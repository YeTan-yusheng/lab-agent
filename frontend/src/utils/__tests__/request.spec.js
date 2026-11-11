import { beforeEach, describe, expect, it, vi } from 'vitest'

const { clearUserMock, pushMock, errorMessageMock } = vi.hoisted(() => ({
  clearUserMock: vi.fn(),
  pushMock: vi.fn(),
  errorMessageMock: vi.fn()
}))

vi.mock('@/utils/user', () => ({
  useUser: () => ({ clearUser: clearUserMock })
}))

vi.mock('@/router', () => ({
  default: { push: pushMock }
}))

vi.mock('element-plus', () => ({
  ElMessage: { error: errorMessageMock }
}))

import service from '@/utils/request'

function successAdapter(payload, captureConfig) {
  return async (config) => {
    captureConfig?.(config)
    return {
      data: payload,
      status: 200,
      statusText: 'OK',
      headers: {},
      config
    }
  }
}

function errorAdapter(status, data, extraConfig = {}) {
  return async (config) => {
    const requestConfig = { ...config, ...extraConfig }
    return Promise.reject({
      config: requestConfig,
      response: { status, data, headers: {}, config: requestConfig },
      isAxiosError: true,
      message: data?.message || 'request failed'
    })
  }
}

describe('request 拦截器', () => {
  beforeEach(() => {
    localStorage.clear()
    clearUserMock.mockReset()
    pushMock.mockReset()
    errorMessageMock.mockReset()
  })

  it('请求自动携带 Bearer token', async () => {
    localStorage.setItem('token', 'token-abc')
    let captured
    service.defaults.adapter = successAdapter(
      { code: 200, message: 'ok', data: null },
      (config) => {
        captured = config
      }
    )

    const body = await service.get('/api/lab/list')

    expect(captured.headers.Authorization).toBe('Bearer token-abc')
    expect(body.code).toBe(200)
  })

  it('HTTP 200 但业务 code 非 200 时 reject', async () => {
    service.defaults.adapter = successAdapter({
      code: 409,
      message: '该时段已预约',
      data: null
    })

    await expect(service.post('/api/reservation')).rejects.toMatchObject({
      code: 409
    })
    expect(errorMessageMock).toHaveBeenCalledWith('该时段已预约')
  })

  it('登录接口 401 只提示，不清理会话、不跳转', async () => {
    service.defaults.adapter = errorAdapter(401, {
      code: 401,
      message: '账号或密码错误'
    })

    await expect(
      service.post('/api/auth/login', { username: 'u', password: 'bad' })
    ).rejects.toMatchObject({ code: 401 })

    expect(errorMessageMock).toHaveBeenCalledWith('账号或密码错误')
    expect(clearUserMock).not.toHaveBeenCalled()
    expect(pushMock).not.toHaveBeenCalled()
  })

  it('普通接口 401 清理会话并跳登录', async () => {
    service.defaults.adapter = errorAdapter(401, {
      code: 401,
      message: '登录已失效'
    })

    await expect(service.get('/api/user/list')).rejects.toMatchObject({
      code: 401
    })

    expect(errorMessageMock).toHaveBeenCalledWith('登录状态已失效，请重新登录')
    expect(clearUserMock).toHaveBeenCalledTimes(1)
    expect(pushMock).toHaveBeenCalledWith('/login')
  })

  it('skipAuthHandler 的 401 交给调用方处理', async () => {
    service.defaults.adapter = errorAdapter(
      401,
      { code: 401, message: '登录已失效' },
      { skipAuthHandler: true }
    )

    await expect(
      service.get('/api/user/me', { skipAuthHandler: true })
    ).rejects.toMatchObject({ code: 401 })

    expect(clearUserMock).not.toHaveBeenCalled()
    expect(pushMock).not.toHaveBeenCalled()
    expect(errorMessageMock).not.toHaveBeenCalled()
  })

  it('403 只提示，不清理会话、不跳转', async () => {
    service.defaults.adapter = errorAdapter(403, {
      code: 403,
      message: '无权限访问'
    })

    await expect(service.get('/api/user/list')).rejects.toMatchObject({
      code: 403
    })

    expect(errorMessageMock).toHaveBeenCalledWith('无权限访问')
    expect(clearUserMock).not.toHaveBeenCalled()
    expect(pushMock).not.toHaveBeenCalled()
  })
})
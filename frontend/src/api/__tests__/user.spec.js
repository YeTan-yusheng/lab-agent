import { beforeEach, describe, expect, it, vi } from 'vitest'

const { requestMock } = vi.hoisted(() => ({
  requestMock: vi.fn()
}))

vi.mock('@/utils/request', () => ({
  default: requestMock
}))

import { createUserApi, updateUserApi, updateUserRolesApi } from '@/api/user'

describe('user API 协议', () => {
  beforeEach(() => {
    requestMock.mockReset()
    requestMock.mockResolvedValue({ code: 200 })
  })

  it('创建用户按后端协议发送 roles 数组', async () => {
    const payload = {
      username: 'teacher02',
      password: '123456',
      name: '教师二',
      roles: ['teacher'],
      status: 1
    }

    await createUserApi(payload)

    expect(requestMock).toHaveBeenCalledWith({
      url: '/api/user',
      method: 'post',
      data: payload
    })
    expect(requestMock.mock.calls[0][0].data.roles).toEqual(['teacher'])
  })

  it('更新资料接口不发送 roles 字段', async () => {
    const payload = { name: '新名字', email: 'new@example.com', status: 1 }

    await updateUserApi(7, payload)

    expect(requestMock).toHaveBeenCalledWith({
      url: '/api/user/7',
      method: 'put',
      data: payload
    })
    expect(requestMock.mock.calls[0][0].data).not.toHaveProperty('roles')
  })

  it('角色更新接口发送 roles 数组', async () => {
    await updateUserRolesApi(7, ['teacher', 'admin'])

    expect(requestMock).toHaveBeenCalledWith({
      url: '/api/user/7/roles',
      method: 'put',
      data: { roles: ['teacher', 'admin'] }
    })
  })

  it('提供用户详情 API，供编辑时回显完整角色', async () => {
    const api = await import('@/api/user')

    expect(api.getUserDetailApi).toBeTypeOf('function')
  })
})
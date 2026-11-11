import { beforeEach, describe, expect, it, vi } from 'vitest'

const { getUserInfoMock } = vi.hoisted(() => ({
  getUserInfoMock: vi.fn()
}))

vi.mock('@/api/user', () => ({
  getUserInfo: getUserInfoMock
}))

const studentUser = {
  id: 1,
  username: 'student01',
  name: '学生一',
  role: 'student',
  roles: ['student'],
  capabilities: ['book_equipment', 'use_ai'],
  primary_role: 'student',
  display_name: '学生'
}

const teacherUser = {
  id: 2,
  username: 'teacher01',
  name: '教师一',
  role: 'teacher',
  roles: ['teacher'],
  capabilities: ['book_equipment', 'book_lab', 'use_ai'],
  primary_role: 'teacher',
  display_name: '教师'
}

async function loadStore() {
  const { useUser } = await import('@/utils/user')
  return useUser()
}

describe('useUser 登录态', () => {
  beforeEach(() => {
    vi.resetModules()
    localStorage.clear()
    getUserInfoMock.mockReset()
  })

  it('saveLoginData 保存 token、用户信息并标记已校准', async () => {
    const store = await loadStore()

    store.saveLoginData({ token: 'token-1', user: studentUser })

    expect(localStorage.getItem('token')).toBe('token-1')
    expect(JSON.parse(localStorage.getItem('userInfo'))).toEqual(studentUser)
    expect(store.userInfo.value).toEqual(studentUser)
    expect(store.hydrated.value).toBe(true)
  })

  it('updateUser 同步内存和 localStorage', async () => {
    const store = await loadStore()
    const updated = { ...studentUser, name: '新名字' }

    store.updateUser(updated)

    expect(store.userInfo.value).toEqual(updated)
    expect(JSON.parse(localStorage.getItem('userInfo'))).toEqual(updated)
  })

  it('clearUser 清理 token、用户信息和 hydrated', async () => {
    const store = await loadStore()
    store.saveLoginData({ token: 'token-1', user: studentUser })

    store.clearUser()

    expect(localStorage.getItem('token')).toBeNull()
    expect(localStorage.getItem('userInfo')).toBeNull()
    expect(store.userInfo.value).toBeNull()
    expect(store.hydrated.value).toBe(false)
  })
})

describe('useUser 能力判断', () => {
  beforeEach(() => {
    vi.resetModules()
    localStorage.clear()
    getUserInfoMock.mockReset()
  })

  it('can 只判断当前用户具备的能力', async () => {
    const store = await loadStore()
    store.saveLoginData({ token: 'token-1', user: studentUser })

    expect(store.can('book_equipment')).toBe(true)
    expect(store.can('book_lab')).toBe(false)
    expect(store.can('manage_users')).toBe(false)
  })

  it('hasAny 是“任意一个”，不是“全部”', async () => {
    const store = await loadStore()
    store.saveLoginData({ token: 'token-1', user: teacherUser })

    expect(store.hasAny(['book_lab', 'manage_users'])).toBe(true)
    expect(store.hasAny(['manage_users', 'audit_reservation'])).toBe(false)
    expect(store.hasAny([])).toBe(false)
  })

  it('hasAll 要求全部具备', async () => {
    const store = await loadStore()
    store.saveLoginData({ token: 'token-1', user: teacherUser })

    expect(store.hasAll(['book_lab', 'book_equipment'])).toBe(true)
    expect(store.hasAll(['book_lab', 'manage_users'])).toBe(false)
  })
})

describe('useUser 启动校准', () => {
  beforeEach(() => {
    vi.resetModules()
    localStorage.clear()
    getUserInfoMock.mockReset()
  })

  it('无 token 时返回 null 并清空用户', async () => {
    const store = await loadStore()

    const user = await store.hydrateUser()

    expect(user).toBeNull()
    expect(store.userInfo.value).toBeNull()
    expect(store.hydrated.value).toBe(false)
    expect(getUserInfoMock).not.toHaveBeenCalled()
  })

  it('有 token 时调用 /me，覆盖内存状态并设置 hydrated', async () => {
    localStorage.setItem('token', 'token-1')
    getUserInfoMock.mockResolvedValue({ code: 200, data: studentUser })
    const store = await loadStore()

    const user = await store.hydrateUser()

    expect(getUserInfoMock).toHaveBeenCalledTimes(1)
    expect(user).toEqual(studentUser)
    expect(store.userInfo.value).toEqual(studentUser)
    expect(JSON.parse(localStorage.getItem('userInfo'))).toEqual(studentUser)
    expect(store.hydrated.value).toBe(true)
  })

  it('并发调用只请求一次 /me', async () => {
    localStorage.setItem('token', 'token-1')
    getUserInfoMock.mockResolvedValue({ code: 200, data: studentUser })
    const store = await loadStore()

    const [first, second] = await Promise.all([
      store.hydrateUser(),
      store.hydrateUser()
    ])

    expect(getUserInfoMock).toHaveBeenCalledTimes(1)
    expect(first).toEqual(studentUser)
    expect(second).toEqual(studentUser)
  })

  it('/me 返回 401 时清理登录态', async () => {
    localStorage.setItem('token', 'token-1')
    getUserInfoMock.mockRejectedValue({ code: 401, message: 'expired' })
    const store = await loadStore()

    const user = await store.hydrateUser()

    expect(user).toBeNull()
    expect(localStorage.getItem('token')).toBeNull()
    expect(store.userInfo.value).toBeNull()
    expect(store.hydrated.value).toBe(false)
  })

  it('已校准后再次调用不重复请求', async () => {
    localStorage.setItem('token', 'token-1')
    getUserInfoMock.mockResolvedValue({ code: 200, data: studentUser })
    const store = await loadStore()

    await store.hydrateUser()
    await store.hydrateUser()

    expect(getUserInfoMock).toHaveBeenCalledTimes(1)
  })
})
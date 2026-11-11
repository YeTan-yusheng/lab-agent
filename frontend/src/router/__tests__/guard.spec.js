import { beforeEach, describe, expect, it, vi } from 'vitest'

const { hydrateUserMock } = vi.hoisted(() => ({
  hydrateUserMock: vi.fn()
}))

vi.mock('@/utils/user', () => ({
  useUser: () => ({ hydrateUser: hydrateUserMock })
}))

import router from '@/router'

const student = {
  id: 1,
  username: 'student01',
  roles: ['student'],
  capabilities: ['book_equipment', 'use_ai'],
  primary_role: 'student',
  display_name: '学生'
}

const teacher = {
  id: 2,
  username: 'teacher01',
  roles: ['teacher'],
  capabilities: ['book_equipment', 'book_lab', 'use_ai'],
  primary_role: 'teacher',
  display_name: '教师'
}

const admin = {
  id: 3,
  username: 'admin01',
  roles: ['admin'],
  capabilities: [
    'manage_resources',
    'audit_reservation',
    'view_admin_stats',
    'manage_users',
    'manage_kb',
    'use_ai'
  ],
  primary_role: 'admin',
  display_name: '管理员'
}

const teacherAdmin = {
  id: 4,
  username: 'teacher_admin01',
  roles: ['teacher', 'admin'],
  capabilities: [
    'book_equipment',
    'book_lab',
    'manage_resources',
    'audit_reservation',
    'view_admin_stats',
    'manage_users',
    'manage_kb',
    'use_ai'
  ],
  primary_role: 'admin',
  display_name: '教师/管理员'
}

async function go(path) {
  await router.push(path).catch(() => {})
  return router.currentRoute.value
}

describe('router 认证与能力守卫', () => {
  beforeEach(async () => {
    localStorage.clear()
    hydrateUserMock.mockReset()
    await router.push('/login').catch(() => {})
  })

  it('无 token 访问受保护页面时回登录并带 redirect', async () => {
    const route = await go('/manager/home')

    expect(route.path).toBe('/login')
    expect(route.query.redirect).toBe('/manager/home')
  })

  it('token 无效时清理后回登录', async () => {
    localStorage.setItem('token', 'invalid-token')
    hydrateUserMock.mockResolvedValue(null)

    const route = await go('/manager/user')

    expect(route.path).toBe('/login')
    expect(route.query.redirect).toBe('/manager/user')
  })

  it('学生访问用户管理进入 403', async () => {
    localStorage.setItem('token', 'student-token')
    hydrateUserMock.mockResolvedValue(student)

    const route = await go('/manager/user')

    expect(route.path).toBe('/403')
  })

  it('学生访问实验室管理进入 403', async () => {
    localStorage.setItem('token', 'student-token')
    hydrateUserMock.mockResolvedValue(student)

    const route = await go('/manager/lab')

    expect(route.path).toBe('/403')
  })

  it('纯管理员访问我的预约进入 403', async () => {
    localStorage.setItem('token', 'admin-token')
    hydrateUserMock.mockResolvedValue(admin)

    const route = await go('/manager/my-reservation')

    expect(route.path).toBe('/403')
  })

  it('教师访问审核页进入 403', async () => {
    localStorage.setItem('token', 'teacher-token')
    hydrateUserMock.mockResolvedValue(teacher)

    const route = await go('/manager/audit-reservation')

    expect(route.path).toBe('/403')
  })

  it('教师可以访问我的预约', async () => {
    localStorage.setItem('token', 'teacher-token')
    hydrateUserMock.mockResolvedValue(teacher)

    const route = await go('/manager/my-reservation')

    expect(route.path).toBe('/manager/my-reservation')
  })

  it('教师+管理员可以进入管理页和预约页', async () => {
    localStorage.setItem('token', 'teacher-admin-token')
    hydrateUserMock.mockResolvedValue(teacherAdmin)

    const userRoute = await go('/manager/user')
    expect(userRoute.path).toBe('/manager/user')

    const reservationRoute = await go('/manager/my-reservation')
    expect(reservationRoute.path).toBe('/manager/my-reservation')
  })
})
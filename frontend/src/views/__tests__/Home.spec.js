import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/utils/user', async () => {
  const { ref } = await import('vue')
  const userInfo = ref(null)
  return {
    setTestUser: (user) => {
      userInfo.value = user
    },
    useUser: () => ({
      userInfo,
      can: (capability) => Boolean(userInfo.value?.capabilities?.includes(capability)),
      hasAny: (capabilities) =>
        capabilities.some((capability) =>
          userInfo.value?.capabilities?.includes(capability)
        )
    })
  }
})

vi.mock('@/api/lab', () => ({
  getLabPageList: vi.fn().mockResolvedValue({ code: 200, data: { total: 1 } })
}))

vi.mock('@/api/reservation', () => ({
  getReservationPageList: vi.fn().mockResolvedValue({ code: 200, data: { total: 2 } })
}))

import { setTestUser } from '@/utils/user'
import Home from '@/views/Home.vue'

const stubs = {
  'el-card': {
    template: '<div><slot name="header" /><slot /></div>'
  },
  'el-row': { template: '<div><slot /></div>' },
  'el-col': { template: '<div><slot /></div>' },
  'el-button': {
    emits: ['click'],
    template: '<button type="button" @click="$emit(\'click\')"><slot /></button>'
  }
}

const student = {
  id: 1,
  role: 'student',
  roles: ['student'],
  capabilities: ['book_equipment', 'use_ai'],
  display_name: '学生'
}

const teacher = {
  id: 2,
  role: 'teacher',
  roles: ['teacher'],
  capabilities: ['book_equipment', 'book_lab', 'use_ai'],
  display_name: '教师'
}

const admin = {
  id: 3,
  role: 'admin',
  roles: ['admin'],
  capabilities: [
    'manage_resources',
    'audit_reservation',
    'view_admin_stats',
    'manage_users',
    'manage_kb',
    'use_ai'
  ],
  display_name: '管理员'
}

const teacherAdmin = {
  id: 4,
  role: 'admin',
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
  display_name: '教师/管理员'
}

async function shortcutLabels(user) {
  setTestUser(user)
  const wrapper = mount(Home, {
    global: { stubs }
  })
  await flushPromises()
  return wrapper
    .findAll('button')
    .map((button) => button.text())
    .filter((text) => text !== '打开 AI 助手')
}

describe('Home 快捷入口按能力显示', () => {
  beforeEach(() => {
    setTestUser(null)
  })

  it('学生看到 AI、实验室列表和我的预约，没有管理入口', async () => {
    const labels = await shortcutLabels(student)

    expect(labels).toContain('AI 智能助手')
    expect(labels).toContain('实验室列表')
    expect(labels).toContain('我的预约')
    expect(labels).not.toContain('预约审核')
    expect(labels).not.toContain('用户管理')
  })

  it('教师没有管理入口', async () => {
    const labels = await shortcutLabels(teacher)

    expect(labels).toContain('我的预约')
    expect(labels).not.toContain('预约审核')
    expect(labels).not.toContain('实验室管理')
    expect(labels).not.toContain('设备管理')
    expect(labels).not.toContain('用户管理')
  })

  it('纯管理员不显示我的预约，显示管理和审核入口', async () => {
    const labels = await shortcutLabels(admin)

    expect(labels).not.toContain('我的预约')
    expect(labels).toContain('预约审核')
    expect(labels).toContain('实验室管理')
    expect(labels).toContain('设备管理')
    expect(labels).toContain('用户管理')
  })

  it('教师+管理员同时显示预约和管理入口', async () => {
    const labels = await shortcutLabels(teacherAdmin)

    expect(labels).toContain('我的预约')
    expect(labels).toContain('预约审核')
    expect(labels).toContain('实验室管理')
    expect(labels).toContain('设备管理')
    expect(labels).toContain('用户管理')
  })
})
import { describe, expect, it } from 'vitest'

import CapabilityDefault, {
  Capability,
  hasAll,
  hasAny,
  hasCapability
} from '../permissions'

const student = { capabilities: ['book_equipment', 'use_ai'] }
const teacher = { capabilities: ['book_equipment', 'book_lab', 'use_ai'] }
const admin = {
  capabilities: [
    'manage_resources',
    'audit_reservation',
    'view_admin_stats',
    'manage_users',
    'manage_kb',
    'use_ai'
  ]
}
const teacherAdmin = {
  capabilities: [...new Set([...teacher.capabilities, ...admin.capabilities])]
}

describe('Capability', () => {
  it('与后端能力值保持一致', () => {
    expect(Capability).toEqual({
      BOOK_EQUIPMENT: 'book_equipment',
      BOOK_LAB: 'book_lab',
      MANAGE_RESOURCES: 'manage_resources',
      AUDIT_RESERVATION: 'audit_reservation',
      VIEW_ADMIN_STATS: 'view_admin_stats',
      MANAGE_USERS: 'manage_users',
      MANAGE_KB: 'manage_kb',
      USE_AI: 'use_ai'
    })
    expect(CapabilityDefault).toBe(Capability)
  })

  it('是冻结对象，不能运行时修改', () => {
    expect(Object.isFrozen(Capability)).toBe(true)
  })
})

describe('hasCapability', () => {
  it('命中能力时返回 true', () => {
    expect(hasCapability(student, Capability.BOOK_EQUIPMENT)).toBe(true)
    expect(hasCapability(teacher, Capability.BOOK_LAB)).toBe(true)
    expect(hasCapability(admin, Capability.MANAGE_USERS)).toBe(true)
  })

  it('未命中能力时返回 false', () => {
    expect(hasCapability(student, Capability.BOOK_LAB)).toBe(false)
    expect(hasCapability(student, Capability.MANAGE_USERS)).toBe(false)
    expect(hasCapability(admin, Capability.BOOK_EQUIPMENT)).toBe(false)
  })

  it('用户或 capabilities 缺失时返回 false', () => {
    expect(hasCapability(null, Capability.USE_AI)).toBe(false)
    expect(hasCapability(undefined, Capability.USE_AI)).toBe(false)
    expect(hasCapability({}, Capability.USE_AI)).toBe(false)
    expect(hasCapability({ capabilities: null }, Capability.USE_AI)).toBe(false)
  })
})

describe('hasAny', () => {
  it('任意一个能力命中即返回 true', () => {
    expect(hasAny(student, [Capability.BOOK_LAB, Capability.BOOK_EQUIPMENT])).toBe(true)
    expect(hasAny(teacher, [Capability.BOOK_LAB, Capability.BOOK_EQUIPMENT])).toBe(true)
    expect(
      hasAny(teacherAdmin, [Capability.AUDIT_RESERVATION, Capability.BOOK_LAB])
    ).toBe(true)
  })

  it('全部未命中返回 false', () => {
    expect(hasAny(student, [Capability.BOOK_LAB, Capability.MANAGE_USERS])).toBe(false)
    expect(hasAny(admin, [Capability.BOOK_LAB, Capability.BOOK_EQUIPMENT])).toBe(false)
  })

  it('空数组返回 false', () => {
    expect(hasAny(student, [])).toBe(false)
  })
})

describe('hasAll', () => {
  it('全部命中返回 true', () => {
    expect(hasAll(teacher, [Capability.BOOK_LAB, Capability.BOOK_EQUIPMENT])).toBe(true)
    expect(
      hasAll(teacherAdmin, [
        Capability.BOOK_LAB,
        Capability.AUDIT_RESERVATION,
        Capability.MANAGE_USERS
      ])
    ).toBe(true)
  })

  it('缺少任意一个能力返回 false', () => {
    expect(hasAll(student, [Capability.BOOK_EQUIPMENT, Capability.BOOK_LAB])).toBe(false)
    expect(hasAll(admin, [Capability.MANAGE_USERS, Capability.BOOK_LAB])).toBe(false)
  })

  it('空数组返回 true，路由守卫应先判断数组长度', () => {
    expect(hasAll(student, [])).toBe(true)
  })
})
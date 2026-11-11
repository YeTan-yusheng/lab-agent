export const Capability = Object.freeze({
  BOOK_EQUIPMENT: 'book_equipment',
  BOOK_LAB: 'book_lab',
  MANAGE_RESOURCES: 'manage_resources',
  AUDIT_RESERVATION: 'audit_reservation',
  VIEW_ADMIN_STATS: 'view_admin_stats',
  MANAGE_USERS: 'manage_users',
  MANAGE_KB: 'manage_kb',
  USE_AI: 'use_ai'
})
export default Capability

export function hasCapability(user, capability) {
  /**
   * 检查用户是否有指定权限
   */
  return Boolean(user?.capabilities?.includes(capability))
}

export function hasAny(user, capabilities) {
  /**
   * 检查用户是否有部分指定权限
   */
  return capabilities.some((capability) => hasCapability(user, capability))
}

export function hasAll(user, capabilities) {
  /**
   * 检查用户是否有所有指定权限
   */
  return capabilities.every((capability) => hasCapability(user, capability))
}

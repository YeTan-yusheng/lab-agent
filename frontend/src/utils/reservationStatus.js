export const RESERVATION_STATUS = Object.freeze({
  PENDING: 0,
  APPROVED: 1,
  REJECTED: 2,
  CANCELLED: 3,
  EXPIRED: 4
})

const STATUS_TEXT = {
  0: '待审核',
  1: '已通过',
  2: '已拒绝',
  3: '已取消',
  4: '已过期'
}

const STATUS_TAG_TYPE = {
  0: 'warning',
  1: 'success',
  2: 'danger',
  3: 'info',
  4: 'info'
}

const ACTION_TEXT = {
  submit: '提交',
  approve: '通过',
  reject: '拒绝',
  cancel: '取消',
  force_cancel: '强制取消',
  expire: '过期'
}

const ACTION_TAG_TYPE = {
  submit: 'info',
  approve: 'success',
  reject: 'danger',
  cancel: 'warning',
  force_cancel: 'danger',
  expire: 'info'
}

export function statusText(status) {
  return STATUS_TEXT[Number(status)] || '-'
}

export function statusTagType(status) {
  return STATUS_TAG_TYPE[Number(status)] || 'info'
}

export function isTerminal(status) {
  // 判断是否为终态（已拒绝、已取消、已过期）
  return [2, 3, 4].includes(Number(status))
}

export function actionText(action) {
  return ACTION_TEXT[action] || action || '-'
}

export function actionTagType(action) {
  return ACTION_TAG_TYPE[action] || 'info'
}

export function parseStartAt(row) {
  // 将 row 中的 date 和 start_time 字段解析为 Date 对象
  if (!row?.date || !row?.start_time) return null
  const [year, month, day] = String(row.date).split('-').map(Number)
  const [hour, minute] = String(row.start_time).split(':').map(Number)
  if ([year, month, day, hour, minute].some(Number.isNaN)) return null
  return new Date(year, month - 1, day, hour, minute, 0, 0)
}

export function canOwnerCancel(row, now = new Date()) {
  // 判断是否可以由用户取消预约
  const status = Number(row?.status)
  if (status === RESERVATION_STATUS.PENDING) return true
  if (status !== RESERVATION_STATUS.APPROVED) return false
  const startAt = parseStartAt(row)
  if (!startAt) return false
  return startAt.getTime() - now.getTime() >= 12 * 60 * 60 * 1000 // 大于12小时可以取消
}

export function canForceCancel(row, now = new Date()) {
  // 已开始的预约不再允许管理员强制取消
  const status = Number(row?.status)
  if (status !== RESERVATION_STATUS.PENDING && status !== RESERVATION_STATUS.APPROVED) {
    return false
  }
  const startAt = parseStartAt(row)
  if (!startAt) return false
  return startAt.getTime() > now.getTime()
}

export function cancelHint(row, now = new Date()) {
  // 获取取消预约的提示信息
  const status = Number(row?.status)
  if (status === RESERVATION_STATUS.PENDING) return ''
  if (status === RESERVATION_STATUS.APPROVED && !canOwnerCancel(row, now)) {
    return '距开始不足 12 小时，无法取消'
  }
  if (isTerminal(status)) return '当前状态不可取消'
  return ''
}

export function formatDateTime(value) {
  // 格式化日期时间
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString()
}

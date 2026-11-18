const toDateString = (date) => {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}
export function todayString() {
  return toDateString(new Date())
}
// 校验是否过期
export function isPastDate(value) {
  return Boolean(value) && value < todayString()
}

// 将日期对象转换为字符串
const toDateString = (date) => {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}
// 获取今天的日期字符串
export function todayString() {
  return toDateString(new Date())
}
// 校验是否过期
export function isPastDate(value) {
  return Boolean(value) && value < todayString()
}
// 校验日期是否被禁用
export function isDateDisabled(date) {
  return toDateString(date) < todayString()
}
// 校验今天是否是闭馆日
export function isClosedToday(days){
  return days.some(day => day.date === todayString())
}
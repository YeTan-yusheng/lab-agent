import request from '@/utils/request'

// 创建预约
export function createReservationApi(data) {
  return request({
    url: '/api/reservation',
    method: 'post',
    data
  })
}

// 查看预约可用性
export function checkAvailabilityApi(data) {
  return request({
    url: '/api/reservation/availability',
    method: 'post',
    data
  })
}

// 查看某天可预约区间
export function getDayAvailabilityApi(data) {
  return request({
    url: '/api/reservation/availability/day',
    method: 'post',
    data
  })
}

// 预约查看列表
export function getReservationPageList(params) {
  return request({
    url: '/api/reservation/list',
    method: 'get',
    params
  })
}

// 取消预约
export function cancelReservationApi(id, data = {}) {
  return request({
    url: `/api/reservation/${id}/cancel`,
    method: 'put',
    data
  })
}

// 审核预约
export function auditReservationApi(id, data) {
  const payload = typeof data === 'number' ? { status: data } : data
  return request({
    url: `/api/reservation/${id}/audit`,
    method: 'put',
    data: payload
  })
}

// 预约状态历史
export function getReservationHistoryApi(id) {
  return request({
    url: `/api/reservation/${id}/history`,
    method: 'get'
  })
}

// 待审核数量
export function getAuditPendingCountApi() {
  return request({
    url: '/api/reservation/audit/pending-count',
    method: 'get'
  })
}

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
export function cancelReservationApi(id) {
  return request({
    url: `/api/reservation/${id}/cancel`,
    method: 'put'
  })
}

// 审核预约
export function auditReservationApi(id, status) {
  return request({
    url: `/api/reservation/${id}/audit`,
    method: 'put',
    data: { status }
  })
}

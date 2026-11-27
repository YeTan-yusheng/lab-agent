import request from '@/utils/request'

// 站内信列表
export function getNotificationList(params) {
  return request({
    url: '/api/notification/list',
    method: 'get',
    params
  })
}

// 未读数量
export function getNotificationUnreadCount() {
  return request({
    url: '/api/notification/unread-count',
    method: 'get'
  })
}

// 单条已读
export function markNotificationRead(id) {
  return request({
    url: `/api/notification/${id}/read`,
    method: 'put'
  })
}

// 全部已读
export function markAllNotificationsRead() {
  return request({
    url: '/api/notification/read-all',
    method: 'put'
  })
}
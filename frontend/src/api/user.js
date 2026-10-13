import request from '@/utils/request'

export function getUserInfo(data) {
  return request({
    url: '/api/user/info',
    method: 'get'
  })
}

export function updateUserInfo(data) {
  return request({
    url: '/api/user/update',
    method: 'put',
    data
  })
}

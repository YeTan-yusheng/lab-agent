import request from '@/utils/request'

export function getUserInfo() {
  return request({
    url: '/api/user/me',
    method: 'get',
    skipAuthHandler: true
  })
}

export function updateUserInfo(data) {
  return request({
    url: '/api/user/me',
    method: 'put',
    data
  })
}

export function updatePassword(data) {
  return request({
    url: '/api/user/password',
    method: 'put',
    data
  })
}

// 分页模糊查询用户列表
export function getUserPageList(params) {
  return request({
    url: '/api/user/list',
    method: 'get',
    params
  })
}

// 新增用户
export function createUserApi(data) {
  return request({
    url: '/api/user',
    method: 'post',
    data
  })
}

//更新用户
export function updateUserApi(userId, data) {
  return request({
    url: `/api/user/${userId}`,
    method: 'put',
    data
  })
}

// 更新用户角色
export function updateUserRolesApi(userId, roles) {
  return request({
    url: `/api/user/${userId}/roles`,
    method: 'put',
    data: { roles }
  })
}

// 用户详情
export function getUserDetailApi(userId) {
  return request({
    url: `/api/user/${userId}`,
    method: 'get'
  })
}

// 删除用户
export function deleteUserApi(userId) {
  return request({
    url: `/api/user/${userId}`,
    method: 'delete'
  })
}

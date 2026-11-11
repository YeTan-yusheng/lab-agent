import { ref } from 'vue'
import { getUserInfo, setToken, setUserInfo, logout, getToken } from './auth'
import * as permissions from './permissions'

const userInfo = ref(getUserInfo())
const hydrated = ref(false) // 是否已初始化
let hydratePromise = null //防止重复请求

export function useUser() {
  /**
   * 返回当前用户状态和相关操作函数
   */
  function saveLoginData(data) {
    /**
     * 保存登录数据
     * @param {Object} data - 登录数据
     */
    setToken(data.token)
    setUserInfo(data.user)
    userInfo.value = data.user
    hydrated.value = true
  }

  function updateUser(user) {
    /**
     * 更新用户信息
     * @param {Object} user - 用户信息
     */
    setUserInfo(user)
    userInfo.value = user
  }

  function clearUser() {
    /**
     * 清除用户信息
     */
    logout()
    userInfo.value = null
    hydrated.value = false
    hydratePromise = null
  }

  async function hydrateUser() {
    /**
     * 使用'/me'接口获取用户信息校验登录态
     */
    if (hydrated.value) return userInfo.value
    if (!getToken()) {
      clearUser()
      return null
    }

    if (!hydratePromise) {
      hydratePromise = import('../api/user')
        .then(({ getUserInfo }) => getUserInfo())
        .then((res) => {
          updateUser(res.data)
          hydrated.value = true
          return res.data
        })
        .catch((err) => {
          if (err?.code === 401) {
            clearUser()
          }
          return null
        })
        .finally(() => {
          hydratePromise = null
        })
    }
    return hydratePromise
  }

  function can(capability) {
    /**
     * 检查用户是否有指定权限
     */
    return permissions.hasCapability(userInfo.value, capability)
  }

  function hasAny(capabilities) {
    /**
     * 检查用户是否有部分指定权限
     */
    return permissions.hasAny(userInfo.value, capabilities)
  }

  function hasAll(capabilities) {
    /**
     * 检查用户是否有所有指定权限
     */
    return permissions.hasAll(userInfo.value, capabilities)
  }

  return {
    userInfo,
    hydrated,
    saveLoginData,
    updateUser,
    clearUser,
    hydrateUser,
    can,
    hasAny,
    hasAll
  }
}

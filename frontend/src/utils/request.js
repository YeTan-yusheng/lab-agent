import axios from 'axios'
import { getToken, logout } from './auth'
import { ElMessage } from 'element-plus'
import router from '@/router'

const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 30000
})

//请求拦截器
service.interceptors.request.use(
  (config) => {
    const token = getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (err) => Promise.reject(err)
)

service.interceptors.response.use(
  (res) => {
    const data = res.data
    if (data.code !== 200) {
      ElMessage.error(data.message || '请求失败')
      return Promise.reject(data)
    }
    return data
  },
  (err) => {
    const status = err.response?.status
    const data = err.response?.data
    const message = data?.message || '请求失败'
    const isLoginRequest = String(err.config?.url || '').includes('/api/auth/login')

    if (status === 401) {
      if (isLoginRequest) {
        // 登录失败提示账号密码错误/账号禁用
        ElMessage.error(message)
      } else {
        ElMessage.error('登录状态已失效，请重新登录')
        logout()
        router.push('/login')
      }
    } else if (status === 403) {
      ElMessage.error(message || '无权限访问')
    } else {
      ElMessage.error(message)
    }
    return Promise.reject(data || err)
  }
)

export default service

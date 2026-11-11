import { getToken } from '@/utils/auth'
import { createRouter, createWebHistory } from 'vue-router'
import { useUser } from '@/utils/user'
import { hasAll, hasAny } from '@/utils/permissions'
import Capability from '@/utils/permissions'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/manager/home' },
    {
      path: '/manager',
      name: 'Layout',
      component: () => import('@/layouts/Layout.vue'),
      meta: {
        requiresAuth: true
      },
      children: [
        {
          path: 'home',
          name: 'Home',
          component: () => import('@/views/Home.vue')
        },
        {
          path: 'lab',
          name: 'Lab',
          component: () => import('@/views/Lab.vue'),
          meta: { requiredCapabilities: [Capability.MANAGE_RESOURCES] }
        },
        {
          path: 'lablist',
          name: 'LabList',
          component: () => import('@/views/LabList.vue')
        },
        {
          path: 'profile',
          name: 'Profile',
          component: () => import('@/views/Profile.vue')
        },
        {
          path: 'password',
          name: 'Password',
          component: () => import('@/views/Password.vue')
        },
        {
          path: 'user',
          name: 'User',
          component: () => import('@/views/User.vue'),
          meta: { requiredCapabilities: [Capability.MANAGE_USERS] }
        },
        {
          path: 'equ',
          name: 'Equipment',
          component: () => import('@/views/Equ.vue'),
          meta: {
            requiredCapabilities: [Capability.MANAGE_RESOURCES]
          }
        },
        {
          path: 'lab-equipment',
          name: 'LabEquipment',
          component: () => import('@/views/LabEquipment.vue')
        },
        {
          path: 'my-reservation',
          name: 'MyReservation',
          component: () => import('@/views/MyReservation.vue'),
          meta: {
            anyCapabilities: [Capability.BOOK_EQUIPMENT, Capability.BOOK_LAB]
          }
        },
        {
          path: 'audit-reservation',
          name: 'AuditReservation',
          component: () => import('@/views/AuditReservation.vue'),
          meta: {
            requiredCapabilities: [Capability.AUDIT_RESERVATION]
          }
        },
        {
          path: 'ai-chat',
          name: 'AiChat',
          component: () => import('@/views/AiChat.vue'),
          meta: {
            requiredCapabilities: [Capability.USE_AI]
          }
        }
      ]
    },
    { path: '/login', name: 'Login', component: () => import('@/views/Login.vue') },
    { path: '/register', name: 'Register', component: () => import('@/views/Register.vue') },
    { path: '/403', name: '403', component: () => import('@/views/403.vue') },
    // 兜底路由
    { path: '/:pathMatch(.*)*', redirect: '/manager/home' }
  ]
})

const PUBLIC_PATHS = ['/login', '/register']
router.beforeEach(async (to) => {
  const { hydrateUser } = useUser()
  const token = getToken()

  if (PUBLIC_PATHS.includes(to.path)) {
    // 判断是否已经登录
    if (!token) return true

    const user = await hydrateUser()
    return user ? '/manager/home' : true
  }

  if (!token) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  const user = await hydrateUser()
  if (!user) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  const required = to.meta.requiredCapabilities || []
  const any = to.meta.anyCapabilities || []

  if (required.length && !hasAll(user, required)) return '/403'
  if (any.length && !hasAny(user, any)) return '/403'

  return true
})
export default router

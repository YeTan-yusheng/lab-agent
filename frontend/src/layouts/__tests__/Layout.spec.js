import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { resourceStubs } from '@/views/__tests__/resourceStubs'

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  startPolling: vi.fn(),
  stopPolling: vi.fn(),
  refreshPendingCount: vi.fn()
}))

vi.mock('@/router', () => ({
  default: { push: mocks.push }
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ path: '/manager/home' })
}))

vi.mock('@/utils/user', async () => {
  const { ref } = await import('vue')
  return {
    useUser: () => ({
      userInfo: ref({ id: 1, name: '测试用户', avatar: '' }),
      clearUser: vi.fn(),
      can: () => true,
      hasAny: () => true
    })
  }
})

vi.mock('@/composables/useAuditPendingCount', async () => {
  const { ref } = await import('vue')
  return {
    useAuditPendingCount: () => ({
      pendingCount: ref(0),
      refresh: mocks.refreshPendingCount
    })
  }
})

vi.mock('@/composables/useNotificationCount', async () => {
  const { ref } = await import('vue')
  return {
    useNotificationCount: () => ({
      unreadCount: ref(2),
      startPolling: mocks.startPolling,
      stopPolling: mocks.stopPolling
    })
  }
})

import Layout from '@/layouts/Layout.vue'

const layoutStubs = {
  ...resourceStubs,
  'el-container': { template: '<div><slot /></div>' },
  'el-header': { template: '<div><slot /></div>' },
  'el-aside': { template: '<div><slot /></div>' },
  'el-main': { template: '<div><slot /></div>' },
  'el-menu': { template: '<div><slot /></div>' },
  'el-menu-item': { template: '<div class="menu-item"><slot /></div>' },
  'el-dropdown': { template: '<div><slot /><slot name="dropdown" /></div>' },
  'el-dropdown-menu': { template: '<div><slot /></div>' },
  'el-dropdown-item': { template: '<div><slot /></div>' },
  'router-view': true
}

function mountLayout() {
  return mount(Layout, {
    global: {
      stubs: layoutStubs,
      directives: { loading: {} }
    }
  })
}

describe('Layout notification entry', () => {
  beforeEach(() => {
    mocks.push.mockReset()
    mocks.startPolling.mockReset()
    mocks.stopPolling.mockReset()
    mocks.refreshPendingCount.mockReset()
  })

  it('starts polling and shows the unread badge', () => {
    const wrapper = mountLayout()

    expect(mocks.startPolling).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('2')
  })

  it('opens the notification center and stops polling on unmount', async () => {
    const wrapper = mountLayout()

    await wrapper.find('[title="消息中心"]').trigger('click')
    expect(mocks.push).toHaveBeenCalledWith('/manager/notifications')

    wrapper.unmount()
    expect(mocks.stopPolling).toHaveBeenCalledTimes(1)
  })
})
<template>
  <div>
    <el-container style="min-height: 100vh">
      <el-header
        style="
          display: flex;
          align-items: center;
          border-bottom: 1px solid #ddd;
          background-color: #fff;
        "
      >
        <div
          style="flex: 1; display: flex; align-items: center; font-size: 24px; font-weight: bold"
        >
          <img style="width: 40px" src="@/assets/imgs/logo.png" alt="" />
          <div style="margin-left: 5px">智能实验室预约系统</div>
        </div>

        <div>
          <el-dropdown @command="handleCommand">
            <div style="display: flex; align-items: center; cursor: pointer">
              <img :src="userInfo?.avatar" alt="" style="width: 30px; border-radius: 50%" />
              <div style="margin-left: 3px">{{ userInfo?.name }}</div>
            </div>

            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人信息</el-dropdown-item>
                <el-dropdown-item command="password">修改密码</el-dropdown-item>
                <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-container>
        <el-aside width="220px">
          <el-menu router :default-active="route.path">
            <el-menu-item v-for="item in visibleMenus" :key="item.path" :index="item.path">
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ item.label }}</span>
            </el-menu-item>
          </el-menu>
        </el-aside>

        <el-main>
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup>
import {
  Menu as IconMenu,
  House,
  Setting,
  User,
  OfficeBuilding,
  Tickets,
  Checked,
  ChatDotRound
} from '@element-plus/icons-vue'
import router from '@/router'
import { useUser } from '@/utils/user'
import { Capability } from '@/utils/permissions'
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const { userInfo, clearUser, can, hasAny } = useUser()
const route = useRoute()

const handleCommand = (command) => {
  if (command == 'profile') {
    router.push('/manager/profile')
  } else if (command == 'logout') {
    clearUser()
    router.push('/login')
  } else if (command == 'password') {
    router.push('/manager/password')
  }
}

const menus = [
  { label: '系统首页', path: '/manager/home', icon: IconMenu },
  {
    label: 'AI 智能助手',
    path: '/manager/ai-chat',
    icon: ChatDotRound,
    capability: Capability.USE_AI
  },
  { label: '实验室列表', path: '/manager/lablist', icon: OfficeBuilding },
  {
    label: '我的预约',
    path: '/manager/my-reservation',
    icon: Tickets,
    anyCapabilities: [Capability.BOOK_EQUIPMENT, Capability.BOOK_LAB]
  },
  {
    label: '预约审核',
    path: '/manager/audit-reservation',
    icon: Checked,
    capability: Capability.AUDIT_RESERVATION
  },
  {
    label: '实验室管理',
    path: '/manager/lab',
    icon: House,
    capability: Capability.MANAGE_RESOURCES
  },
  {
    label: '设备管理',
    path: '/manager/equ',
    icon: Setting,
    capability: Capability.MANAGE_RESOURCES
  },
  {
    label: '用户管理',
    path: '/manager/user',
    icon: User,
    capability: Capability.MANAGE_USERS
  }
]

const visibleMenus = computed(() =>
  menus.filter((item) => {
    if (item.capability) return can(item.capability)
    if (item.anyCapabilities) return hasAny(item.anyCapabilities)
    return true
  })
)
</script>

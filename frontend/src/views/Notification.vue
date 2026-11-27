<template>
  <div>
    <el-card>
      <template #header>
        <div style="display: flex; align-items: center; justify-content: space-between">
          <div style="font-size: 16px; font-weight: bold">
            <span>消息中心</span>
            <el-tag v-if="unreadCount" type="warning" style="margin-left: 8px">
              未读：{{ unreadCount }}
            </el-tag>
          </div>
          <el-button type="primary" text bg @click="handleReadAll">全部已读</el-button>
        </div>
      </template>

      <div style="margin-bottom: 10px; display: flex; gap: 8px">
        <el-button :type="readFilter === 'all' ? 'primary' : ''" text bg @click="setFilter('all')">
          全部
        </el-button>
        <el-button
          :type="readFilter === 'unread' ? 'primary' : ''"
          text
          bg
          @click="setFilter('unread')"
        >
          未读
        </el-button>
        <el-button
          :type="readFilter === 'read' ? 'primary' : ''"
          text
          bg
          @click="setFilter('read')"
        >
          已读
        </el-button>
      </div>

      <el-table
        :header-cell-style="{ backgroundColor: '#f5f7fa', color: '#333' }"
        :data="tableData"
        style="width: 100%"
        v-loading="loading"
      >
        <el-table-column label="状态" min-width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_read ? 'info' : 'warning'">
              {{ row.is_read ? '已读' : '未读' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="140" />
        <el-table-column prop="content" label="内容" min-width="320" />
        <el-table-column label="时间" min-width="180">
          <template #default="{ row }">{{ formatDateTime(row.create_time) }}</template>
        </el-table-column>
        <el-table-column label="操作" min-width="210">
          <template #default="{ row }">
            <el-button v-if="!row.is_read" type="primary" text bg @click="handleRead(row)">
              标记已读
            </el-button>
            <el-button v-if="row.reservation_id" type="primary" text bg @click="goReservation(row)">
              {{ isAuditAction(row) ? '去审核' : '查看我的预约' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div style="margin-top: 10px; display: flex; justify-content: flex-end">
        <el-pagination
          v-model:current-page="params.page"
          v-model:page-size="params.page_size"
          :total="total"
          background
          layout="total, prev, pager, next"
          @current-change="load"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
  getNotificationList,
  markAllNotificationsRead,
  markNotificationRead
} from '@/api/notification'
import { ElMessage } from 'element-plus'
import router from '@/router'
import { formatDateTime } from '@/utils/reservationStatus'
import { useNotificationCount } from '@/composables/useNotificationCount'
import { useUser } from '@/utils/user'
import Capability from '@/utils/permissions'

const { can } = useUser()
const canAudit = computed(() => can(Capability.AUDIT_RESERVATION))
const { unreadCount, refresh } = useNotificationCount()
const loading = ref(false)
const tableData = ref([])
const total = ref(0)
const readFilter = ref('all')
const params = reactive({
  page: 1,
  page_size: 10,
  is_read: null
})

const load = async () => {
  params.is_read = readFilter.value === 'all' ? null : readFilter.value === 'unread' ? false : true
  loading.value = true
  try {
    const res = await getNotificationList(params)
    if (res.code === 200) {
      tableData.value = res.data?.list || []
      total.value = res.data?.total ?? 0
    }
  } catch {
  } finally {
    loading.value = false
  }
}

const setFilter = (filter) => {
  readFilter.value = filter
  params.page = 1
  load()
}

const handleRead = async (row) => {
  try {
    const res = await markNotificationRead(row.id)
    if (res.code === 200) {
      ElMessage.success('已标记为已读')
      await Promise.all([load(), refresh()])
    }
  } catch {}
}

const handleReadAll = async () => {
  try {
    const res = await markAllNotificationsRead()
    if (res.code === 200) {
      ElMessage.success('全部通知已读')
      await Promise.all([load(), refresh()])
    }
  } catch {}
}

const isAuditAction = (row) => {
  return canAudit.value && row.type === 'reservation_submitted'
}

const goReservation = async (row) => {
  if (!row.is_read) {
    try {
      const res = await markNotificationRead(row.id)
      if (res.code === 200) {
        row.is_read = true
        await refresh()
      }
    } catch {}
  }
  router.push(isAuditAction(row) ? '/manager/audit-reservation' : '/manager/my-reservation')
}

onMounted(() => {
  load()
  refresh()
})
</script>

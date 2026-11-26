<template>
  <div>
    <el-card>
      <template #header>
        <div style="font-size: 16px; font-weight: bold">
          <span>我的预约记录</span>
        </div>
      </template>
      <div style="margin-bottom: 10px">
        <el-select
          placeholder="请选择状态"
          v-model="params.status"
          style="width: 200px; margin-right: 8px"
          clearable
          @change="handleSearch"
          @clear="handleSearch"
        >
          <el-option :value="0" label="待审核" />
          <el-option :value="1" label="已通过" />
          <el-option :value="2" label="已拒绝" />
          <el-option :value="3" label="已取消" />
          <el-option :value="4" label="已过期" />
        </el-select>
        <el-button type="primary" @click="handleSearch">查询</el-button>
      </div>
      <el-table
        :header-cell-style="{ backgroundColor: '#f5f7fa', color: '#333' }"
        :data="tableData"
        style="width: 100%"
        v-loading="loading"
      >
        <el-table-column prop="lab_name" label="实验室" min-width="160" />
        <el-table-column label="预约类型" min-width="80">
          <template #default="{ row }">
            <el-tag :type="row.type === '实验室' ? 'success' : 'primary'">{{ row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="设备" min-width="160">
          <template #default="{ row }">
            {{ row.equipment_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="date" label="日期" min-width="120" />
        <el-table-column label="预约时段" min-width="160">
          <template #default="{ row }"> {{ row.start_time }} - {{ row.end_time }} </template>
        </el-table-column>
        <el-table-column label="原因" min-width="200">
          <template #default="{ row }">{{ reasonText(row) }}</template>
        </el-table-column>
        <el-table-column label="预约状态" min-width="80">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="200">
          <template #default="{ row }">
            <el-button type="primary" text bg @click="openHistory(row)">历史</el-button>
            <el-button
              v-if="row.status === 0 || row.status === 1"
              type="danger"
              text
              bg
              :disabled="!canOwnerCancel(row)"
              :title="cancelHint(row)"
              @click="handleCancel(row)"
              >取消
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
    <!-- 预约历史抽屉 -->
    <el-drawer v-model="historyVisible" title="预约历史" size="420px">
      <div v-loading="historyLoading">
        <el-timeline v-if="historyList.length">
          <el-timeline-item
            v-for="item in historyList"
            :key="item.id"
            :timestamp="formatDateTime(item.create_time)"
            :type="actionTagType(item.action)"
          >
            <div style="font-weight: 600">{{ actionText(item.action) }}</div>
            <div v-if="item.reason" style="margin-top: 4px; color: #606266">
              原因：{{ item.reason }}
            </div>
            <div v-if="item.actor_name" style="margin-top: 4px; color: #909399">
              操作人：{{ item.actor_name }}
            </div>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无历史记录" />
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import {
  cancelReservationApi,
  getReservationHistoryApi,
  getReservationPageList
} from '@/api/reservation'
import { ElMessageBox, ElMessage } from 'element-plus'
import {
  actionTagType,
  actionText,
  canOwnerCancel,
  cancelHint,
  formatDateTime,
  statusTagType,
  statusText
} from '@/utils/reservationStatus'

const loading = ref(false)
const tableData = ref([])
const total = ref(0)
const historyVisible = ref(false)
const historyLoading = ref(false)
const historyList = ref([])
const params = reactive({
  page: 1,
  page_size: 10,
  status: null,
  mine: true
})

const reasonText = (row) => {
  if (row.reject_reason) return `拒绝：${row.reject_reason}`
  if (row.cancel_reason) return `取消：${row.cancel_reason}`
  return '-'
}

const load = async () => {
  loading.value = true
  try {
    const res = await getReservationPageList(params)
    if (res.code === 200) {
      tableData.value = res.data?.list
      total.value = res.data?.total ?? 0
    }
  } catch {
  } finally {
    loading.value = false
  }
}
/**
 * 取消预约
 * @param row 预约记录行数据
 */
const handleCancel = (row) => {
  if (!canOwnerCancel(row)) return
  ElMessageBox.confirm(`确认取消[${row.lab_name}]的预约?`, '确认取消', {
    type: 'warning'
  })
    .then(async () => {
      try {
        const res = await cancelReservationApi(row.id)
        if (res.code === 200) {
          ElMessage.success('取消预约成功')
          load()
        }
      } catch {}
    })
    .catch(() => {})
}
/**
 * 打开预约历史记录抽屉
 * @param row 预约记录行数据
 */
const openHistory = async (row) => {
  historyVisible.value = true
  historyLoading.value = true
  historyList.value = []
  try {
    const res = await getReservationHistoryApi(row.id)
    if (res.code === 200) {
      historyList.value = res.data || []
    }
  } catch {
  } finally {
    historyLoading.value = false
  }
}

const handleSearch = () => {
  params.page = 1
  load()
}

onMounted(() => {
  load()
})
</script>

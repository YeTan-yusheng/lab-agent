<template>
  <div>
    <el-card>
      <template #header>
        <div style="font-size: 16px; font-weight: bold">
          <span>审核预约</span>
          <el-tag v-if="pendingCount" type="warning" style="margin-left: 8px">
            待审核数量：{{ pendingCount }}
          </el-tag>
        </div>
      </template>
      <div style="margin-bottom: 10px; display: flex; gap: 8px; flex-wrap: wrap">
        <el-select
          placeholder="状态"
          v-model="params.status"
          style="width: 140px"
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
        <el-select
          v-model="params.lab_id"
          placeholder="实验室"
          clearable
          style="width: 180px"
          @change="handleSearch"
          @clear="handleSearch"
        >
          <el-option v-for="lab in labs" :key="lab.id" :value="lab.id" :label="lab.name" />
        </el-select>
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          value-format="YYYY-MM-DD"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          style="flex: 0 0 600px"
          @change="handleSearch"
        />
        <el-button type="primary" @click="handleSearch">查询</el-button>
      </div>
      <el-table
        :header-cell-style="{ backgroundColor: '#f5f7fa', color: '#333' }"
        :data="tableData"
        style="width: 100%"
        v-loading="loading"
      >
        <el-table-column prop="lab_name" label="实验室" min-width="160" />
        <el-table-column prop="user_name" label="预约人" min-width="100" />
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
        <el-table-column label="操作" min-width="320">
          <template #default="{ row }">
            <template v-if="row.status === 0">
              <el-button type="success" text bg @click="handleAudit(row, 1)">通过</el-button>
              <el-button type="danger" text bg @click="handleAudit(row, 2)">拒绝</el-button>
            </template>
            <el-button
              v-if="canForceCancel(row)"
              type="warning"
              text
              bg
              @click="handleForceCancel(row)"
              >强制取消
            </el-button>
            <el-button type="primary" text bg @click="openHistory(row)">历史</el-button>
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

    <el-dialog
      v-model="auditDialogVisible"
      :title="auditStatus === 1 ? '通过预约' : '拒绝预约'"
      width="460px"
    >
      <div style="line-height: 1.8">
        <div>预约人：{{ auditRow?.user_name || '-' }}</div>
        <div>实验室：{{ auditRow?.lab_name || '-' }}</div>
        <div>时间：{{ auditRow?.date }} {{ auditRow?.start_time }} - {{ auditRow?.end_time }}</div>
      </div>
      <el-form v-if="auditStatus === 2" style="margin-top: 12px">
        <el-form-item label="拒绝原因" required>
          <el-input
            v-model="rejectReason"
            type="textarea"
            :rows="3"
            maxlength="255"
            show-word-limit
            placeholder="请填写拒绝原因"
          />
        </el-form-item>
      </el-form>
      <el-form v-if="isOwn(auditRow)" style="margin-top: 12px">
        <el-form-item label="自审">
          <el-switch v-model="selfAudit" />
          <span style="margin-left: 8px; color: #909399; font-size: 12px">
            本人预约必须显式开启自审
          </span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="auditDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="auditLoading" @click="submitAudit"> 确认 </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="forceDialogVisible" title="强制取消预约" width="460px">
      <div style="line-height: 1.8">
        <div>预约人：{{ forceRow?.user_name || '-' }}</div>
        <div>实验室：{{ forceRow?.lab_name || '-' }}</div>
        <div>时间：{{ forceRow?.date }} {{ forceRow?.start_time }} - {{ forceRow?.end_time }}</div>
      </div>
      <el-form style="margin-top: 12px">
        <el-form-item label="取消原因" required>
          <el-input
            v-model="forceReason"
            type="textarea"
            :rows="3"
            maxlength="255"
            show-word-limit
            placeholder="请填写强制取消原因"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="forceDialogVisible = false">取消</el-button>
        <el-button type="danger" :loading="forceLoading" @click="submitForceCancel">
          确认强制取消
        </el-button>
      </template>
    </el-dialog>

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
  auditReservationApi,
  cancelReservationApi,
  getReservationHistoryApi,
  getReservationPageList
} from '@/api/reservation'
import { getLabPageList } from '@/api/lab'
import { ElMessage } from 'element-plus'
import { useUser } from '@/utils/user'
import {
  actionTagType,
  actionText,
  canForceCancel,
  formatDateTime,
  statusTagType,
  statusText
} from '@/utils/reservationStatus'
import { useAuditPendingCount } from '@/composables/useAuditPendingCount'

const { userInfo } = useUser()
const { pendingCount, refresh: refreshPendingCount } = useAuditPendingCount()
const loading = ref(false)
const tableData = ref([])
const total = ref(0)
const labs = ref([])
const dateRange = ref([])
const params = reactive({
  page: 1,
  page_size: 10,
  status: null,
  lab_id: null,
  date_from: null,
  date_to: null
})

const auditDialogVisible = ref(false)
const auditRow = ref(null)
const auditStatus = ref(1)
const rejectReason = ref('')
const selfAudit = ref(false)
const auditLoading = ref(false)

const forceDialogVisible = ref(false)
const forceRow = ref(null)
const forceReason = ref('')
const forceLoading = ref(false)

const historyVisible = ref(false)
const historyLoading = ref(false)
const historyList = ref([])

const isOwn = (row) => Boolean(row && row.user_id === userInfo.value?.id)

const reasonText = (row) => {
  if (row.reject_reason) return `拒绝：${row.reject_reason}`
  if (row.cancel_reason) return `取消：${row.cancel_reason}`
  return '-'
}

const loadLabs = async () => {
  try {
    const res = await getLabPageList({ page: 1, page_size: 100 })
    if (res.code === 200) {
      labs.value = res.data?.list || []
    }
  } catch {}
}

const load = async () => {
  loading.value = true
  params.date_from = dateRange.value?.[0] || null
  params.date_to = dateRange.value?.[1] || null
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

const handleSearch = () => {
  params.page = 1
  load()
}

const handleAudit = (row, status) => {
  auditRow.value = row
  auditStatus.value = status
  rejectReason.value = ''
  selfAudit.value = false
  auditDialogVisible.value = true
}

const submitAudit = async () => {
  const reason = rejectReason.value.trim()
  if (auditStatus.value === 2 && !reason) {
    ElMessage.warning('请填写拒绝原因')
    return
  }
  if (isOwn(auditRow.value) && !selfAudit.value) {
    ElMessage.warning('本人预约必须显式开启自审')
    return
  }

  auditLoading.value = true
  try {
    const payload = {
      status: auditStatus.value,
      self_audit: isOwn(auditRow.value) ? selfAudit.value : false
    }
    if (auditStatus.value === 2) payload.reject_reason = reason
    const res = await auditReservationApi(auditRow.value.id, payload)
    if (res.code === 200) {
      ElMessage.success(auditStatus.value === 1 ? '审核通过' : '审核拒绝')
      auditDialogVisible.value = false
      await load()
      refreshPendingCount()
    }
  } catch {
  } finally {
    auditLoading.value = false
  }
}

const handleForceCancel = (row) => {
  forceRow.value = row
  forceReason.value = ''
  forceDialogVisible.value = true
}

const submitForceCancel = async () => {
  const reason = forceReason.value.trim()
  if (!reason) {
    ElMessage.warning('请填写强制取消原因')
    return
  }

  forceLoading.value = true
  try {
    const res = await cancelReservationApi(forceRow.value.id, {
      force: true,
      reason
    })
    if (res.code === 200) {
      ElMessage.success('强制取消成功')
      forceDialogVisible.value = false
      await load()
      refreshPendingCount()
    }
  } catch {
  } finally {
    forceLoading.value = false
  }
}

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

onMounted(() => {
  loadLabs()
  load()
  refreshPendingCount()
})
</script>

<template>
  <div>
    <el-card>
      <template #header>
        <div style="font-size: 16px; font-weight: bold">预约审计</div>
      </template>
      <!-- 查询区 -->
      <div style="margin-bottom: 10px; display: flex; gap: 8px; flex-wrap: wrap">
        <el-input
          v-model="params.reservation_id"
          placeholder="预约号"
          style="width: 120px"
          clearable
        />
        <el-input v-model="params.user_id" placeholder="预约人ID" style="width: 120px" clearable />
        <el-select
          v-model="params.action"
          placeholder="行为"
          clearable
          style="width: 150px"
          @change="handleSearch"
          @clear="handleSearch"
        >
          <el-option value="submit" label="提交" />
          <el-option value="approve" label="通过" />
          <el-option value="reject" label="拒绝" />
          <el-option value="cancel" label="取消" />
          <el-option value="force_cancel" label="强制取消" />
          <el-option value="expire" label="过期" />
        </el-select>
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          value-format="YYYY-MM-DD"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          style="flex: 0 0 320px"
          single-panel
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
        <el-table-column label="时间" min-width="160">
          <template #default="{ row }">{{ formatDateTime(row.create_time) }}</template>
        </el-table-column>
        <el-table-column prop="reservation_id" label="预约号" min-width="80" />
        <el-table-column prop="owner_name" label="预约人" min-width="110" />
        <el-table-column prop="lab_name" label="实验室" min-width="150" />
        <el-table-column label="预约时段" min-width="180">
          <template #default="{ row }">
            {{ row.date }} {{ row.start_time }}-{{ row.end_time }}
          </template>
        </el-table-column>
        <el-table-column label="行为" min-width="90">
          <template #default="{ row }">
            <el-tag :type="actionTagType(row.action)">{{ actionText(row.action) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态变化" min-width="140">
          <template #default="{ row }">
            {{ statusText(row.from_status) }} → {{ statusText(row.to_status) }}
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="原因" min-width="140">
          <template #default="{ row }">{{ row.reason || '-' }}</template>
        </el-table-column>
        <el-table-column prop="actor_name" label="操作人" min-width="110">
          <template #default="{ row }">{{ row.actor_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="请求ID" min-width="150">
          <template #default="{ row }">
            <el-tooltip :content="row.request_id">
              <span>{{ row.request_id }}</span>
            </el-tooltip>
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
import { onMounted, reactive, ref } from 'vue'
import { getAuditHistoryApi } from '@/api/reservation'
import { actionTagType, actionText, formatDateTime, statusText } from '@/utils/reservationStatus'

const loading = ref(false)
const tableData = ref([])
const total = ref(0)
const dateRange = ref([])
const params = reactive({
  page: 1,
  page_size: 10,
  reservation_id: null,
  user_id: null,
  action: null
})

const toId = (value) => {
  const text = String(value ?? '').trim()
  if (!text) return null
  const parsed = Number(text)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

const load = async () => {
  loading.value = true
  try {
    const res = await getAuditHistoryApi({
      page: params.page,
      page_size: params.page_size,
      reservation_id: toId(params.reservation_id),
      user_id: toId(params.user_id),
      action: params.action || null,
      date_from: dateRange.value?.[0] || null,
      date_to: dateRange.value?.[1] || null
    })
    if (res.code === 200) {
      tableData.value = res.data?.list || []
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

onMounted(() => {
  load()
})
</script>

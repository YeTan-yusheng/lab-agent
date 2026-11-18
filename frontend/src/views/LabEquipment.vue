<template>
  <div>
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <div style="font-size: 16px; font-weight: bold">
            <span style="font-size: 18px">{{ lab?.name || '实验室' }}</span>
            <span> 设备列表</span>
          </div>
          <div>
            <div style="display: inline-block; margin-right: 8px">
              <el-tag v-if="lab?.closed_days?.some((day) => day.date === todayString())"
                >今日闭馆
              </el-tag>
              <el-tag v-else :type="isLabOpen ? 'success' : 'danger'">
                {{ lab?.name || '实验室' }} {{ isLabOpen ? '开放中' : '已关闭' }}
              </el-tag>
            </div>
            <el-button
              v-if="can(Capability.BOOK_LAB)"
              :disabled="
                !lab?.status || lab?.closed_days?.some((day) => day.date === todayString())
              "
              type="primary"
              @click="handleReserveLab"
              >预约实验室
            </el-button>
            <el-button @click="router.push('/manager/lablist')">返回实验室列表</el-button>
          </div>
        </div>
      </template>
      <div
        v-if="lab"
        style="
          color: #666;
          margin-bottom: 16px;
          background-color: #f4f5ff;
          padding: 10px;
          border-radius: 6px;
        "
      >
        <div style="display: flex; align-items: center; margin-bottom: 10px">
          <div style="margin-right: 10px">
            简介：{{ lab.description ? `${lab.description}` : '暂无简介' }}
          </div>
        </div>
        <div>
          位置：{{ lab.location ? `${lab.location}` : '暂无数据' }}
          <span style="margin: 0 10px">|</span> 容纳 {{ lab.capacity }} 人
          <span style="margin: 0 10px">|</span>
          开放：{{ lab.open_time && lab.close_time ? `${lab.open_time} - ${lab.close_time}` : '-' }}
        </div>
        <div style="display: flex; align-items: center; margin-top: 6px">
          <span style="white-space: nowrap"> 近期闭馆时间： </span>
          <template v-if="upcomingClosedDays.length">
            <span
              v-for="closedDay in upcomingClosedDays"
              :key="closedDay.date"
              style="display: inline-flex; margin-right: 3px"
            >
              <span>{{ closedDay.date }}</span>

              <el-tooltip :content="closedDay.reason || '暂无原因'" placement="top">
                <span
                  style="
                    max-width: 100px;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    color: cornflowerblue;
                    cursor: pointer;
                  "
                >
                  （{{ closedDay.reason || '暂无原因' }}）
                </span>
              </el-tooltip>
            </span>
          </template>
          <span v-else style="margin-right: 8px">暂无</span>
          <el-button
            :disabled="lab.closed_days?.length === 0"
            type="primary"
            size="small"
            style="margin-top: 2px"
            @click="openClosedDayDialog"
            >更多</el-button
          >
        </div>
      </div>
      <!-- 查询区 -->
      <div style="margin-bottom: 10px">
        <el-input
          placeholder="请输入名称查询"
          v-model="params.keywords"
          style="width: 240px; margin-right: 8px"
          clearable
          @keyup.enter="handleSearch"
        ></el-input>
        <el-select
          placeholder="请选择状态"
          v-model="params.status"
          style="width: 120px; margin-right: 8px"
          clearable
          @change="handleSearch"
        >
          <el-option :value="0" label="维修" />
          <el-option :value="1" label="正常" />
        </el-select>
        <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
      </div>
      <!-- 实验室设备列表 -->
      <el-table
        :header-cell-style="{ backgroundColor: '#f5f7fa', color: '#333' }"
        :data="tableData"
        style="width: 100%"
        v-loading="loading"
      >
        <el-table-column prop="img" label="图片" width="100">
          <template #default="{ row }">
            <div style="min-height: 50px; display: flex; align-items: center">
              <el-image
                v-if="row.img"
                style="display: block; width: 50px; height: 50px; border-radius: 6px"
                :src="row.img"
                :preview-src-list="[row.img]"
                :preview-teleported="true"
                alt=""
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="设备名称" />
        <el-table-column prop="spec" label="型号规格" />
        <el-table-column prop="quantity" label="数量" width="80" />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'">
              {{ row.status === 1 ? '正常' : '维修' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" v-if="can(Capability.BOOK_EQUIPMENT)">
          <template #default="{ row }">
            <el-button
              v-if="can(Capability.BOOK_EQUIPMENT)"
              :disabled="
                !row?.status ||
                !lab?.status ||
                lab?.closed_days?.some((day) => day.date === todayString())
              "
              type="primary"
              text
              bg
              @click="handleReserveEquipment(row)"
              >预约</el-button
            >
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无数据" />
        </template>
      </el-table>
      <!-- 分页 -->
      <div style="margin-top: 10px; display: flex; justify-content: flex-end">
        <el-pagination
          v-model:current-page="params.page"
          v-model:page-size="params.page_size"
          :total="total"
          background
          layout="total, prev, pager, next"
          @current-change="loadEquipment"
        />
      </div>
    </el-card>
    <!-- 闭馆日列表 -->
    <el-dialog
      v-model="closedDayDialogVisible"
      :title="lab ? `闭馆日 - ${lab.name}` : '闭馆日'"
      width="640px"
    >
      <el-table
        :data="pagedClosedDayList"
        size="small"
        :header-cell-style="{ backgroundColor: '#f5f7fa', color: '#333' }"
      >
        <el-table-column prop="date" label="日期" width="130" />
        <el-table-column label="原因" min-width="200">
          <template #default="{ row }">{{ row.reason || '暂无原因' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag v-if="isPastDate(row.date)" type="info">已过期</el-tag>
            <el-tag v-else type="success">生效中</el-tag>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无数据" />
        </template>
      </el-table>
      <div style="margin-top: 10px; display: flex; justify-content: flex-end">
        <el-pagination
          v-model:current-page="closedDayPage"
          v-model:page-size="closedDayPageSize"
          :total="closedDayList.length"
          background
          layout="total, prev, pager, next"
        />
      </div>
      <template #footer>
        <el-button @click="closedDayDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
    <!-- 预约弹窗 -->
    <reserve-dialog
      v-model:visible="reserveVisible"
      :lab-id="lab?.id"
      :lab-name="lab?.name"
      :equipment-id="currentEquipment?.id"
      :equipment-name="currentEquipment?.name"
    ></reserve-dialog>
  </div>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { ref, reactive, computed, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { getEquipmentPageList } from '@/api/equipment'
import { getLab } from '@/api/lab'
import { useRoute, useRouter } from 'vue-router'
import ReserveDialog from '@/components/ReserveDialog.vue'
import Capability from '@/utils/permissions'
import { useUser } from '@/utils/user'
import { todayString, isPastDate } from '@/utils/todayTime'

const { can } = useUser()
const reserveVisible = ref(false)
const closedDayDialogVisible = ref(false)
const closedDayList = ref([])
const closedDayPage = ref(1)
const closedDayPageSize = ref(10)
const currentEquipment = ref(null)
const route = useRoute()
const router = useRouter()
const lab = ref(null)
const params = reactive({
  page: 1,
  page_size: 10,
  keywords: '',
  status: null,
  lab_id: Number(route.query.lab_id) // "8" -> 8
})
const loading = ref(false)
const tableData = ref([])
const total = ref(0)

// 闭馆日过滤今日之后的展示
const upcomingClosedDays = computed(() => {
  return (lab.value?.closed_days || [])
    .filter((closedDay) => closedDay.date >= todayString())
    .slice(0, 3)
})

const isLabOpen = computed(() => {
  return (
    lab.value?.status === 1 && !lab.value?.closed_days?.some((day) => day.date === todayString())
  )
})
const handleReserveLab = () => {
  currentEquipment.value = null
  reserveVisible.value = true
}

const handleReserveEquipment = (row) => {
  currentEquipment.value = row
  reserveVisible.value = true
}

const loadLab = async () => {
  if (!params.lab_id) {
    ElMessage.error('缺少实验室查询条件 [lab_id]')
    return
  }
  try {
    const res = await getLab(params.lab_id)
    if (res.code === 200) {
      lab.value = res.data
      closedDayList.value = res.data?.closed_days || []
    }
  } catch (err) {
    if (err.code === 404) {
      router.push('/manager/lablist')
    }
  }
}

const pagedClosedDayList = computed(() => {
  const start = (closedDayPage.value - 1) * closedDayPageSize.value
  return closedDayList.value.slice(start, start + closedDayPageSize.value)
})

const openClosedDayDialog = () => {
  closedDayPage.value = 1
  closedDayDialogVisible.value = true
}

// 加载设备分页数据
const loadEquipment = async () => {
  loading.value = true
  try {
    const res = await getEquipmentPageList(params)
    if (res.code === 200) {
      tableData.value = res.data?.list
      total.value = res.data?.total
    }
  } catch {
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  params.page = 1
  loadEquipment()
}

watch(
  () => route.query.lab_id,
  async (value) => {
    const labId = Number(value)
    if (!Number.isInteger(labId) || labId <= 0) {
      ElMessage.error('实验室错误，请重试')
      router.push('/manager/lablist')
      return
    }
    // 更新查询参数并重置分页
    params.lab_id = labId
    params.page = 1
    // 切换实验室后重置弹窗分页状态
    closedDayPage.value = 1
    closedDayDialogVisible.value = false
    // 重新加载实验室信息和设备列表
    await Promise.all([loadLab(), loadEquipment()])
  },
  { immediate: true }
)
</script>

<template>
  <div>
    <el-card>
      <template #header>
        <div style="font-size: 16px; font-weight: bold">
          <span>实验室列表</span>
        </div>
      </template>
      <!-- 查询 -->
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
          <el-option :value="0" label="关闭" />
          <el-option :value="1" label="开放" />
        </el-select>
        <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
      </div>
      <!-- 列表区 -->
      <div>
        <el-row v-if="tableData.length" :gutter="16" v-loading="loading">
          <el-col v-for="item in tableData" :key="item.id" :span="6" style="margin-bottom: 16px">
            <el-card shadow="hover" style="height: 400px">
              <div style="height: 312px">
                <img
                  v-if="item.img"
                  :src="item.img"
                  alt=""
                  style="
                    display: block;
                    width: 100%;
                    height: 150px;
                    object-fit: contain;
                    border-radius: 6px;
                  "
                />
                <div
                  v-else
                  style="
                    display: flex;
                    height: 150px;
                    background-color: #f5f7fa;
                    border-radius: 6px;
                    align-items: center;
                    justify-content: center;
                  "
                >
                  暂无图片
                </div>
                <div style="display: flex; align-items: center; justify-content: space-between">
                  <div style="font-size: 16px; font-weight: bold; margin-top: 10px">
                    {{ item.name }}
                  </div>
                  <el-tag v-if="isClosedToday(item.upcoming_closed_days || [])">今日闭馆 </el-tag>
                  <el-tag v-else :type="item.status === 1 ? 'success' : 'danger'">
                    {{ item.status === 1 ? '开放中' : '已关闭' }}
                  </el-tag>
                </div>
                <div style="font-size: 13px; margin-top: 8px; color: #666">
                  位置：{{ item.location || '-' }}
                </div>
                <div style="font-size: 13px; margin-top: 6px; color: #666">
                  容量：{{ item.capacity }} 人
                </div>
                <div style="font-size: 13px; margin-top: 6px; color: #666">
                  开放：{{
                    item.open_time && item.close_time
                      ? `${item.open_time} - ${item.close_time}`
                      : '-'
                  }}
                </div>
                <div style="display: flex; align-items: flex-start; margin-top: 6px">
                  <span style="font-size: 13px; white-space: nowrap"> 近期闭馆时间： </span>
                  <div style="font-size: 13px; margin-left: 3px">
                    <template v-if="item.upcoming_closed_days?.length">
                      <span
                        v-for="closedDay in item.upcoming_closed_days"
                        :key="closedDay.date"
                        style="display: inline-flex; align-items: center; margin-right: 3px"
                      >
                        <span>{{ closedDay.date }}</span>

                        <el-tooltip :content="closedDay.reason || '暂无原因'" placement="top">
                          <span
                            style="
                              display: inline-block;
                              max-width: 110px;
                              overflow: hidden;
                              text-overflow: ellipsis;
                              white-space: nowrap;
                              vertical-align: bottom;
                              color: cornflowerblue;
                              cursor: pointer;
                            "
                          >
                            （{{ closedDay.reason || '暂无原因' }}）
                          </span>
                        </el-tooltip>
                      </span>
                    </template>
                    <span v-else>暂无</span>
                  </div>
                </div>
              </div>
              <div style="margin-top: 12px; display: flex; gap: 8px">
                <el-button style="flex: 1" @click="handleViewEquipment(item)">查看设备</el-button>
                <el-button
                  :disabled="!item.status || isClosedToday(item.upcoming_closed_days || [])"
                  style="flex: 1"
                  v-if="can(Capability.BOOK_LAB)"
                  type="primary"
                  @click="handleReserve(item)"
                  >预约
                </el-button>
              </div>
            </el-card>
          </el-col>
        </el-row>
        <el-empty v-else-if="!loading" description="暂无数据" />
        <!-- 分页 -->
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
      </div>
    </el-card>
    <!-- 弹窗  -->
    <reserve-dialog
      v-model:visible="reserveVisible"
      :lab-id="currentLab?.id"
      :lab-name="currentLab?.name"
    ></reserve-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getLabPageList } from '@/api/lab'
import { Search } from '@element-plus/icons-vue'
import router from '@/router'
import ReserveDialog from '@/components/ReserveDialog.vue'
import Capability from '@/utils/permissions'
import { useUser } from '@/utils/user'
import { isClosedToday } from '@/utils/todayTime'

const { can } = useUser()
const reserveVisible = ref(false)
const currentLab = ref(null)
const params = reactive({
  page: 1,
  page_size: 8,
  keywords: '',
  status: null
})
const loading = ref(false)
const tableData = ref([])
const total = ref(0)

const handleViewEquipment = (lab) => {
  router.push({ path: '/manager/lab-equipment', query: { lab_id: lab.id } })
}

const handleReserve = (lab) => {
  currentLab.value = lab
  reserveVisible.value = true
}

// 加载分页数据
const load = async () => {
  loading.value = true
  try {
    const res = await getLabPageList(params)
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
  load()
}

onMounted(() => {
  load()
})
</script>

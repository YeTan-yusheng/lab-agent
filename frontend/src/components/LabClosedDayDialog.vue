<template>
  <div>
    <el-dialog
      :model-value="visible"
      :title="labName ? `闭馆日 - ${labName}` : '闭馆日'"
      width="640px"
      @close="emit('update:visible', false)"
    >
      <div style="display: flex; gap: 8px; margin-bottom: 12px">
        <el-date-picker
          v-model="closedDayForm.date"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          placeholder="选择闭馆日期"
          style="width: 180px"
          :disabled-date="isDateDisabled"
          :disabled="closedDayEditing"
        />
        <el-input
          v-model="closedDayForm.reason"
          placeholder="闭馆原因（可选）"
          maxlength="255"
          show-word-limit
          style="flex: 1"
        />
        <el-button
          type="primary"
          :loading="closedDaySaving"
          :disabled="closedDaySaving"
          @click="handleClosedDaySave"
          >{{ closedDayEditing ? '保存修改' : '新增' }}</el-button
        >
        <el-button v-if="closedDayEditing" @click="resetClosedDayForm">取消编辑</el-button>
      </div>
      <el-table
        :data="closedDays"
        size="small"
        v-loading="closedDayLoading"
        :header-cell-style="{ backgroundColor: '#f5f7fa', color: '#333' }"
      >
        <el-table-column prop="date" label="日期" width="130" />
        <el-table-column label="原因" min-width="200">
          <template #default="{ row }">{{ row.reason || '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag v-if="isPastDate(row.date)" type="info">已过期</el-tag>
            <el-tag v-else type="success">生效中</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button
              text
              bg
              type="primary"
              :disabled="isPastDate(row.date) || closedDaySaving"
              @click="handleClosedDaySelect(row)"
              >编辑</el-button
            >
            <el-button
              text
              bg
              type="danger"
              :disabled="isPastDate(row.date) || closedDaySaving"
              @click="handleClosedDayDelete(row)"
              >删除</el-button
            >
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无数据" />
        </template>
      </el-table>
      <template #footer>
        <el-button @click="emit('update:visible', false)">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { isDateDisabled, isPastDate } from '@/utils/todayTime'
import { deleteLabClosedDay, updateLabClosedDayApi, getLabClosedDays } from '@/api/lab'

const props = defineProps({
  visible: Boolean,
  labId: Number,
  labName: String
})
const emit = defineEmits(['update:visible', 'not-found'])

const closedDays = ref([])
const closedDaySaving = ref(false)
const closedDayEditing = ref(false)
const closedDayLoading = ref(false)
const closedDayForm = reactive({
  date: '',
  reason: ''
})
// 重置闭馆日表单
const resetClosedDayForm = () => {
  closedDayEditing.value = false
  Object.assign(closedDayForm, { date: '', reason: '' })
}
// 加载闭馆日数据
const loadClosedDays = async () => {
  if (!props.labId) return
  closedDayLoading.value = true
  try {
    const res = await getLabClosedDays(props.labId)
    closedDays.value = res.data || []
  } catch (err) {
    if (err.code === 404) {
      emit('update:visible', false)
      emit('not-found')
    }
  } finally {
    closedDayLoading.value = false
  }
}
// 监听弹窗显示和实验室ID变化，加载闭馆日数据
watch(
  [() => props.visible, () => props.labId],
  async ([visible]) => {
    if (!visible) return
    resetClosedDayForm()
    closedDays.value = []
    await loadClosedDays()
  },
  { immediate: true }
)
// 选择闭馆日进行编辑
const handleClosedDaySelect = (row) => {
  closedDayEditing.value = true
  Object.assign(closedDayForm, {
    date: row.date,
    reason: row.reason || ''
  })
}
// 保存闭馆日
const handleClosedDaySave = async () => {
  if (!props.labId || closedDaySaving.value) return

  if (!closedDayForm.date) {
    ElMessage.warning('请选择闭馆日期')
    return
  }
  if (isPastDate(closedDayForm.date)) {
    ElMessage.warning('闭馆日期必须在今天及以后')
    return
  }

  closedDaySaving.value = true
  try {
    await updateLabClosedDayApi(props.labId, {
      date: closedDayForm.date,
      reason: closedDayForm.reason.trim() || null
    })
    ElMessage.success('保存成功')
    resetClosedDayForm()
    await loadClosedDays(props.labId)
  } catch (err) {
    if (err.code === 404) {
      emit('update:visible', false)
      emit('not-found')
    }
  } finally {
    closedDaySaving.value = false
  }
}
// 删除闭馆日
const handleClosedDayDelete = (row) => {
  if (!props.labId || closedDaySaving.value || isPastDate(row.date)) return
  ElMessageBox.confirm(`确认删除 ${row.date} 的闭馆日？`, '确认删除', { type: 'warning' })
    .then(async () => {
      closedDaySaving.value = true
      try {
        await deleteLabClosedDay(props.labId, row.date)
        ElMessage.success('删除成功')
        if (closedDayEditing.value && closedDayForm.date === row.date) {
          resetClosedDayForm()
        }
        await loadClosedDays(props.labId)
      } catch (err) {
        if (err.code === 404) {
          emit('update:visible', false)
          emit('not-found')
        }
      } finally {
        closedDaySaving.value = false
      }
    })
    .catch(() => {})
}
</script>

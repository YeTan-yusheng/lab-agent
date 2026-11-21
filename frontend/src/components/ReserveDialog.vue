<template>
  <div>
    <el-dialog
      :model-value="visible"
      title="预约"
      width="560"
      @open="handleOpen"
      @close="emit('update:visible', false)"
    >
      <el-form
        ref="formRef"
        :rules="rules"
        :model="form"
        label-width="100px"
        style="width: 100%; padding-right: 30px; padding-top: 18px"
      >
        <el-form-item label="实验室">
          <el-input :model-value="labName" disabled />
        </el-form-item>
        <el-form-item label="设备">
          <el-input :model-value="equipmentName" disabled />
        </el-form-item>
        <el-form-item label="预约日期" prop="date">
          <el-date-picker
            v-model="form.date"
            type="date"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            placeholder="请选择日期"
            style="width: 100%"
            :disabled-date="isPastDate"
          />
        </el-form-item>
        <el-form-item label="预约情况">
          <div style="width: 100%">
            <div v-if="!form.date" class="timeline-tip">请选择预约日期</div>
            <div v-else-if="dayLoading" class="timeline-tip">正在加载当天可预约区间...</div>
            <div v-else-if="dayError" class="timeline-tip timeline-error">
              {{ dayError }}
              <el-button type="primary" link @click="loadDayAvailability">重试</el-button>
            </div>
            <template v-else>
              <availability-timeline
                :ranges="dayRanges"
                :open-time="dayOpenTime"
                :close-time="dayCloseTime"
                :current-time="dayCurrentTime"
                :selected-start="form.startTime"
                :selected-end="form.endTime"
              />
              <div v-if="dayMessage" class="timeline-tip">{{ dayMessage }}</div>
            </template>
          </div>
        </el-form-item>
        <el-form-item label="开始时间" prop="startTime">
          <el-select
            v-model="form.startTime"
            :disabled="!form.date || dayLoading || !startOptions.length"
            placeholder="请选择开始时间"
            style="width: 100%"
            @change="handleStartChange"
          >
            <el-option v-for="time in startOptions" :key="time" :label="time" :value="time" />
          </el-select>
        </el-form-item>
        <el-form-item label="结束时间" prop="endTime">
          <el-select
            v-model="form.endTime"
            :disabled="!form.startTime || !endOptions.length"
            placeholder="请选择结束时间"
            style="width: 100%"
            @change="handleEndChange"
          >
            <el-option v-for="time in endOptions" :key="time" :label="time" :value="time" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" placeholder="请输入备注信息" />
        </el-form-item>
        <el-form-item v-if="submitError" label="预约失败">
          <span class="timeline-error">{{ submitError }}</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="emit('update:visible', false)">取消</el-button>
        <el-button
          type="primary"
          :loading="submitting"
          :disabled="!canSubmit"
          @click="handleSubmit"
        >
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createReservationApi, getDayAvailabilityApi } from '@/api/reservation'
import AvailabilityTimeline from '@/components/AvailabilityTimeline.vue'

const props = defineProps({
  visible: Boolean,
  labId: Number,
  labName: String,
  equipmentId: Number,
  equipmentName: String
})
const emit = defineEmits(['update:visible'])

const STEP_MINUTES = 10

const submitting = ref(false)
const formRef = ref()
const dayLoading = ref(false)
const dayError = ref('')
const dayRanges = ref([])
const dayMessageText = ref('')
const dayOpenTime = ref('')
const dayCloseTime = ref('')
const dayCurrentTime = ref('')
const startOptions = ref([])
const endOptions = ref([])
const submitError = ref('')
let dayRequestId = 0

const form = reactive({
  date: '',
  startTime: '',
  endTime: '',
  remark: ''
})

const toMinutes = (value) => {
  // 将时间字符串转换为分钟数
  if (!value) return null
  const [hours, minutes] = value.split(':').map(Number)
  if (Number.isNaN(hours) || Number.isNaN(minutes)) return null
  return hours * 60 + minutes
}

const toTime = (value) => {
  // 将分钟数转换为时间字符串
  const hours = String(Math.floor(value / 60)).padStart(2, '0')
  const minutes = String(value % 60).padStart(2, '0')
  return `${hours}:${minutes}`
}

const isPastDate = (date) => {
  // 只允许选择今天及之后的日期
  const candidate = new Date(date)
  candidate.setHours(0, 0, 0, 0)

  const today = new Date()
  today.setHours(0, 0, 0, 0)

  return candidate < today
}

const resetAll = () => {
  dayRequestId += 1
  Object.assign(form, { date: '', startTime: '', endTime: '', remark: '' })
  dayLoading.value = false
  dayError.value = ''
  dayRanges.value = []
  dayMessageText.value = ''
  dayOpenTime.value = ''
  dayCloseTime.value = ''
  dayCurrentTime.value = ''
  startOptions.value = []
  endOptions.value = []
  submitError.value = ''
}

const handleOpen = () => {
  resetAll()
  formRef.value?.clearValidate?.()
}

const dayMessage = computed(() => {
  if (!form.date || dayLoading.value || dayError.value) return ''
  if (startOptions.value.length) return ''
  return dayMessageText.value || '当天无可预约时段'
})

const buildStartOptions = () => {
  // 构建开始时间选项
  const options = new Set()
  for (const range of dayRanges.value) {
    const start = toMinutes(range.start)
    const end = toMinutes(range.end)
    if (start === null || end === null) continue
    for (let value = start; value < end; value += STEP_MINUTES) {
      options.add(toTime(value))
    }
  }
  startOptions.value = [...options].sort()
}

const rangeForStart = (start) => {
  // 根据开始时间查找对应的可预约区间
  const value = toMinutes(start)
  if (value === null) return null
  return (
    dayRanges.value.find((range) => {
      const rangeStart = toMinutes(range.start)
      const rangeEnd = toMinutes(range.end)
      return rangeStart !== null && rangeEnd !== null && value >= rangeStart && value < rangeEnd
    }) || null
  )
}

const buildEndOptions = () => {
  // 构建结束时间选项，不包括右端点
  const range = rangeForStart(form.startTime)
  if (!range) {
    endOptions.value = []
    return
  }
  const start = toMinutes(form.startTime)
  const end = toMinutes(range.end)
  const options = []
  for (let value = start + STEP_MINUTES; value <= end; value += STEP_MINUTES) {
    options.push(toTime(value))
  }
  endOptions.value = options
}

const loadDayAvailability = async () => {
  // 加载当天的可预约区间
  if (!form.date || props.labId === undefined || props.labId === null) return

  const requestId = ++dayRequestId
  dayLoading.value = true
  dayError.value = ''
  dayRanges.value = []
  startOptions.value = []
  endOptions.value = []

  try {
    const res = await getDayAvailabilityApi({
      lab_id: props.labId,
      equipment_id: props.equipmentId,
      date: form.date
    })
    if (requestId !== dayRequestId) return

    const data = res.data || {}
    dayRanges.value = data.ranges || []
    dayMessageText.value = data.message || ''
    dayOpenTime.value = data.open_time || ''
    dayCloseTime.value = data.close_time || ''
    dayCurrentTime.value = data.current_time || ''
    buildStartOptions()
  } catch (err) {
    if (requestId !== dayRequestId) return
    dayError.value = err?.message || '获取预约可用性失败'
  } finally {
    if (requestId === dayRequestId) {
      dayLoading.value = false
    }
  }
}

watch(
  () => form.date,
  () => {
    form.startTime = ''
    form.endTime = ''
    submitError.value = ''
    loadDayAvailability()
  }
)

const handleStartChange = () => {
  submitError.value = ''
  buildEndOptions()
  if (!endOptions.value.includes(form.endTime)) {
    form.endTime = ''
  }
}

const handleEndChange = () => {
  submitError.value = ''
}

const canSubmit = computed(() =>
  Boolean(form.date && form.startTime && form.endTime && !dayLoading.value && !submitting.value)
)

const validateTimeRange = (_rule, _value, callback) => {
  if (!form.startTime || !form.endTime) {
    callback()
    return
  }
  if (form.startTime >= form.endTime) {
    callback(new Error('开始时间必须早于结束时间'))
    return
  }
  callback()
}

const rules = {
  date: [{ required: true, message: '请选择预约日期', trigger: 'change' }],
  startTime: [
    { required: true, message: '请选择开始时间', trigger: 'change' },
    { validator: validateTimeRange, trigger: 'change' }
  ],
  endTime: [
    { required: true, message: '请选择结束时间', trigger: 'change' },
    { validator: validateTimeRange, trigger: 'change' }
  ]
}

const handleSubmit = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  submitError.value = ''
  try {
    const res = await createReservationApi({
      lab_id: props.labId,
      equipment_id: props.equipmentId,
      date: form.date,
      start_time: form.startTime,
      end_time: form.endTime,
      remark: form.remark
    })

    if (res.code === 200) {
      ElMessage.success('预约已提交，请等待审核')
      emit('update:visible', false)
    }
  } catch (err) {
    submitError.value = err?.message || '创建预约失败，请重试'
    if (err?.code === 409) {
      form.startTime = ''
      form.endTime = ''
      await loadDayAvailability()
    }
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.timeline-tip {
  margin-top: 8px;
  color: #909399;
  font-size: 13px;
  text-align: center;
}

.timeline-error {
  color: #f56c6c;
  font-size: 13px;
}
</style>

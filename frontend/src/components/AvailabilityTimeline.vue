<template>
  <div v-if="openTime && closeTime" class="availability-timeline">
    <div class="timeline-track">
      <div
        v-for="range in ranges"
        :key="`${range.start}-${range.end}`"
        class="timeline-range"
        :style="rangeStyle(range)"
      />
      <div v-if="selectedStyle" class="timeline-selected" :style="selectedStyle" />
      <div v-if="currentLeft !== null" class="timeline-now" :style="{ left: `${currentLeft}%` }">
        <span class="timeline-now-label">{{ currentTime }}</span>
      </div>
    </div>
    <!-- 时间轴线 -->
    <div class="timeline-axis">
      <span
        v-for="tick in ticks"
        :key="tick.label"
        class="timeline-tick"
        :style="{ left: `${tick.left}%` }"
      >
        {{ tick.label }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  ranges: {
    type: Array,
    default: () => []
  },
  openTime: {
    type: String,
    default: ''
  },
  closeTime: {
    type: String,
    default: ''
  },
  currentTime: {
    type: String,
    default: ''
  },
  selectedStart: {
    type: String,
    default: ''
  },
  selectedEnd: {
    type: String,
    default: ''
  }
})

const toMinutes = (value) => {
  if (!value) return null
  const [hours, minutes] = value.split(':').map(Number)
  if (Number.isNaN(hours) || Number.isNaN(minutes)) return null
  return hours * 60 + minutes
}

const openMinutes = computed(() => toMinutes(props.openTime))
const closeMinutes = computed(() => toMinutes(props.closeTime))
const totalMinutes = computed(() => {
  if (openMinutes.value === null || closeMinutes.value === null) return 0
  return Math.max(closeMinutes.value - openMinutes.value, 0)
})

const percent = (minutes) => {
  // 将分钟数转换为相对于开放时间的百分比
  if (!totalMinutes.value || minutes === null) return null
  return ((minutes - openMinutes.value) / totalMinutes.value) * 100
}

const rangeStyle = (range) => {
  // 计算可预约区间的样式
  const start = toMinutes(range.start)
  const end = toMinutes(range.end)
  const left = percent(start)
  const right = percent(end)
  if (left === null || right === null) return {}
  return {
    left: `${Math.max(0, Math.min(100, left))}%`,
    width: `${Math.max(0, Math.min(100, right) - Math.max(0, Math.min(100, left)))}%`
  }
}

const selectedStyle = computed(() => {
  // 计算选中区间的样式
  const start = toMinutes(props.selectedStart)
  const end = toMinutes(props.selectedEnd)
  const left = percent(start)
  const right = percent(end)
  if (left === null || right === null || right <= left) return null
  return {
    left: `${Math.max(0, Math.min(100, left))}%`,
    width: `${Math.max(0, Math.min(100, right) - Math.max(0, Math.min(100, left)))}%`
  }
})

const currentLeft = computed(() => {
  // 计算当前时间的百分比
  const current = toMinutes(props.currentTime)
  const left = percent(current)
  if (left === null || left < 0 || left > 100) return null
  return left
})

const ticks = computed(() => {
  // 计算时间轴的刻度
  if (openMinutes.value === null || closeMinutes.value === null) return []
  const startHour = Math.floor(openMinutes.value / 60)
  const endHour = Math.ceil(closeMinutes.value / 60)
  const result = []
  for (let hour = startHour; hour <= endHour; hour += 1) {
    result.push({
      label: `${String(hour)}`,
      left: percent(hour * 60) ?? 0
    })
  }
  return result
})
</script>

<style scoped>
.availability-timeline {
  width: 100%;
  padding: 18px 0 8px;
}

.timeline-track {
  position: relative;
  height: 12px;
  overflow: visible;
  border-radius: 13px;
  background: #ebeef5;
}

.timeline-range {
  position: absolute;
  top: 0;
  bottom: 0;
  border-radius: 13px;
  background: #79b96b;
}

.timeline-selected {
  position: absolute;
  top: -1px;
  bottom: -1px;
  border: 2px solid #0080ff;
  border-radius: 8px;
  background: #1ca9e6e5;
  pointer-events: none;
}

.timeline-now {
  position: absolute;
  top: -5px;
  bottom: -5px;
  width: 2px;
  background: #909399;
  transform: translateX(-1px);
}

.timeline-now-label {
  position: absolute;
  top: -24px;
  left: 50%;
  color: #606266;
  font-size: 12px;
  white-space: nowrap;
  transform: translateX(-50%);
}

.timeline-axis {
  position: relative;
  height: 20px;
  margin-top: 6px;
}

.timeline-tick {
  position: absolute;
  color: #909399;
  font-size: 12px;
  transform: translateX(-50%);
}

.timeline-tick:first-child {
  transform: none;
}

.timeline-tick:last-child {
  transform: translateX(-100%);
}
</style>

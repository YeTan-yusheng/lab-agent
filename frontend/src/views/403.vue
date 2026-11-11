<template>
  <div>
    <div style="font-size: 58px; font-weight: 100; text-align: center; margin: 30px 0 20px">
      <span>403</span>
    </div>
    <div style="color: #ff4949; font-size: 24px; text-align: center">
      <span>您没有权限访问该资源</span>
    </div>
    <div style="text-align: center">
      <el-button
        style="margin-top: 20px"
        type="primary"
        size="large"
        :loading="submitting"
        @click="back"
        >返回首页</el-button
      >
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import router from '@/router'

const submitting = ref(false)

const back = () => {
  submitting.value = true
  setTimeout(() => {
    submitting.value = false
    router.push('/manager/home')
  }, 300)
}
</script>

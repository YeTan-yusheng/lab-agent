<template>
  <div class="login-container">
    <div class="login-box">
      <h1 style="font-size: 28px">智能实验室预约系统</h1>
      <div style="margin-bottom: 30px; margin-top: 6px">基于Agent的智能预约系统</div>

      <el-form :model="form" label-width="auto" style="max-width: 600px">
        <el-form-item>
          <el-input size="large" v-model="form.name" placeholder="请输入账号" :prefix-icon="User" />
        </el-form-item>
        <el-form-item>
          <el-input
            type="password"
            size="large"
            v-model="form.password"
            placeholder="请输入密码"
            :prefix-icon="Lock"
          />
        </el-form-item>
        <el-form-item>
          <el-button
            :loading="loadingValue"
            size="large"
            type="primary"
            style="width: 100%"
            @click="login"
            >登录</el-button
          >
        </el-form-item>
        <div>还没有账号？<a href="/register" style="color: #409eff">立即注册</a></div>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import router from '@/router'
import { User, Lock } from '@element-plus/icons-vue'

const loadingValue = ref(false)

const form = ref({
  name: '',
  password: ''
})

const login = () => {
  loadingValue.value = true
  setTimeout(() => {
    loadingValue.value = false
    ElMessage.success('登录成功')
    router.push('/manager/home')
  }, 2000)
}
</script>

<style scoped>
.login-container {
  height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
}

.login-box {
  width: 380px;
  border-radius: 8px;
  padding: 30px;
  box-shadow: 0 8px 12px rgba(0, 0, 0, 0.1);
  text-align: center;
  background-color: #fff;
}
</style>

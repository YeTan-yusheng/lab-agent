<template>
  <div class="login-container">
    <div class="login-box">
      <h1 style="font-size: 28px; margin-bottom: 30px">欢迎注册</h1>

      <el-form :model="form" label-width="auto" style="max-width: 600px">
        <el-form-item>
          <el-input size="large" v-model="form.name" placeholder="请输入账号" prefix-icon="User" />
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
          <el-input
            type="password"
            size="large"
            v-model="form.confirmPassword"
            placeholder="请确认密码"
            :prefix-icon="Lock"
          />
        </el-form-item>
        <el-form-item>
          <el-button size="large" type="primary" style="width: 100%" @click="register"
            >注册</el-button
          >
        </el-form-item>
        <div>还没有账号？<a href="/login" style="color: #409eff">立即登录</a></div>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import router from '@/router'
import { User, Lock } from '@element-plus/icons-vue'

const form = ref({
  name: '',
  password: '',
  confirmPassword: ''
})

const register = () => {
  setTimeout(() => {
    ElMessage.success('注册成功')
    router.push('/login')
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

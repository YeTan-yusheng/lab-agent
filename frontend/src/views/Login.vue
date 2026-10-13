<template>
  <div class="login-container">
    <div class="login-box">
      <h1 style="font-size: 28px">智能实验室预约系统</h1>
      <div style="margin-bottom: 30px; margin-top: 6px">基于Agent的智能预约系统</div>

      <el-form ref="formRef" :rules="rules" :model="form" label-width="0px" style="max-width: 100%">
        <el-form-item prop="username">
          <el-input
            size="large"
            v-model="form.username"
            placeholder="请输入账号"
            :prefix-icon="User"
          />
        </el-form-item>
        <el-form-item prop="password">
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
        <div>
          还没有账号？<router-link to="/register" style="color: #409eff">立即注册</router-link>
        </div>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import router from '@/router'
import { User, Lock } from '@element-plus/icons-vue'
import { loginApi } from '@/api/auth'
import { useUser } from '@/utils/user'

const { saveLoginData } = useUser()

const loadingValue = ref(false)

const formRef = ref()

const rules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const form = reactive({
  username: '',
  password: ''
})

const login = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loadingValue.value = true
  try {
    const res = await loginApi(form)
    saveLoginData(res.data)
    if (res.code == 200) {
      ElMessage.success('登录成功')
      await router.push('/manager/home')
    }
  } finally {
    loadingValue.value = false
  }
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

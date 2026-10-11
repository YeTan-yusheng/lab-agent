<template>
  <div class="login-container">
    <div class="login-box">
      <h1 style="font-size: 28px; margin-bottom: 30px">欢迎注册</h1>

      <el-form ref="formRef" :rules="rules" :model="form" label-width="0px" style="max-width: 100%">
        <el-form-item prop="username">
          <el-input
            size="large"
            v-model="form.username"
            placeholder="请输入账号"
            prefix-icon="User"
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
        <el-form-item prop="confirmPassword">
          <el-input
            type="password"
            size="large"
            v-model="form.confirmPassword"
            placeholder="请确认密码"
            :prefix-icon="Lock"
          />
        </el-form-item>
        <el-form-item>
          <el-button
            :loading="loadingValue"
            size="large"
            type="primary"
            style="width: 100%"
            @click="register"
            >注册</el-button
          >
        </el-form-item>
        <div>还没有账号？<RouterLink to="/login" style="color: #409eff">立即登录</RouterLink></div>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import router from '@/router'
import { User, Lock } from '@element-plus/icons-vue'
import { registerApi } from '@/api/auth'

const formRef = ref()

const form = reactive({
  username: '',
  password: '',
  confirmPassword: ''
})

const loadingValue = ref(false)

const validatePass = (rule, value, callback) => {
  if (value === '') {
    callback(new Error('请确认密码'))
  } else {
    if (value !== form.password) {
      callback(new Error('两次密码输入不一致'))
    } else {
      callback()
    }
  }
}

const rules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  confirmPassword: [{ validator: validatePass, trigger: 'blur' }]
}

const register = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loadingValue.value = true

  try {
    const res = await registerApi(form)

    if (res.code == 200) {
      ElMessage.success('注册成功')
      await router.push('/login')
    }
  } catch (err) {
    console.log(err)
    router.push('/register')
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

<template>
  <div style="width: 40%">
    <el-card>
      <template #header>
        <div style="font-size: 16px; font-weight: bold">修改密码</div>
      </template>
      <el-form
        ref="formRef"
        :rules="rules"
        :model="form"
        label-width="80px"
        style="width: 100%; padding-right: 50px"
        v-loading="loading"
      >
        <el-form-item label="原密码" prop="oldPassword">
          <el-input
            type="password"
            show-password
            v-model="form.oldPassword"
            placeholer="请输入原密码"
          />
        </el-form-item>
        <el-form-item label="新密码" prop="newPassword">
          <el-input
            type="password"
            show-password
            v-model="form.newPassword"
            placeholer="请输入新密码"
          />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            type="password"
            show-password
            v-model="form.confirmPassword"
            placeholer="请确认密码"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="submitting" @click="handleSubmit">保存修改</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { updatePassword } from '@/api/user'
import { ref, reactive } from 'vue'
import { useUser } from '@/utils/user'
import { logout } from '@/utils/auth'
import router from '@/router'

const { updateUser } = useUser()
const submitting = ref(false)
const loading = ref(false)
const formRef = ref()
const form = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const validatePass = (rule, value, callback) => {
  if (value == '') {
    callback(new Error('请确认新密码'))
  } else {
    if (value != form.newPassword) {
      callback(new Error('两次密码输入不一致'))
    } else {
      callback()
    }
  }
}

const rules = {
  oldPassword: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  newPassword: [{ required: true, message: '请输入新密码', trigger: 'blur' }],
  confirmPassword: [{ validator: validatePass, trigger: 'blur' }]
}

const handleSubmit = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  loading.value = true
  try {
    const res = await updatePassword({
      old_password: form.oldPassword,
      new_password: form.newPassword
    })
    if (res.code == 200) {
      ElMessage.success('修改成功')
      logout()
      await router.push('/login')
    }
  } finally {
    loading.value = false
  }
}
</script>

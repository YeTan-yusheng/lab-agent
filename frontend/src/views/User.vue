<template>
  <div>
    <el-card>
      <template #header>
        <div style="font-size: 16px; font-weight: bold">用户管理</div>
      </template>
      <div style="margin-bottom: 10px">
        <el-input
          placeholder="请输入用户名或名称查询"
          v-model="params.keywords"
          style="width: 240px; margin-right: 8px"
          clearable
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        ></el-input>
        <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
        <el-button
          v-if="can(Capability.MANAGE_USERS)"
          type="success"
          :icon="Plus"
          @click="handleCreate"
          >新增</el-button
        >
      </div>

      <el-table
        :header-cell-style="{ backgroundColor: '#f5f7fa', color: '#333' }"
        :data="tableData"
        style="width: 100%"
        v-loading="loading"
      >
        <el-table-column prop="username" label="账号" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="avatar" label="头像">
          <template #default="{ row }">
            <div style="min-height: 50px">
              <img
                v-if="row.avatar"
                style="display: block; width: 50px; height: 50px; border-radius: 50%"
                :src="row.avatar"
                alt=""
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" />
        <el-table-column prop="phone" label="手机号" />
        <el-table-column prop="role" label="角色" width="100">
          <template #default="{ row }">
            {{ roleText(row.role) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'">
              {{ row.status === 1 ? '正常' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button
              v-if="can(Capability.MANAGE_USERS)"
              type="primary"
              text
              bg
              @click="handleEdit(row)"
              >编辑</el-button
            >
            <el-button
              v-if="can(Capability.MANAGE_USERS)"
              type="danger"
              text
              bg
              @click="handleDelete(row)"
              >删除</el-button
            >
          </template>
        </el-table-column>
      </el-table>

      <div style="margin-top: 10px; display: flex; justify-content: flex-end">
        <el-pagination
          v-model:current-page="params.page"
          v-model:page-size="params.pageSize"
          :total="total"
          background
          layout="total, prev, pager, next"
          @current-change="load"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑' : '新增'" width="450">
      <el-form
        ref="formRef"
        :rules="rules"
        :model="form"
        label-width="80px"
        style="width: 100%; padding-right: 30px; padding-top: 16px"
        v-loading="loading"
      >
        <el-form-item label="账号" prop="username">
          <el-input :disabled="!!form.id" v-model="form.username" placeholer="请输入账号" />
        </el-form-item>
        <el-form-item v-if="!form.id" label="密码" prop="password">
          <el-input type="password" show-password v-model="form.password" placeholer="请输入密码" />
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholer="请输入名称" />
        </el-form-item>
        <el-form-item label="角色" prop="roleKey">
          <el-select v-model="form.roleKey" :disabled="isSelf">
            <el-option
              v-for="item in roleOptions"
              :key="item.key"
              :label="item.label"
              :value="item.key"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholer="请输入邮箱" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" placeholer="请输入手机号" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio :value="1">正常</el-radio>
            <el-radio :value="0">禁用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button
          v-if="can(Capability.MANAGE_USERS)"
          type="primary"
          :loading="formLoading"
          @click="handleSave"
          >确定</el-button
        >
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { Search, Plus } from '@element-plus/icons-vue'
import {
  createUserApi,
  deleteUserApi,
  getUserPageList,
  updateUserApi,
  updateUserRolesApi,
  getUserDetailApi
} from '@/api/user'
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import Capability from '@/utils/permissions'
import { useUser } from '@/utils/user'
import { computed } from 'vue'

const { userInfo, can } = useUser()
const params = reactive({
  page: 1,
  pageSize: 10,
  keywords: ''
})
const loading = ref(false)
const tableData = ref([])
const total = ref(0)
const dialogVisible = ref(false)
const formRef = ref()
// 角色选项
const roleOptions = [
  { key: 'student', label: '学生', roles: ['student'] },
  { key: 'teacher', label: '教师', roles: ['teacher'] },
  { key: 'admin', label: '管理员', roles: ['admin'] },
  { key: 'teacher_admin', label: '教师+管理员', roles: ['teacher', 'admin'] }
]
const roleText = (role) => {
  return (
    {
      student: '学生',
      teacher: '教师',
      admin: '管理员'
    }[role] || role
  )
}
//把下拉的 roleKey 转成后端需要的数组格式
const roleMap = Object.fromEntries(roleOptions.map((item) => [item.key, item.roles]))
//判断角色是否真的改了
const originalRoleKey = ref('student')
//把后端返回的 roles 还原成下拉项的 roleKey
const isSelf = computed(() => form.id === userInfo.value?.id)

function toRoleKey(roles = []) {
  const set = new Set(roles)
  if (set.has('teacher') && set.has('admin')) return 'teacher_admin'
  if (set.has('teacher')) return 'teacher'
  if (set.has('admin')) return 'admin'
  return 'student'
}
const form = reactive({
  username: '',
  password: '',
  name: '',
  roleKey: 'student',
  email: '',
  phone: '',
  avatar: '',
  status: 1
})
const formLoading = ref(false)

const roleLabel = computed(() => userInfo.value?.display_name || '用户')

const rules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [
    { message: '请输入密码', trigger: 'blur' },
    { min: 3, max: 10, message: '密码是3-10位', trigger: 'blur' }
  ],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  email: [{ type: 'email', message: '邮箱格式错误', trigger: 'blur' }],
  phone: [{ pattern: /^1[3-9]\d{9}$/, message: '手机号格式错误', trigger: 'blur' }]
}

const resetForm = () => {
  Object.assign(form, {
    id: null,
    username: '',
    password: '',
    name: '',
    roleKey: 'student',
    email: '',
    phone: '',
    avatar: '',
    status: 1
  })
}

const handleCreate = () => {
  resetForm()
  dialogVisible.value = true
}

const handleEdit = async (row) => {
  const res = await getUserDetailApi(row.id)
  const detail = res.data

  Object.assign(form, {
    id: detail.id,
    username: detail.username,
    password: '',
    name: detail.name,
    roleKey: toRoleKey(detail.roles),
    email: detail.email,
    phone: detail.phone,
    avatar: detail.avatar,
    status: detail.status
  })

  originalRoleKey.value = form.roleKey
  dialogVisible.value = true
}

// 删除用户信息
const handleDelete = (row) => {
  ElMessageBox.confirm(`确认删除用户 [${row.username}] ？`, '确认删除', { type: 'warning' }).then(
    async () => {
      const res = await deleteUserApi(row.id)
      if (res.code === 200) {
        ElMessage.success('删除用户成功')
        load()
      }
    }
  )
}

// 保存用户
const handleSave = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  formLoading.value = true
  try {
    if (!form.id) {
      const payload = {
        username: form.username,
        name: form.name,
        email: form.email,
        phone: form.phone,
        avatar: form.avatar,
        status: form.status,
        roles: roleMap[form.roleKey]
      }
      if (form.password) payload.password = form.password

      await createUserApi(payload)
    } else {
      await updateUserApi(form.id, {
        name: form.name,
        email: form.email,
        phone: form.phone,
        avatar: form.avatar,
        status: form.status
      })

      if (!isSelf.value && form.roleKey !== originalRoleKey.value) {
        await updateUserRolesApi(form.id, roleMap[form.roleKey])
      }
    }

    dialogVisible.value = false
    ElMessage.success('操作成功')
    load()
  } catch (err) {
    // 请求拦截器已提示；这里保持弹窗打开
  } finally {
    formLoading.value = false
  }
}

// 加载分页数据
const load = async () => {
  loading.value = true
  try {
    const res = await getUserPageList({
      page: params.page,
      page_size: params.pageSize,
      keywords: params.keywords
    })
    if (res.code === 200) {
      tableData.value = res.data?.list
      total.value = res.data?.total
    }
  } catch {
  } finally {
    loading.value = false
  }
}

const handleSearch = async () => {
  params.page = 1
  load()
}

onMounted(() => {
  load()
})
</script>

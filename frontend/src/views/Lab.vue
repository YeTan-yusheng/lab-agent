<template>
  <div>
    <el-card>
      <template #header>
        <div style="font-size: 16px; font-weight: bold">
          <span>实验室管理</span>
        </div>
      </template>
      <div style="margin-bottom: 10px">
        <el-input
          placeholder="请输入名称或位置查询"
          v-model="params.keywords"
          style="width: 240px; margin-right: 8px"
          clearable
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        ></el-input>
        <el-select
          placeholder="请选择状态"
          v-model="params.status"
          style="width: 120px; margin-right: 8px"
          clearable
          @change="handleSearch"
        >
          <el-option :value="0" label="关闭" />
          <el-option :value="1" label="开放" />
        </el-select>
        <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
        <el-button
          v-if="can(Capability.MANAGE_RESOURCES)"
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
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column prop="img" label="封面" width="100">
          <template #default="{ row }">
            <div style="min-height: 50px">
              <img
                v-if="row.img"
                style="display: block; width: 50px; height: 50px; border-radius: 6px"
                :src="row.img"
                alt=""
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="location" label="位置" min-width="180" />
        <el-table-column prop="capacity" label="容纳人数" width="120" />
        <el-table-column label="开放时间" min-width="180">
          <template #default="{ row }">
            {{ row.open_time && row.close_time ? `${row.open_time} - ${row.close_time}` : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'">
              {{ row.status === 1 ? '开放' : '关闭' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="can(Capability.MANAGE_RESOURCES)" label="操作" min-width="360">
          <template #default="{ row }">
            <el-button type="primary" text bg @click="handleClosedDayManage(row)">
              新增/更新闭馆日
            </el-button>
            <el-button type="primary" text bg @click="handleEdit(row)">编辑</el-button>
            <el-button type="danger" text bg @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无数据" />
        </template>
      </el-table>

      <div style="margin-top: 10px; display: flex; justify-content: flex-end">
        <el-pagination
          v-model:current-page="params.page"
          v-model:page-size="params.page_size"
          :total="total"
          background
          layout="total, prev, pager, next"
          @current-change="load"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑' : '新增'" width="520">
      <el-form
        ref="formRef"
        :rules="rules"
        :model="form"
        label-width="90px"
        style="width: 100%; padding-right: 30px; padding-top: 16px"
      >
        <el-form-item label="封面">
          <el-upload
            :http-request="(file) => handleFileUpload({ file }, form, 'img')"
            :show-file-list="false"
            accept="image/jpeg,image/png,image/gif,image/webp"
            :before-upload="beforeAvatarUpload"
          >
            <img
              v-if="form.img"
              :src="form.img"
              style="width: 80px; height: 80px; border-radius: 6px; display: block"
            />
            <el-button v-else type="primary" plain>上传封面</el-button>
          </el-upload>
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入实验室名称" maxlength="50" />
        </el-form-item>
        <el-form-item label="位置">
          <el-input v-model="form.location" placeholder="请输入位置" maxlength="100" />
        </el-form-item>
        <el-form-item label="容纳人数" prop="capacity">
          <el-input-number v-model="form.capacity" :min="1" :max="500" />
        </el-form-item>
        <div style="display: flex; align-items: flex-start">
          <el-form-item label="开放-开始时间" prop="open_time">
            <el-time-picker
              v-model="form.open_time"
              format="HH:mm"
              value-format="HH:mm"
              placeholder="开始"
              :editable="false"
              style="width: 140px; margin-right: 8px"
              @change="validateTimeFields"
            />
          </el-form-item>
          <el-form-item label="开放-结束时间" prop="close_time">
            <el-time-picker
              v-model="form.close_time"
              format="HH:mm"
              value-format="HH:mm"
              placeholder="结束"
              :editable="false"
              style="width: 140px"
              @change="validateTimeFields"
            />
          </el-form-item>
        </div>
        <el-form-item label="简介">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="2"
            placeholder="请输入简介"
            maxlength="500"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio :value="1">开放</el-radio>
            <el-radio :value="0">关闭</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button
          v-if="can(Capability.MANAGE_RESOURCES)"
          type="primary"
          :loading="formLoading"
          @click="handleSave"
          >确定</el-button
        >
      </template>
    </el-dialog>

    <!-- 闭馆日 -->
    <lab-closed-day-dialog
      v-model:visible="closedDayDialogVisible"
      :lab-id="closedDayLab?.id"
      :lab-name="closedDayLab?.name"
      @not-found="load"
    />
  </div>
</template>

<script setup>
import { Search, Plus } from '@element-plus/icons-vue'
import { createLabApi, deleteLabApi, getLabPageList, updateLabApi, getLab } from '@/api/lab'
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUser } from '@/utils/user'
import { Capability } from '@/utils/permissions'
import LabClosedDayDialog from '@/components/LabClosedDayDialog.vue'
import { useImageUpload } from '@/utils/image'

const { can } = useUser()
const { beforeAvatarUpload, handleFileUpload } = useImageUpload()
const params = reactive({
  page: 1,
  page_size: 10,
  keywords: '',
  status: 1
})
const loading = ref(false)
const tableData = ref([])
const total = ref(0)
const dialogVisible = ref(false)
const formRef = ref()
const formLoading = ref(false)
const form = reactive({
  id: null,
  name: '',
  location: '',
  capacity: 20,
  open_time: '08:00',
  close_time: '18:00',
  description: '',
  img: '',
  status: 1
})

const closedDayDialogVisible = ref(false)
const closedDayLab = ref(null)

const validateTimeRange = (_rule, _value, callback) => {
  if (!form.open_time || !form.close_time) {
    callback()
    return
  }
  if (form.open_time >= form.close_time) {
    callback(new Error('实验室开放时间必须早于关闭时间'))
    return
  }
  callback()
}
const rules = {
  name: [{ required: true, message: '请输入实验室名称', trigger: 'blur' }],
  capacity: [{ required: true, message: '请输入容纳人数', trigger: 'blur' }],
  open_time: [
    { required: true, message: '请选择开始时间', trigger: 'change' },
    { validator: validateTimeRange, trigger: 'change' }
  ],
  close_time: [
    { required: true, message: '请选择关闭时间', trigger: 'change' },
    { validator: validateTimeRange, trigger: 'change' }
  ]
}

const validateTimeFields = async () => {
  if (!formRef.value) return
  try {
    await formRef.value.validateField(['open_time', 'close_time'])
  } catch {}
}

const resetForm = () => {
  Object.assign(form, {
    id: null,
    name: '',
    location: '',
    capacity: 20,
    open_time: '08:00',
    close_time: '18:00',
    description: '',
    img: '',
    status: 1
  })
}

const handleCreate = () => {
  resetForm()
  dialogVisible.value = true
}
// 闭馆日管理
const handleClosedDayManage = (row) => {
  closedDayLab.value = row
  closedDayDialogVisible.value = true
}

const handleEdit = async (row) => {
  try {
    const res = await getLab(row.id)
    resetForm()
    Object.assign(form, {
      id: res.data.id,
      name: res.data.name,
      location: res.data.location,
      capacity: res.data.capacity,
      open_time: res.data.open_time,
      close_time: res.data.close_time,
      description: res.data.description,
      img: res.data.img,
      status: res.data.status
    })
    dialogVisible.value = true
  } catch (res) {
    if (res.code === 404) {
      load()
    }
  }
}
/**
 * 删除实验室
 * @param row 表单数据
 */
const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除实验室 [${row.name}] ？`, '确认删除', { type: 'warning' })

    const res = await deleteLabApi(row.id)
    if (res.code === 200) {
      ElMessage.success('删除成功')
      await load()
    }
  } catch (err) {
    // 用户取消确认时不提示
    if (err === 'cancel' || err === 'close') return

    // 数据已被其他人删除，刷新列表
    if (err?.code === 404) {
      await load()
      return
    }
    ElMessage.error(err?.message || '删除失败')
  }
}
/**
 * 检查是否是编辑模式，如果是将清空的字符串替换为null
 * @param data 表单数据
 */
const buildLabPayload = (data) => {
  const payload = {
    name: data.name.trim(),
    location: data.location,
    capacity: data.capacity,
    open_time: data.open_time,
    close_time: data.close_time,
    description: data.description,
    img: data.img,
    status: data.status
  }

  Object.keys(payload).forEach((key) => {
    if (payload[key] === '') payload[key] = null
  })

  return payload
}
/**
 * 提交保存
 */
const handleSave = async () => {
  if (formLoading.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  formLoading.value = true
  try {
    const payload = buildLabPayload(form)

    const res = form.id ? await updateLabApi(form.id, payload) : await createLabApi(payload)
    if (res.code === 200) {
      dialogVisible.value = false
      ElMessage.success('操作成功')
      load()
    }
  } catch {
  } finally {
    formLoading.value = false
  }
}

const load = async () => {
  loading.value = true
  try {
    const res = await getLabPageList(params)
    if (res.code === 200) {
      tableData.value = res.data?.list
      total.value = res.data?.total
    }
  } catch {
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  params.page = 1
  load()
}

onMounted(() => {
  load()
})
</script>

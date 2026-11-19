import { ElMessage } from 'element-plus'
import { uploadFileApi } from '@/api/file'

const beforeAvatarUpload = (file) => {
  const imageTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
  if (!imageTypes.includes(file.type)) {
    ElMessage.error('只能上传图片')
    return false
  }
  if (file.size / 1024 / 1024 > 2) {
    ElMessage.error('上传图片大小不能超过2M')
    return false
  }
  return true
}

const handleFileUpload = async ({ file }, form, field) => {
  try {
    const res = await uploadFileApi(file)
    if (res.code === 200) {
      form[field] = res.data?.url
    }
  } catch {}
}

export function useImageUpload() {
  return {
    beforeAvatarUpload,
    handleFileUpload
  }
}

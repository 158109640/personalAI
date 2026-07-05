<template>
  <div class="document-uploader">
    <el-drawer
      v-model="showDrawer"
      title="📄 知识库文档管理"
      direction="rtl"
      size="420px"
    >
      <div class="drawer-content">
        <!-- 上传区域 -->
        <div class="upload-area">
          <el-upload
            class="upload-demo"
            drag
            :action="uploadUrl"
            :headers="uploadHeaders"
            :data="uploadData"
            :on-success="handleUploadSuccess"
            :on-error="handleUploadError"
            :before-upload="beforeUpload"
            multiple
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">
              拖拽文件到此处，或 <em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                支持 .txt, .pdf, .docx, .md 文件
              </div>
            </template>
          </el-upload>
        </div>

        <!-- 已上传文档列表 -->
        <div class="documents-list" v-if="documents.length > 0">
          <div class="list-header">
            <span>已上传文档 ({{ documents.length }})</span>
            <el-button type="danger" size="small" text @click="clearAllDocuments">
              清空全部
            </el-button>
          </div>

          <div
            v-for="doc in documents"
            :key="doc.doc_id"
            class="document-item"
          >
            <div class="doc-info">
              <el-icon><Document /></el-icon>
              <span class="doc-name">{{ doc.filename }}</span>
              <span class="doc-status" :class="doc.status">
                {{ doc.status === 'processed' ? '✅' : '⏳' }}
              </span>
            </div>
            <el-button
              type="danger"
              size="small"
              text
              @click="removeDocument(doc.doc_id)"
            >
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </div>

        <div v-else class="empty-docs">
          <el-empty description="暂无文档" />
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped lang="scss">
@use '@/assets/styles/variables' as *;
@use '@/assets/styles/mixins' as *;

.drawer-content {
  padding: $spacing-md 0;
}

.upload-area {
  margin-bottom: $spacing-lg;
}

.documents-list {
  .list-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: $spacing-sm 0;
    border-bottom: 1px solid $border-color;
    margin-bottom: $spacing-sm;
    font-weight: bold;
    font-size: $font-size-sm;
  }
}

.document-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: $spacing-sm;
  border-radius: $radius-sm;
  background: $bg-gray;
  margin-bottom: $spacing-sm;

  .doc-info {
    display: flex;
    align-items: center;
    gap: $spacing-sm;
    flex: 1;
    overflow: hidden;

    .doc-name {
      font-size: $font-size-sm;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
  }
}

.empty-docs {
  padding: $spacing-xl 0;
}
</style>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Document, Delete } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { deleteDocument } from '@/api/chat'

const props = defineProps<{
  sessionId: string | number | null
  modelValue: boolean
}>()

const emit = defineEmits<{
  (e: 'doc-uploaded', doc: any): void
  (e: 'update:modelValue', value: boolean): void
}>()

const showDrawer = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})
const documents = ref<any[]>([])

const uploadUrl = '/api/documents/upload'
const uploadHeaders = {
  Authorization: `Bearer ${useUserStore().token}`
}
const uploadData = computed(() => ({
  session_id: props.sessionId || 'default'
}))

const beforeUpload = (file: File) => {
  const maxSize = 10 * 1024 * 1024
  if (file.size > maxSize) {
    ElMessage.error('文件大小不能超过 10MB')
    return false
  }

  const validTypes = ['.txt', '.pdf', '.docx', '.md']
  const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
  if (!validTypes.includes(ext)) {
    ElMessage.error('不支持的文件格式')
    return false
  }

  return true
}

const handleUploadSuccess = (response: any) => {
  ElMessage.success(`文档 "${response.filename}" 上传成功`)
  documents.value.push({
    doc_id: response.doc_id,
    filename: response.filename,
    chunks: response.chunks,
    status: 'processed'
  })
  emit('doc-uploaded', response)
}

const handleUploadError = (_error: any) => {
  ElMessage.error('上传失败，请重试')
}

const removeDocument = async (docId: string) => {
  try {
    await deleteDocument(docId)
    const index = documents.value.findIndex(d => d.doc_id === docId)
    if (index !== -1) {
      documents.value.splice(index, 1)
      ElMessage.success('文档已删除')
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

const clearAllDocuments = async () => {
  if (documents.value.length === 0) return
  
  try {
    await ElMessageBox.confirm('确定要清空所有文档吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    // 逐个删除所有文档
    const deletePromises = documents.value.map(doc => deleteDocument(doc.doc_id))
    await Promise.all(deletePromises)
    
    documents.value = []
    ElMessage.success('已清空所有文档')
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error('清空失败')
    }
  }
}

// 加载已上传文档
const loadDocuments = () => {
  const saved = localStorage.getItem('uploaded_documents')
  if (saved) {
    try {
      documents.value = JSON.parse(saved)
    } catch (e) {
      console.error('加载文档列表失败:', e)
    }
  }
}

// 保存到 localStorage
const saveDocuments = () => {
  localStorage.setItem('uploaded_documents', JSON.stringify(documents.value))
}

watch(documents, () => {
  saveDocuments()
}, { deep: true })

onMounted(() => {
  loadDocuments()
})
</script>
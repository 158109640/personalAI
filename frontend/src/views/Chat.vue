<template>
  <div class="chat-layout">
    <!-- 左侧：会话列表 -->
    <Conversation ref="conversationRef" :conversations="conversations" :currentConversationId="currentConversationId" @switchConversation="switchConversation" @deleteConversation="deleteConversation" @createNewConversation="createNewConversation" />

    <!-- 右侧：聊天区域 -->
    <main class="chat-area">
      <header class="chat-header">
        <div class="header-left">
          <el-icon class="header-icon pointer" v-if="isMobile" @click="handleConversationList(true)"><DArrowRight /></el-icon>
          <h1>🤖 AI 研发助理</h1>
          <span class="user-info">👤 {{ userStore.userInfo?.username }}</span>
        </div>
        <div class="header-right">
          <el-button type="danger" size="small" @click="handleLogout">退出</el-button>
        </div>
      </header>

      <div class="messages-container" ref="messagesContainer">
        <div v-if="currentConversationId === 0" class="empty-state">
          <p>💬 选择或创建一个对话开始</p>
        </div>

        <template v-else>
          <div v-for="(msg, idx) in currentMessages" :key="idx">
            <div v-if="msg.role === 'assistant' && msg.status" class="status-message">
              <span class="status-icon">⏳</span>
              <span class="status-text">{{ msg.status }}</span>
            </div>
            <ChatMessage
              v-else
              :role="msg.role"
              :content="msg.content"
              :attachments="msg.attachments"
              :created_at="msg.created_at ?? undefined"
              :index="idx"
              @regenerate="handleRegenerate"
            />
          </div>
        </template>
      </div>

      <footer class="input-container" v-if="currentConversationId !== 0">
        <div v-if="imageList.length > 0" class="image-preview-list">
          <div v-for="(file, idx) in imageList" :key="idx" class="image-preview-item">
            <img :src="file.url" alt="图片预览" />
            <el-icon class="image-remove" @click="removeImage(idx)"><Close /></el-icon>
          </div>
        </div>
        <div class="input-wrapper">
          <div class="input-box">
            <el-input
              v-model="inputMessage"
              placeholder="输入消息... (Enter 发送)"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 6 }"
              @keydown.enter.prevent="sendMessage"
              :disabled="isLoading"
              class="custom-textarea"
            />
            <div class="input-actions">
              <!-- 图片上传按钮 -->
              <el-upload
                class="action-btn"
                action=""
                :auto-upload="false"
                :on-change="handleImageSelect"
                :on-remove="handleImageRemove"
                accept="image/*"
                multiple
                :show-file-list="false"
              >
                <el-tooltip content="上传图片" placement="top">
                  <el-icon><PictureFilled /></el-icon>
                </el-tooltip>
              </el-upload>
              <!-- 文档上传按钮 -->
              <div class="action-btn" @click="openDocumentUploader">
                <el-tooltip content="上传文档" placement="top">
                  <el-icon><DocumentAdd /></el-icon>
                </el-tooltip>
              </div>
              <!-- 发送按钮 -->
              <el-button
                type="primary"
                circle
                size="small"
                @click="sendMessage"
                :disabled="!inputMessage.trim() || isLoading"
                class="send-btn"
              >
                <el-icon><ArrowUp /></el-icon>
              </el-button>
            </div>
          </div>
        </div>
      </footer>
    </main>

    <!-- 文档上传组件 -->
    <DocumentUploader
      v-model="showDocUploader"
      :sessionId="currentConversationId"
      @doc-uploaded="handleDocUploaded"
    />
  </div>
</template>

<style scoped lang="scss">
@use '@/assets/styles/variables' as *;
@use '@/assets/styles/mixins' as *;

.chat-layout {
  display: flex;
  height: 100vh;
  background: $bg-gray;
}

.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: $bg-white;
  min-width: 0;
}

.chat-header {
  padding: $spacing-md $spacing-lg;
  border-bottom: 1px solid $border-color;
  @include flex-between;
  flex-shrink: 0;

  .header-left {
    @include flex-center;
    gap: $spacing-md;
    h1 {
      font-size: $font-size-lg;
      color: $text-primary;
      margin: 0;
    }
    .user-info {
      font-size: $font-size-sm;
      color: $text-secondary;
      background: $bg-gray;
      padding: 2px 12px;
      border-radius: $radius-full;
    }
  }
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: $spacing-lg;
  background: $bg-gray;
}

.empty-state {
  @include flex-center;
  height: 100%;
  color: $text-light;
  font-size: $font-size-lg;
}

// 在 style 中添加或修改
.status-message {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  width: fit-content;
  margin-bottom: 16px;
  background: linear-gradient(135deg, #f0f7ff 0%, #e8f4fd 100%);
  border: 1px solid #b3d9ff;
  border-radius: 12px;
  color: #1a6fb5;
  font-size: 14px;
  font-weight: 500;
  box-shadow: 0 2px 8px rgba(26, 111, 181, 0.08);
  animation: statusPulse 2s ease-in-out infinite;
  
  .status-icon {
    font-size: 20px;
    animation: spin 2s linear infinite;
  }
  
  .status-text {
    flex: 1;
    letter-spacing: 0.3px;
  }
}

// 动画
@keyframes statusPulse {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.85;
    transform: scale(1.01);
  }
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

// 不同状态的样式变体
.status-message {
  &.status-thinking {
    background: linear-gradient(135deg, #f0f7ff 0%, #e8f4fd 100%);
    border-color: #b3d9ff;
    color: #1a6fb5;
  }
  
  &.status-processing {
    background: linear-gradient(135deg, #fef7e0 0%, #fdf0d0 100%);
    border-color: #ffd699;
    color: #b8860b;
  }
  
  &.status-completed {
    background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
    border-color: #81c784;
    color: #2e7d32;
    animation: none;
  }
  
  &.status-error {
    background: linear-gradient(135deg, #fde8e8 0%, #fcd0d0 100%);
    border-color: #ff6b6b;
    color: #c62828;
    animation: none;
  }
}

.input-container {
  padding: $spacing-md $spacing-lg;
  border-top: 1px solid $border-color;
  flex-shrink: 0;

  .input-wrapper {
    width: 100%;
    max-width: 1000px;
    margin: 0 auto;
  }

  .input-box {
    position: relative;
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 12px 16px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    transition: all 0.2s;
    box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05);
    
    &:hover {
      border-color: #d1d5db;
      box-shadow: 0 4px 16px 0 rgba(0, 0, 0, 0.08);
    }
    
    &:focus-within {
      border-color: #409eff;
      box-shadow: 0 4px 20px 0 rgba(64, 158, 255, 0.15);
    }

    .custom-textarea {
      :deep(.el-textarea__inner) {
        border: none;
        box-shadow: none;
        padding: 0;
        resize: none;
        font-size: 15px;
        line-height: 1.5;
        min-height: 24px;
        
        &:focus {
          border: none;
          box-shadow: none;
        }
      }
    }

    .input-actions {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;

      .action-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 32px;
        border-radius: 50%;
        color: #6b7280;
        cursor: pointer;
        transition: all 0.2s;
        
        &:hover {
          background: #f3f4f6;
          color: #374151;
        }
        
        .el-icon {
          font-size: 18px;
        }
      }

      .send-btn {
        width: 32px;
        height: 32px;
        padding: 0;
        
        .el-icon {
          font-size: 16px;
        }
      }
    }
  }
}
.image-preview-list {
  display: flex;
  flex-wrap: wrap;
  gap: $spacing-sm;
  margin-bottom: $spacing-sm;
}

.image-preview-item {
  position: relative;
  width: 60px;
  height: 60px;
  border-radius: $radius-sm;
  overflow: hidden;
  border: 1px solid $border-color;

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .image-remove {
    position: absolute;
    top: 2px;
    right: 2px;
    font-size: 14px;
    color: $bg-white;
    background: rgba(0, 0, 0, 0.6);
    border-radius: $radius-full;
    cursor: pointer;
    padding: 2px;
  }
}
</style>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { PictureFilled, DocumentAdd, ArrowUp, Close, DArrowRight, DArrowLeft } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { sendMessageStream, checkNeedTool, sendMessage as sendMessageApi, getConversations,
  getConversationMessages,
  deleteConversation as deleteConversationApi } from '@/api/chat'
import ChatMessage from '@/components/ChatMessage.vue'
import type { ChatMessage as ChatMessageType } from '@/types/chat'
import DocumentUploader from '@/components/DocumentUploader.vue'
import Conversation from '@/components/Conversation.vue'
import { throttle } from '@/utils/index'

const router = useRouter()
const userStore = useUserStore()

type ConversationType = typeof Conversation
const isMobile = ref(innerWidth <= 768)
const isConversationListOpen = ref(false)
const conversationRef = ref<ConversationType>()

const handleConversationList = (isOpen: boolean) => {
  isConversationListOpen.value = isOpen
  conversationRef.value?.toggleConversationList(isOpen)
}

// ===== 状态 =====
const conversations = ref<any[]>([])
const currentConversationId = ref<number>(0)
const currentMessages = ref<ChatMessageType[]>([])
const inputMessage = ref('')
const isLoading = ref(false)
const messagesContainer = ref<HTMLElement | null>(null)
const showDocUploader = ref(false)

// 临时会话 ID（固定使用 -1）
const TEMP_CONV_ID = -1

// ===== 方法 =====
const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const openDocumentUploader = () => {
  showDocUploader.value = true
}

// ===== 加载会话 =====
const loadConversations = async () => {
  try {
    const res = await getConversations()
    conversations.value = res.data.conversations
  } catch (e) {
    console.error('加载会话列表失败:', e)
  }
}

const offset = ref(0)
const total = ref(0)
const isLoadingHistory = ref(false)
const LOAD_MORE_THRESHOLD = 80

const loadConversationMessages = async (convId: number, limit: number = 10, toBottom: boolean = true) => {
  if (convId === TEMP_CONV_ID) {
    currentMessages.value = []
    return
  }

  if (isLoadingHistory.value) return
  if (!toBottom && offset.value >= total.value) return

  isLoadingHistory.value = true
  const container = messagesContainer.value
  const prevScrollHeight = container?.scrollHeight ?? 0

  try {
    const res = await getConversationMessages(convId, limit, offset.value)
    const newMessages = res.data.messages.data
    total.value = res.data.messages.total

    if (newMessages.length === 0) return

    offset.value += newMessages.length

    if (toBottom) {
      currentMessages.value = newMessages
      await scrollToBottom()
    } else {
      currentMessages.value.unshift(...newMessages)
      await nextTick()
      if (container) {
        // 保持当前阅读位置，避免加载后仍停在顶部而连续触发
        container.scrollTop = container.scrollHeight - prevScrollHeight
      }
    }
  } catch (e) {
    console.error('加载会话消息失败:', e)
  } finally {
    isLoadingHistory.value = false
  }
}

const switchConversation = (convId: number) => {
  if (convId === currentConversationId.value) return
  currentConversationId.value = convId
  offset.value = 0
  total.value = 0
  currentMessages.value = []
  loadConversationMessages(convId)
}

const createNewConversation = async () => {
  // 检查是否已有临时会话
  const existingTemp = conversations.value.find(c => c.id === TEMP_CONV_ID)
  if (existingTemp) {
    // 如果已有临时会话，直接切换到它
    currentConversationId.value = TEMP_CONV_ID
    currentMessages.value = []
    inputMessage.value = ''
    ElMessage.info('已切换到新对话')
    return
  }

  // 创建临时会话
  const tempConv = {
    id: TEMP_CONV_ID,
    title: '新对话',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    is_temp: true
  }
  conversations.value.unshift(tempConv)
  currentConversationId.value = TEMP_CONV_ID
  currentMessages.value = []
  inputMessage.value = ''
  ElMessage.success('已创建新对话')
}

const deleteConversation = async (convId: number) => {
  // 如果是临时会话，直接删除
  if (convId === TEMP_CONV_ID) {
    const idx = conversations.value.findIndex(c => c.id === TEMP_CONV_ID)
    if (idx !== -1) {
      conversations.value.splice(idx, 1)
    }
    if (currentConversationId.value === TEMP_CONV_ID) {
      currentConversationId.value = 0
      currentMessages.value = []
    }
    ElMessage.info('已取消新对话')
    return
  }

  try {
    await ElMessageBox.confirm('确定要删除这个对话吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await deleteConversationApi(convId)
    ElMessage.success('对话已删除')
    if (currentConversationId.value === convId) {
      currentConversationId.value = 0
      currentMessages.value = []
    }
    await loadConversations()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 图片相关
const imageList = ref<any[]>([])
// 图片处理
const handleImageSelect = (file: any) => {
  if (imageList.value.length >= 5) {
    ElMessage.warning('最多上传5张图片')
    return false
  }
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.warning('图片不能超过10MB')
    return false
  }
  imageList.value.push({
    raw: file.raw,
    url: URL.createObjectURL(file.raw)
  })
  return true
}

const handleImageRemove = (_idx: number) => {
  // 由 removeImage 处理
}

// removeImage 处理
const removeImage = (idx: number) => {
  imageList.value.splice(idx, 1)
}

// ===== 发送消息 =====
const sendMessage = async () => {
  const msg = inputMessage.value.trim()
  if (!msg || isLoading.value) return

  // ===== 如果没有会话或当前是临时会话，创建新会话 =====
  let conversationId = currentConversationId.value
  
  if (conversationId === null || conversationId === TEMP_CONV_ID) {
    // 如果当前是临时会话，先更新标题
    if (conversationId === TEMP_CONV_ID) {
      const tempConv = conversations.value.find(c => c.id === TEMP_CONV_ID)
      if (tempConv) {
        tempConv.title = msg.slice(0, 30) + (msg.length > 30 ? '...' : '')
      }
    } else {
      // 没有会话，创建临时会话
      const tempConv = {
        id: TEMP_CONV_ID,
        title: msg.slice(0, 30) + (msg.length > 30 ? '...' : ''),
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        is_temp: true
      }
      conversations.value.unshift(tempConv)
      currentConversationId.value = TEMP_CONV_ID
    }
    conversationId = TEMP_CONV_ID
  }

  // 先构建 formData（使用当前的图片）
  const formData = new FormData()
  formData.append('message', msg || '')
  imageList.value.forEach(img => formData.append('files', img.raw))
  if (currentConversationId.value) {
    formData.append('conversation_id', String(currentConversationId.value))
  }

  const attachments = imageList.value.map((img) => ({
    file_url: img.url,
    file_name: img.raw?.name || 'image',
    file_type: img.raw?.type || 'image/jpeg',
  }))

  // 添加用户消息
  currentMessages.value.push({
    role: 'user',
    content: msg,
    created_at: Date.now(),
    attachments: attachments.length > 0 ? attachments : undefined,
  })
  inputMessage.value = ''
  // 清空图片列表
  imageList.value = []
  await scrollToBottom()

  const assistantIndex = currentMessages.value.length
  currentMessages.value.push({
    role: 'assistant',
    content: '',
    created_at: Date.now(),
    status: '⏳ 发送问题中...'
  })
  isLoading.value = true

  try {
    // 调用 need-tool 接口判断
    const needToolRes = await checkNeedTool(formData)
    const needTool = needToolRes.data.need_tool

    if (needTool) {
      // ===== 需要工具：普通接口 =====
      const res = await sendMessageApi(formData)
      const newConvId = res.data.conversation_id

      // 更新会话 ID（从临时 ID 变为真实 ID）
      if (conversationId === TEMP_CONV_ID) {
        const idx = conversations.value.findIndex(c => c.id === TEMP_CONV_ID)
        if (idx !== -1) {
          conversations.value[idx].id = newConvId
          conversations.value[idx].is_temp = false
          conversations.value[idx].title = msg.slice(0, 30) + (msg.length > 30 ? '...' : '')
        }
        currentConversationId.value = newConvId
        conversationId = newConvId
      }

      const updatedMessage = {
        ...currentMessages.value[assistantIndex],
        content: res.data.response,
        status: '' // 清除状态
      }
      currentMessages.value.splice(assistantIndex, 1, updatedMessage)
      isLoading.value = false
      await loadConversations()
      await scrollToBottom()
    } else {
      // ===== 不需要工具：流式接口 =====
      // 在 sendMessage 函数中的流式处理部分
      // 在 sendMessage 中的流式处理
      sendMessageStream(
        formData,
        (chunk) => {
          console.log('📦 收到chunk:', chunk)
          
          try {
            const data = JSON.parse(chunk)
            console.log('📊 解析数据:', data)
            
            // 根据 type 处理不同类型的数据
            if (data.type === 'conversation_id') {
              console.log('🆔 更新会话 ID:', data.conversation_id)
              // 更新会话 ID（从临时 ID 变为真实 ID）
              if (conversationId === TEMP_CONV_ID) {
                const idx = conversations.value.findIndex(c => c.id === TEMP_CONV_ID)
                if (idx !== -1) {
                  conversations.value[idx].id = data.conversation_id
                  conversations.value[idx].is_temp = false
                }
                currentConversationId.value = data.conversation_id
                conversationId = data.conversation_id
              }
            } else if (data.type === 'status') {
              console.log('📌 状态更新:', data.content)
              const updatedMsg = {
                ...currentMessages.value[assistantIndex],
                status: data.content
              }
              currentMessages.value.splice(assistantIndex, 1, updatedMsg)
            } else if (data.type === 'content') {
              console.log('✍️ 内容片段:', data.content)
              
              const currentMsg = currentMessages.value[assistantIndex]
              const updatedMsg = {
                ...currentMsg,
                content: currentMsg.content + data.content,
                status: '' // 清除状态
              }
              // 使用 splice 替换，强制触发响应式更新
              currentMessages.value.splice(assistantIndex, 1, updatedMsg)
              
              // 滚动到底部
              
              requestAnimationFrame(() => {
                scrollToBottom()
              })
            }
          } catch (e) {
            console.error('❌ 处理chunk失败:', e, chunk)
          }
        },
        async () => {
          console.log('✅ 流式完成')
          isLoading.value = false
          
          // 清除状态
          if (currentMessages.value[assistantIndex]) {
            currentMessages.value[assistantIndex].status = ''
          }
          
          await scrollToBottom()
          await loadConversations()
        },
        (error) => {
          console.error('❌ 流式错误:', error)
          currentMessages.value[assistantIndex].content = '请求失败，请重试'
          isLoading.value = false
          ElMessage.error('连接中断，请重试')
        }
      )
    }
  } catch (e: any) {
    console.error('发送失败:', e)
    currentMessages.value[assistantIndex].content = '请求失败，请重试'
    ElMessage.error(e.response?.data?.detail || '发送失败')
    isLoading.value = false
  }

  await scrollToBottom()
}

// ===== 重新生成 =====
const handleRegenerate = async (index: number) => {
  // 找到对应的 assistant 消息
  const assistantMsg = currentMessages.value[index]
  if (!assistantMsg || assistantMsg.role !== 'assistant') return

  // 获取上一条用户消息（索引减1）
  const userMsg = currentMessages.value[index - 1]
  if (!userMsg || userMsg.role !== 'user') {
    ElMessage.warning('未找到对应的用户消息')
    return
  }

  // 设置加载状态
  assistantMsg.content = ''
  assistantMsg.status = '🔄 重新生成中...'

  try {
    // 获取当前的会话 ID
    const formData = new FormData()
    formData.append('message', userMsg.content || '')
    imageList.value.forEach(img => formData.append('files', img.raw))
    if (currentConversationId.value) {
      formData.append('conversation_id', String(currentConversationId.value))
    }
    
    // 调用 need-tool 判断
    const needToolRes = await checkNeedTool(formData)
    const needTool = needToolRes.data.need_tool

    if (needTool) {
      // 普通接口
      const res = await sendMessageApi(formData)
      assistantMsg.content = res.data.response
      assistantMsg.status = ''
      ElMessage.success('重新生成成功')
    } else {
      // 流式接口
      let fullContent = ''
      assistantMsg.status = '🔄 重新生成中...'

      await new Promise((resolve, reject) => {
        sendMessageStream(
          formData,
          (chunk) => {
            try {
              const data = JSON.parse(chunk)
              if (data.type === 'status') {
                assistantMsg.status = data.content
              } else if (data.type === 'content') {
                fullContent += data.content
                assistantMsg.content = fullContent
                assistantMsg.status = ''
                scrollToBottom()
              }
            } catch (e) {
              console.error('处理chunk失败:', e)
            }
          },
          () => {
            assistantMsg.status = ''
            resolve(true)
          },
          (error) => {
            assistantMsg.content = '❌ 重新生成失败，请重试'
            assistantMsg.status = ''
            reject(error)
          }
        )
      })

      ElMessage.success('重新生成成功')
    }
  } catch (e: any) {
    console.error('重新生成失败:', e)
    assistantMsg.content = '❌ 重新生成失败，请重试'
    assistantMsg.status = ''
    ElMessage.error(e.response?.data?.detail || '重新生成失败')
  }

  await scrollToBottom()
}

// ===== 文档上传成功 =====
const handleDocUploaded = (doc: any) => {
  ElMessage.success(`文档 "${doc.filename}" 上传成功，问答时将自动检索`)
}

// ===== 退出登录 =====
const handleLogout = () => {
  ElMessageBox.confirm('确定要退出登录吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(() => {
    userStore.logout()
    router.push('/login')
  })
}

const handleMessagesScroll = throttle(() => {
  const container = messagesContainer.value
  const convId = currentConversationId.value

  if (!container || convId === null || convId === TEMP_CONV_ID) return
  if (isLoadingHistory.value || offset.value >= total.value) return
  if (container.scrollTop > LOAD_MORE_THRESHOLD) return

  loadConversationMessages(convId, 10, false)
}, 200)

const handleResize = () => {
  isMobile.value = innerWidth <= 768
}

const initConversation = async () => {
  if (conversations.value.length > 0) {
    const first = conversations.value[0]
    currentConversationId.value = first.id
    await loadConversationMessages(first.id)
  } else {
    currentConversationId.value = 0
    currentMessages.value = []
  }

  messagesContainer.value?.addEventListener('scroll', handleMessagesScroll)
}

// ===== 生命周期 =====
onMounted(async () => {
  window.addEventListener('resize', handleResize)
  await loadConversations()
  initConversation()
})

onBeforeUnmount(() => {
  messagesContainer.value?.removeEventListener('scroll', handleMessagesScroll)
})
</script>
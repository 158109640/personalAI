<!-- frontend/src/components/VoiceButton.vue -->
<template>
  <div class="voice-btn-wrapper">
    <!-- 录音按钮 -->
    <el-tooltip :content="isRecording ? '松开停止录音' : '点击录音'" placement="top">
      <div
        class="voice-btn"
        :class="{
          recording: isRecording,
          processing: isProcessing,
          disabled: disabled
        }"
        @mousedown="startRecording"
        @mouseup="stopRecording"
        @mouseleave="stopRecording"
        @touchstart="startRecording"
        @touchend="stopRecording"
        @touchcancel="stopRecording"
      >
        <el-icon v-if="!isRecording && !isProcessing"><Microphone /></el-icon>
        <el-icon v-if="isRecording" class="recording-icon"><Mic /></el-icon>
        <el-icon v-if="isProcessing" class="loading-icon"><Loading /></el-icon>
        <span v-if="isRecording" class="recording-dot"></span>
      </div>
    </el-tooltip>

    <!-- 录音状态提示 -->
    <div v-if="isRecording" class="recording-tip">
      <span class="pulse-dot"></span>
      <span>录音中... 松开发送</span>
      <span class="recording-time">{{ calculateTime(recordingDuration) }}</span>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="voice-error">{{ error }}</div>
  </div>
</template>

<style scoped lang="scss">
.voice-btn-wrapper {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  position: relative;
}

.voice-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;

  &:hover:not(.recording):not(.processing):not(.disabled) {
    background: #f3f4f6;
    color: #374151;
  }

  .el-icon {
    font-size: 18px;
  }

  &.recording {
    background: #ef4444;
    color: white;
    animation: pulse 1.2s ease-in-out infinite;
    
    .recording-dot {
      position: absolute;
      top: -4px;
      right: -4px;
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: #ef4444;
      border: 2px solid white;
      animation: blink 0.8s ease-in-out infinite;
    }
  }

  &.processing {
    background: #f59e0b;
    color: white;
    cursor: wait;
  }

  &.disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.recording-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 12px;
  background: #fef2f2;
  border-radius: 12px;
  color: #dc2626;
  font-size: 13px;
  font-weight: 500;

  .pulse-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #dc2626;
    animation: blink 0.6s ease-in-out infinite;
  }

  .recording-time {
    font-size: 12px;
    color: #6b7280;
    font-weight: 400;
  }
}

.voice-error {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  color: #ef4444;
  font-size: 12px;
  background: white;
  padding: 2px 8px;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  white-space: nowrap;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.05); }
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.2; }
}
</style>

<script setup lang="ts">
import { ref, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { Microphone, Mic, Loading } from '@element-plus/icons-vue'
import { calculateTime } from '@/utils/index'
import { sendVoiceMessageStream } from '@/api/chat' // 新增：流式API
import type { VoiceResponse } from '@/types/chat'

const emit = defineEmits<{
  (e: 'recognized', data: { audio_url: string, reply_text: string, type: 'audio' | 'done' }): void
  (e: 'pushMessage', data: { role: 'user' | 'assistant', type: 'audio' | 'text', content: string, status: string }): void
  (e: 'error', error: string): void
  // 新增：会话ID更新
  (e: 'updateConversationId', conversationId: number): void
  // 新增：流式状态更新
  (e: 'statusUpdate', status: string): void
  // 新增：流式内容更新
  (e: 'contentUpdate', content: string, type: 'audio' | 'content' | 'done'): void
  // 新增：流式完成
  (e: 'streamComplete', fullReply: string): void
}>()

const props = defineProps<{
  disabled?: boolean
  conversationId: number
}>()

// ===== 状态 =====
const isRecording = ref(false)
const isProcessing = ref(false)
const error = ref('')
const recordingDuration = ref(0)
let mediaRecorder: MediaRecorder | null = null
let audioChunks: BlobPart[] = []
let durationTimer: number | null = null
let stream: MediaStream | null = null

// ===== 方法 =====
const startRecording = async () => {
  if (props.disabled || isProcessing.value) return
  if (isRecording.value) return

  error.value = ''

  try {
    // 获取麦克风权限
    stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate: 16000,
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true
      }
    })

    audioChunks = []
    
    // 创建 MediaRecorder
    mediaRecorder = new MediaRecorder(stream, {
      mimeType: 'audio/webm;codecs=opus'
    })

    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.push(event.data)
      }
    }

    mediaRecorder.onstop = async () => {
      // 停止所有音轨
      if (stream) {
        stream.getTracks().forEach(track => track.stop())
        stream = null
      }

      // 如果录音时间太短（小于0.5秒），视为取消
      if (recordingDuration.value < 0.5) {
        isRecording.value = false
        recordingDuration.value = 0
        ElMessage.info('录音时间太短，已取消')
        return
      }

      // 发送音频到后端
      await sendAudio()
    }

    // 开始录音
    mediaRecorder.start()
    isRecording.value = true
    recordingDuration.value = 0

    // 计时器
    durationTimer = window.setInterval(() => {
      recordingDuration.value += 0.1
    }, 100)

  } catch (err) {
    console.error('录音启动失败:', err)
    error.value = '无法访问麦克风，请检查权限设置'
    ElMessage.error('无法访问麦克风')
  }
}

const stopRecording = () => {
  if (mediaRecorder && isRecording.value) {
    mediaRecorder.stop()
    isRecording.value = false
    
    if (durationTimer) {
      clearInterval(durationTimer)
      durationTimer = null
    }
  }
}

// ===== 🔥 核心改动：支持流式响应 =====
const sendAudio = async () => {
  if (audioChunks.length === 0) {
    ElMessage.warning('录音为空，请重试')
    return
  }

  isProcessing.value = true
  error.value = ''

  try {
    // 构建音频文件
    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' })

    // 发送语音消息到聊天界面
    const audioUrl = URL.createObjectURL(audioBlob)
    emit('pushMessage', {
      role: 'user',
      type: 'audio',
      content: audioUrl,
      status: ''
    })
    
    // 构建 FormData
    const formData = new FormData()
    formData.append('audio', audioBlob, 'recording.webm')
    formData.append('conversation_id', props.conversationId.toString())

    // ===== 🔥 使用流式 API =====
    let fullReply = ''
    let audioUrlResponse = ''

    await sendVoiceMessageStream(
      formData,
      (data: VoiceResponse) => {
        // 类型断言，确保TypeScript识别VoiceResponse的type属性
        const streamData = data as { type: string, conversation_id?: number } & VoiceResponse;
        console.log('收到数据:', streamData)
        switch (streamData.type) {
          case 'audio':
            // 语音识别结果
            audioUrlResponse = data.content || ''
            
            // 保持向后兼容：触发 recognized 事件
            emit('recognized', {
              audio_url: audioUrlResponse,
              reply_text: '', // 流式模式下，reply_text 会通过 content 逐步返回
              type: 'audio'
            })
            break

          case 'status':
            // 状态更新
            emit('statusUpdate', data.content)
            break

          case 'content':
            // AI 回复内容（逐字累积）
            fullReply += data.content
            // 实时通知父组件内容更新
            emit('contentUpdate', fullReply, 'content')
            break

          case 'conversation_id':
            // 会话ID更新
            if (streamData.conversation_id) {
              emit('updateConversationId', streamData.conversation_id)
            }
            break

          case 'done':
            // 触发完成事件
            emit('streamComplete', fullReply)
            
            // 保持向后兼容：触发 recognized 事件（带完整回复）
            if (fullReply) {
              emit('recognized', {
                audio_url: audioUrlResponse,
                reply_text: fullReply,
                type: 'done'
              })
            }
            break

          default:
            // 尝试兼容旧格式
            if (data.success !== undefined) {
              // 旧格式响应
              if (data.success) {
                emit('recognized', {
                  audio_url: data.audio_url,
                  reply_text: data.reply_text,
                  type: 'done'
                })
              } else {
                throw new Error(data.err_msg || '识别失败')
              }
            }
        }
      },
      (error: Error) => {
        console.error('❌ 流式错误:', error)
        const errMsg = error.message || '语音识别失败，请重试'
        ElMessage.error(errMsg)
        emit('error', errMsg)
        isProcessing.value = false
      },
      () => {
        isProcessing.value = false
        audioChunks = []
      }
    )
  } catch (err: any) {
    console.error('语音识别失败:', err)
    error.value = err.message || '语音识别失败，请重试'
    ElMessage.error(error.value)
    emit('error', error.value)
    isProcessing.value = false
    audioChunks = []
  }
}

// ===== 清理 =====
onBeforeUnmount(() => {
  if (mediaRecorder && isRecording.value) {
    mediaRecorder.stop()
  }
  if (stream) {
    stream.getTracks().forEach(track => track.stop())
  }
  if (durationTimer) {
    clearInterval(durationTimer)
  }
})
</script>
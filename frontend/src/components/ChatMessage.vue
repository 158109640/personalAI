<template>
  <article :class="['message', role]">
    <header class="message-avatar">
      {{ role === 'user' ? '👤' : '🤖' }}
    </header>
    <section class="message-bubble">
      <div v-if="attachments?.length" class="message-attachments">
        <template v-for="(att, i) in attachments" :key="i">
          <div v-if="isImage(att)" class="attachment-image">
            <el-image
              :src="att.file_url"
              :preview-src-list="imagePreviewList"
              :initial-index="imagePreviewIndex(att)"
              fit="cover"
              loading="lazy"
            />
          </div>
          <a
            v-else
            class="attachment-file"
            :href="att.file_url"
            target="_blank"
            rel="noopener noreferrer"
          >
            📎 {{ att.file_name }}
          </a>
        </template>
      </div>
      <div v-if="content" class="message-content" v-html="renderedContent" />
      <footer class="message-footer">
        <span class="message-time" v-if="created_at">
          {{ formattedTime }}
        </span>
        <div class="message-actions">
          <!-- 复制按钮（所有消息都有） -->
          <button v-if="type === 'text'" class="action-btn" @click="handleCopy" :title="copySuccess ? '✅ 已复制' : '📋 复制'">
            {{ copySuccess ? '✅' : '📋' }}
          </button>
          <!-- 重新生成按钮（仅 assistant 消息） -->
          <button 
            v-if="role === 'assistant'" 
            class="action-btn" 
            @click="handleRegenerate"
            :disabled="regenerating"
            :title="regenerating ? '生成中...' : '🔄 重新生成'"
          >
            <span :class="{ spinning: regenerating }">🔄</span>
          </button>
        </div>
      </footer>
    </section>
  </article>
</template>

<style scoped lang="scss">
@use '@/assets/styles/variables' as *;
@use '@/assets/styles/mixins' as *;

.message {
  display: flex;
  gap: $spacing-sm;
  margin-bottom: $spacing-md;
  max-width: 85%;

  &.user {
    flex-direction: row-reverse;
    margin-left: auto;

    .message-bubble {
      background: $primary-color;
      color: $bg-white;

      .message-time {
        color: rgba(255, 255, 255, 0.7);
      }
    }
  }

  &.assistant {
    margin-right: auto;

    .message-bubble {
      background: $bg-white;
      box-shadow: $shadow-sm;
    }
  }
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: $radius-full;
  background: $bg-gray;
  @include flex-center;
  font-size: 18px;
  flex-shrink: 0;

  .user & {
    background: $primary-color;
  }
}

.message-bubble {
  padding: $spacing-sm $spacing-md;
  border-radius: 14px;
  max-width: 100%;
  word-wrap: break-word;
}

.message-attachments {
  display: flex;
  flex-wrap: wrap;
  gap: $spacing-sm;
  margin-bottom: $spacing-xs;

  &:last-child {
    margin-bottom: 0;
  }
}

.attachment-image {
  width: 120px;
  height: 120px;
  border-radius: $radius-sm;
  overflow: hidden;
  cursor: pointer;

  :deep(.el-image) {
    width: 100%;
    height: 100%;
  }

  :deep(.el-image__inner) {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
}

.attachment-file {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: $radius-sm;
  background: rgba(0, 0, 0, 0.06);
  color: inherit;
  text-decoration: none;
  font-size: $font-size-sm;
  max-width: 100%;
  word-break: break-all;

  &:hover {
    background: rgba(0, 0, 0, 0.1);
  }

  .user & {
    background: rgba(255, 255, 255, 0.15);

    &:hover {
      background: rgba(255, 255, 255, 0.25);
    }
  }
}

.message-content {
  line-height: 1.6;
  font-size: $font-size-sm;

  :deep(pre) {
    background: #1e1e1e;
    border-radius: $radius-sm;
    padding: $spacing-sm;
    overflow-x: auto;
    margin: $spacing-sm 0;
    position: relative;
  }

  :deep(code) {
    font-family: 'Fira Code', monospace;
    font-size: 0.85em;
  }

  :deep(p) {
    margin: 0 0 4px 0;
  }

  :deep(p:last-child) {
    margin-bottom: 0;
  }

  :deep(ul),
  :deep(ol) {
    margin: 4px 0;
    padding-left: 20px;
  }

  :deep(blockquote) {
    border-left: 3px solid $border-color;
    margin: 4px 0;
    padding-left: $spacing-sm;
    color: $text-secondary;
  }
}

.message-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 4px;
  gap: $spacing-sm;
}

.message-time {
  font-size: 11px;
  color: $text-light;
}

.message-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.message-bubble:hover .message-actions {
  opacity: 1;
}

.action-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 14px;
  padding: 2px 6px;
  border-radius: $radius-sm;
  transition: background 0.2s;
  line-height: 1;
  
  &:hover:not(:disabled) {
    background: rgba(0, 0, 0, 0.08);
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .user & {
    &:hover:not(:disabled) {
      background: rgba(255, 255, 255, 0.2);
    }
  }
}

.spinning {
  display: inline-block;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { marked } from 'marked'
import hljs from 'highlight.js'
import 'highlight.js/styles/github-dark.css'
import type { Attachment } from '@/types/chat'

const props = defineProps<{
  role: 'user' | 'assistant'
  content: string
  type: string
  attachments?: Attachment[]
  created_at?: number
  index?: number
}>()

const isImage = (att: Attachment) => {
  if (att.file_type?.startsWith('image/')) return true
  return /\.(jpe?g|png|gif|webp|bmp|svg)$/i.test(att.file_name)
}

const imagePreviewList = computed(() =>
  (props.attachments ?? []).filter(isImage).map((att) => att.file_url)
)

const imagePreviewIndex = (att: Attachment) =>
  imagePreviewList.value.indexOf(att.file_url)

const emit = defineEmits<{
  regenerate: [index: number]  // 触发时传索引
}>()

// ---------- 复制 ----------
const copySuccess = ref(false)
let copyTimer: ReturnType<typeof setTimeout> | null = null

const handleCopy = async () => {
  try {
    await navigator.clipboard.writeText(props.content)
    copySuccess.value = true
    if (copyTimer) clearTimeout(copyTimer)
    copyTimer = setTimeout(() => {
      copySuccess.value = false
    }, 2000)
  } catch {
    // 降级方案：使用 fallback
    try {
      const textarea = document.createElement('textarea')
      textarea.value = props.content
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
      copySuccess.value = true
      if (copyTimer) clearTimeout(copyTimer)
      copyTimer = setTimeout(() => {
        copySuccess.value = false
      }, 2000)
    } catch {
      // 静默失败
    }
  }
}

// ---------- 重新生成 ----------
const regenerating = ref(false)

const handleRegenerate = async () => {
  if (regenerating.value || !props.index) return
  regenerating.value = true
  try {
    await emit('regenerate', props.index)
  } finally {
    regenerating.value = false
  }
}

// ---------- Markdown 渲染 ----------
marked.use({
  renderer: {
    code(token: { text: string; lang?: string }) {
      const code = token.text
      const language = token.lang
      const validLang = language && hljs.getLanguage(language) ? language : 'plaintext'
      const highlighted = hljs.highlight(code, { language: validLang }).value
      return `<pre><code class="hljs language-${validLang}">${highlighted}</code></pre>`
    }
  }
})

const baseUrl = import.meta.env.VITE_API_BASE_URL
const renderedContent = computed(() => {
  if (!props.content) return ''
  const audio_url = props.content.startsWith('blob:http') ? props.content : baseUrl + props.content
  if (props.type === 'audio') return `<audio src="${audio_url}" controls></audio>`
  return marked.parse(props.content) as string
})

const formattedTime = computed(() => {
  if (!props.created_at) return ''
  const date = new Date(props.created_at)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
})
</script>
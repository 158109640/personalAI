import request, { streamRequest } from '@/utils/request'
import type { ChatResponse, NeedToolResponse } from '@/types/chat'
import { useUserStore } from '@/stores/user'

export const sendMessage = (formData: FormData) => {
  return request.post<ChatResponse>('/chat', formData)
}

export const sendMessageStream = (
  formData: FormData,
  onChunk: (chunk: string) => void,
  onDone: () => void,
  onError: (error: any) => void
) => {
  const token = useUserStore().token
  
  fetch('/api/chat/stream', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    },
    body: formData
  })
  .then(async (response) => {
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const reader = response.body?.getReader()
    const decoder = new TextDecoder()
    
    if (!reader) {
      onDone()
      return
    }
    
    let buffer = ''
    
    while (true) {
      const { done, value } = await reader.read()
      
      if (done) {
        // 处理最后的缓冲
        if (buffer.trim()) {
          const lines = buffer.split('\n')
          for (const line of lines) {
            if (line.trim() && line.startsWith('data: ')) {
              const jsonStr = line.slice(6).trim()
              if (jsonStr && jsonStr !== '[DONE]') {
                onChunk(jsonStr) // 直接传递 JSON 字符串
              }
            }
          }
        }
        onDone()
        break
      }
      
      const chunk = decoder.decode(value, { stream: true })
      buffer += chunk
      
      // 按行分割处理
      let lines = buffer.split('\n')
      buffer = lines.pop() || ''
      
      for (const line of lines) {
        if (line.trim() && line.startsWith('data: ')) {
          const jsonStr = line.slice(6).trim()
          if (jsonStr && jsonStr !== '[DONE]') {
            onChunk(jsonStr) // 直接传递 JSON 字符串
          }
        }
      }
    }
  })
  .catch((error) => {
    console.error('请求失败:', error)
    onError(error)
  })
}

export const checkNeedTool = (formData: FormData) => {
  return request.post<NeedToolResponse>('/chat/need-tool', formData)
}

export const sendVoiceMessage = (formData: FormData) => {
  return request.post<string>('/voice/voice-to-text', formData)
}

// ===== 新增：流式请求 =====
export const sendVoiceMessageStream = (
  formData: FormData,
  onMessage: (data: any) => void,
  onError?: (error: any) => void,
  onComplete?: () => void
) => {
  return streamRequest('/voice/voice-to-text', {
    method: 'POST',
    data: formData,
    headers: {
      // Content-Type 让浏览器自动设置（FormData 边界）
    },
    onMessage,
    onError,
    onComplete,
  })
}

// 会话管理
export const getConversations = () => {
  return request.get('/chat/conversations')
}

export const getConversationMessages = (conversationId: number, limit: number = 10, offset: number = 0) => {
  return request.get(`/chat/conversations/${conversationId}?limit=${limit}&offset=${offset}`)
}

export const deleteConversation = (conversationId: number) => {
  return request.delete(`/chat/conversations/${conversationId}`)
}

// 获取文档
export const listDocuments = () => {
  return request.get('/documents/list')
}

export const deleteDocument = (docId: string) => {
  return request.delete(`/documents/${docId}`)
}

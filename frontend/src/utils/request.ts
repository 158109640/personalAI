import axios from 'axios'
import { useUserStore } from '@/stores/user'
import router from '@/router'
import { StreamOptions } from '@/types/chat'

const request = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

request.interceptors.request.use((config) => {
  const userStore = useUserStore()
  const token = userStore.token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

request.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const userStore = useUserStore()
      userStore.clearAuth()
      if (router.currentRoute.value.path !== '/login') {
        router.push('/login')
      }
    }
    return Promise.reject(error)
  }
)

// ===== 新增：流式请求方法 =====

export const streamRequest = async (
  url: string,
  options: StreamOptions
): Promise<void> => {
  const { method = 'POST', data, headers = {}, onMessage, onError, onComplete } = options

  try {
    // 获取 token
    const userStore = useUserStore()
    const token = userStore.token

    // 构建完整 URL
    const fullUrl = `/api${url.startsWith('/') ? '' : '/'}${url}`

    const response = await fetch(fullUrl, {
      method,
      headers: {
        ...headers,
        'Accept': 'text/event-stream',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      },
      body: data instanceof FormData ? data : JSON.stringify(data),
    })

    if (!response.ok) {
      // 处理 401
      if (response.status === 401) {
        const userStore = useUserStore()
        userStore.clearAuth()
        if (router.currentRoute.value.path !== '/login') {
          router.push('/login')
        }
        throw new Error('未授权，请重新登录')
      }
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    if (!response.body) {
      throw new Error('Response body is null')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        onComplete?.()
        break
      }

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.trim()) {
          try {
            const parsed = JSON.parse(line)
            onMessage(parsed)
          } catch (e) {
            // 如果不是 JSON，直接传递原始字符串
            onMessage({ raw: line })
          }
        }
      }
    }
  } catch (error) {
    console.error('流式请求失败:', error)
    onError?.(error)
  }
}

export default request

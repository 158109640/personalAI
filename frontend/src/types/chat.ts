export type Attachment = {
  file_name: string
  file_url: string
  file_type?: string
  file_size?: number
}

export interface NeedToolResponse {
  need_tool: boolean
  use_rag: boolean
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  type: 'text' | 'audio'
  content: string
  attachments?: Attachment[]
  created_at?: number | null
  status?: string
}

export interface ChatRequest {
  message: string
  conversation_id?: number | null
}

export interface ChatResponse {
  response: string
  type: 'text' | 'audio'
  conversation_id: number
}

export interface VoiceResponse {
  success: boolean
  recognized_text: string
  reply_text: string
  err_no: number
  err_msg: string
  audio_url: string
  audio_size: number
  content: string
}

export interface DocumentQueryRequest {
  question: string
  doc_id: string
}

export type Conversation = {
  id: number
  name: string
  title: string
  last_message: ChatMessage | null
  created_at: string
  updated_at: string
}

export interface StreamOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  data?: any
  headers?: Record<string, string>
  onMessage: (data: any) => void
  onError?: (error: any) => void
  onComplete?: () => void
}

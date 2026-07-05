export type Attachment = {
  file_name: string
  file_url: string
  file_type?: string
  file_size?: number
}

export interface ChatMessage {
  role: 'user' | 'assistant'
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
  conversation_id: number
}

export interface DocumentQueryRequest {
  question: string
  doc_id: string
}

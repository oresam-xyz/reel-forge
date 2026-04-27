import client from './client'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatResponse {
  reply: string
  action?: { type: string; path: string } | null
  awaiting_approval?: boolean
}

export interface ChatSession {
  brand_name: string
  cost_usd: number
  updated_at: string
}

export const sendMessage = (messages: ChatMessage[], brand_name = '__inbox__') =>
  client.post<ChatResponse>('/api/chat', { messages, brand_name }).then((r) => r.data)

export const getChatHistory = (brand_name: string) =>
  client.get<{ messages: ChatMessage[] }>(`/api/chat/history/${brand_name}`).then((r) => r.data)

export const listChatSessions = () =>
  client.get<ChatSession[]>('/api/chat/sessions').then((r) => r.data)

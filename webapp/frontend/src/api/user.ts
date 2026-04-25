import client from './client'

export interface UserSettings {
  visual_model?: string
  target_duration?: number
}

export interface Me {
  id: number
  name: string | null
  email: string
  created_at: string
  settings: UserSettings
}

export const getMe = () => client.get<Me>('/api/me').then((r) => r.data)
export const patchMe = (body: { name?: string; settings?: UserSettings }) =>
  client.patch<Me>('/api/me', body).then((r) => r.data)

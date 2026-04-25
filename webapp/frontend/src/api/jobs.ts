import client from './client'
import type { Job } from './campaigns'

export interface ScriptSegmentPatch {
  segment_id: number
  narration?: string
  visual_prompt?: string
  duration_seconds?: number
}

export const getJob = (id: number) => client.get<Job>(`/api/jobs/${id}`).then((r) => r.data)
export const approveJob = (id: number, feedback = '') =>
  client.post(`/api/jobs/${id}/approve`, { feedback }).then((r) => r.data)
export const rejectJob = (id: number, feedback: string) =>
  client.post(`/api/jobs/${id}/reject`, { feedback }).then((r) => r.data)
export const retryJob = (id: number) => client.post(`/api/jobs/${id}/retry`).then((r) => r.data)
export const resetPhase = (id: number, phase: string) =>
  client.post<{ ok: boolean }>(`/api/jobs/${id}/reset`, { phase }).then((r) => r.data)
export const patchScript = (id: number, segments: ScriptSegmentPatch[]) =>
  client.patch<{ ok: boolean }>(`/api/jobs/${id}/script`, { segments }).then((r) => r.data)
export const getPhaseData = (id: number, phase: string) =>
  client.get(`/api/jobs/${id}/phases/${phase}`).then((r) => r.data)

export interface SplitPart {
  filename: string
  size_mb: number
  path: string
}

export interface SplitResult {
  parts: SplitPart[]
  num_parts: number
}

export const splitJobVideo = (id: number, max_size_mb = 10) =>
  client.post<SplitResult>(`/api/jobs/${id}/split`, { max_size_mb }).then((r) => r.data)

export const assetFileUrl = (id: number, filename: string) => {
  const token = localStorage.getItem('rf_token')
  const base = `${client.defaults.baseURL}/api/jobs/${id}/assets/${encodeURIComponent(filename)}`
  return token ? `${base}?token=${encodeURIComponent(token)}` : base
}

export const projectFileUrl = (id: number, filename: string) => {
  const token = localStorage.getItem('rf_token')
  const base = `${client.defaults.baseURL}/api/jobs/${id}/files/${encodeURIComponent(filename)}`
  return token ? `${base}?token=${encodeURIComponent(token)}` : base
}

export const videoUrl = (id: number) => {
  const token = localStorage.getItem('rf_token')
  const base = `${client.defaults.baseURL}/api/jobs/${id}/video`
  return token ? `${base}?token=${encodeURIComponent(token)}` : base
}

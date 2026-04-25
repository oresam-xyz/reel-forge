import client from './client'
import type { Job } from './campaigns'

export const getJob = (id: number) => client.get<Job>(`/api/jobs/${id}`).then((r) => r.data)
export const approveJob = (id: number, feedback = '') =>
  client.post(`/api/jobs/${id}/approve`, { feedback }).then((r) => r.data)
export const rejectJob = (id: number, feedback: string) =>
  client.post(`/api/jobs/${id}/reject`, { feedback }).then((r) => r.data)
export const retryJob = (id: number) => client.post(`/api/jobs/${id}/retry`).then((r) => r.data)
export const getPhaseData = (id: number, phase: string) =>
  client.get(`/api/jobs/${id}/phases/${phase}`).then((r) => r.data)

export const videoUrl = (id: number) => {
  const token = localStorage.getItem('rf_token')
  const base = `${client.defaults.baseURL}/api/jobs/${id}/video`
  return token ? `${base}?token=${encodeURIComponent(token)}` : base
}

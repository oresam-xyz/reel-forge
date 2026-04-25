import client from './client'

export interface Brief {
  product: string
  audience: string
  pain_point: string
  cta: string
  tone: string
  vertical: string
}

export interface Campaign {
  id: number
  name: string
  brief: Brief
  brand_name: string
  auto_approve: boolean
  visual_model: string
  target_duration: number
  created_at: string
  pending: number
  running: number
  review_pending: number
  complete: number
  failed: number
  total_cost_usd: number | null
}

export interface CampaignDetail extends Campaign {
  jobs: Job[]
}

export interface Job {
  id: number
  campaign_id: number
  angle: string
  status: 'pending' | 'running' | 'review_pending' | 'complete' | 'failed'
  phase: string | null
  project_id: string | null
  output_path: string | null
  plan_json: Record<string, unknown> | null
  error: string | null
  created_at: string
  updated_at: string
  cost_usd: number | null
}

export const listCampaigns = () => client.get<Campaign[]>('/api/campaigns').then((r) => r.data)
export const getCampaign = (id: number) => client.get<CampaignDetail>(`/api/campaigns/${id}`).then((r) => r.data)
export const createCampaign = (body: { name: string; brief: Brief; brand_name: string; auto_approve: boolean; visual_model: string; target_duration: number }) =>
  client.post<Campaign>('/api/campaigns', body).then((r) => r.data)
export const deleteCampaign = (id: number) => client.delete(`/api/campaigns/${id}`)
export const queueJobs = (campaignId: number, angles: string[]) =>
  client.post(`/api/campaigns/${campaignId}/jobs`, { angles }).then((r) => r.data)
export const suggestAngles = (campaignId: number) =>
  client.post<{ angles: string[] }>(`/api/campaigns/${campaignId}/suggest-angles`).then((r) => r.data)

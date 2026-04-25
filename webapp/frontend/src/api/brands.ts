import client from './client'

export interface BrandTone {
  voice?: string
  reading_pace?: string
  vocabulary?: string
}

export interface BrandVoiceProfile {
  provider?: string
  voice_id?: string
  speed?: number
  pitch_adjust?: number
}

export interface BrandVisualStyle {
  aesthetic?: string
  colour_palette?: string[]
  caption_style?: string
  image_prompt_prefix?: string
}

export interface BrandIdentity {
  name: string
  tone: BrandTone
  voice_profile: BrandVoiceProfile
  visual_style: BrandVisualStyle
  pronunciations: Record<string, string>
}

export const listBrands = () => client.get<string[]>('/api/brands').then((r) => r.data)
export const getBrand = (name: string) =>
  client.get<BrandIdentity>(`/api/brands/${name}`).then((r) => r.data)
export const patchBrand = (
  name: string,
  body: {
    tone?: Partial<BrandTone>
    voice_profile?: Partial<BrandVoiceProfile>
    visual_style?: Partial<BrandVisualStyle>
    pronunciations?: Record<string, string>
  },
) => client.patch<BrandIdentity>(`/api/brands/${name}`, body).then((r) => r.data)

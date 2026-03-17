import { api } from './api'

export interface UsageMetric {
  used: number
  limit: number | null
  remaining: number | null
  unit: string
}

export interface PlanSummary {
  id: string
  code: string
  name: string
  monthly_story_limit: number | null
  max_pages_per_story: number | null
  image_quality_mode: string | null
  voice_clone_limit: number | null
  monthly_audio_chars_limit: number | null
  price_cents: number
}

export interface SubscriptionSummary {
  id: string
  status: string
  current_period_start: string | null
  current_period_end: string | null
  plan: PlanSummary
  usage: Record<string, UsageMetric>
}

export async function getSubscriptionSummary(): Promise<SubscriptionSummary> {
  const { data } = await api.get<SubscriptionSummary>('/subscription')
  return data
}

import { api } from './api'

export type ConsentType = 'terms_of_service' | 'privacy_policy' | 'voice_cloning'

export interface ConsentStatusItem {
  consent_type: ConsentType
  required_version: string
  accepted_version: string | null
  accepted_at: string | null
  is_current: boolean
}

export interface ConsentStatusResponse {
  items: ConsentStatusItem[]
  requires_legal_consent: boolean
  has_voice_cloning_consent: boolean
}

export interface ConsentAcceptItem {
  consent_type: ConsentType
  accepted_version: string
}

export async function getConsentStatus(): Promise<ConsentStatusResponse> {
  const { data } = await api.get<ConsentStatusResponse>('/consents/status')
  return data
}

export async function acceptConsents(consents: ConsentAcceptItem[]): Promise<ConsentStatusResponse> {
  const { data } = await api.post<ConsentStatusResponse>('/consents', { consents })
  return data
}

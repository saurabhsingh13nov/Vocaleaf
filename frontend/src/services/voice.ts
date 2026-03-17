import { api } from './api'

export interface VoiceSample {
  id: string
  asset_id: string | null
  duration_seconds: number | null
  status: 'pending' | 'uploaded' | 'processing' | 'accepted' | 'rejected'
  created_at: string
}

export interface VoiceProfile {
  id: string
  user_id: string
  display_name: string
  status: 'pending' | 'processing' | 'ready' | 'failed' | 'deleted'
  consent_confirmed: boolean
  default_for_user: boolean
  created_at: string
  updated_at: string
  samples: VoiceSample[]
}

export interface CreateVoiceProfilePayload {
  display_name: string
  consent_confirmed?: boolean | null
  default_for_user?: boolean
}

export interface VoiceSampleUploadPayload {
  mime_type: string
  file_size_bytes: number
  duration_seconds: number
}

export interface VoiceSampleUploadInit {
  sample_id: string
  asset_id: string
  upload_url: string
  expires_at: string
}

export const SUPPORTED_VOICE_SAMPLE_MIME_TYPES = new Set([
  'audio/webm',
  'audio/wav',
  'audio/x-wav',
  'audio/wave',
  'audio/aac',
  'audio/m4a',
  'audio/mpeg',
  'audio/mp4',
  'audio/x-m4a',
  'audio/ogg',
])

export function normalizeVoiceSampleMimeType(mimeType: string): string {
  const normalized = mimeType.split(';', 1)[0]?.trim().toLowerCase() ?? ''

  if (normalized === 'audio/wave') {
    return 'audio/wav'
  }

  return normalized
}

export function isSupportedVoiceSampleMimeType(mimeType: string): boolean {
  return SUPPORTED_VOICE_SAMPLE_MIME_TYPES.has(normalizeVoiceSampleMimeType(mimeType))
}

export async function getVoiceProfiles(): Promise<VoiceProfile[]> {
  const { data } = await api.get<VoiceProfile[]>('/voice-profiles')
  return data
}

export async function getVoiceProfile(profileId: string): Promise<VoiceProfile> {
  const { data } = await api.get<VoiceProfile>(`/voice-profiles/${profileId}`)
  return data
}

export async function createVoiceProfile(payload: CreateVoiceProfilePayload): Promise<VoiceProfile> {
  const { data } = await api.post<VoiceProfile>('/voice-profiles', payload)
  return data
}

export async function cloneVoiceProfile(profileId: string): Promise<VoiceProfile> {
  const { data } = await api.post<VoiceProfile>(`/voice-profiles/${profileId}/clone`)
  return data
}

export async function requestVoiceSampleUpload(
  profileId: string,
  payload: VoiceSampleUploadPayload,
): Promise<VoiceSampleUploadInit> {
  const { data } = await api.post<VoiceSampleUploadInit>(`/voice-profiles/${profileId}/samples`, payload)
  return data
}

export async function confirmVoiceSampleUpload(
  profileId: string,
  sampleId: string,
): Promise<VoiceSample> {
  const { data } = await api.post<VoiceSample>(`/voice-profiles/${profileId}/samples/${sampleId}/confirm`)
  return data
}

export async function deleteVoiceSample(profileId: string, sampleId: string): Promise<void> {
  await api.delete(`/voice-profiles/${profileId}/samples/${sampleId}`)
}

export async function deleteVoiceProfile(profileId: string): Promise<void> {
  await api.delete(`/voice-profiles/${profileId}`)
}

export async function uploadVoiceSampleFile(uploadUrl: string, file: Blob, mimeType: string): Promise<void> {
  const normalizedMimeType = normalizeVoiceSampleMimeType(mimeType)
  const response = await fetch(uploadUrl, {
    method: 'PUT',
    body: file,
    headers: {
      'Content-Type': normalizedMimeType,
    },
  })

  if (!response.ok) {
    throw new Error('Failed to upload voice sample')
  }
}

export async function getAudioDurationSeconds(file: Blob): Promise<number> {
  const objectUrl = URL.createObjectURL(file)

  try {
    const duration = await new Promise<number>((resolve, reject) => {
      const audio = document.createElement('audio')
      audio.preload = 'metadata'
      audio.src = objectUrl
      audio.onloadedmetadata = () => {
        if (Number.isFinite(audio.duration) && audio.duration > 0) {
          resolve(audio.duration)
          return
        }

        reject(new Error('Unable to determine audio duration'))
      }
      audio.onerror = () => reject(new Error('Unable to read audio metadata'))
    })

    return duration
  } finally {
    URL.revokeObjectURL(objectUrl)
  }
}

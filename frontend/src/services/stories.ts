import { api } from './api'

export type StoryStatus = 'draft' | 'generating' | 'ready' | 'failed' | 'deleted'
export type StoryPageStatus = 'pending' | 'text_ready' | 'image_ready' | 'audio_ready' | 'complete' | 'failed'

export interface StoryPage {
  id: string
  page_number: number
  text_content: string | null
  image_prompt: string | null
  continuity_notes: string | null
  status: StoryPageStatus
  image_asset_id: string | null
  audio_asset_id: string | null
  duration_ms: number | null
  created_at: string
  updated_at: string
}

export interface Story {
  id: string
  user_id: string
  child_id: string
  voice_profile_id: string | null
  title: string | null
  prompt: string | null
  theme: string | null
  status: StoryStatus
  target_page_count: number | null
  reading_level: string | null
  language: string
  art_style: string | null
  latest_error_message: string | null
  created_at: string
  updated_at: string
  pages: StoryPage[]
}

export interface StoryListItem {
  id: string
  child_id: string
  title: string | null
  theme: string | null
  status: StoryStatus
  target_page_count: number | null
  art_style: string | null
  latest_error_message: string | null
  created_at: string
  updated_at: string
}

export interface CreateStoryPayload {
  child_id: string
  voice_profile_id?: string | null
  prompt?: string | null
  theme?: string | null
  target_page_count?: number
  reading_level?: string | null
  art_style?: string | null
  language?: string
}

export async function createStory(payload: CreateStoryPayload): Promise<Story> {
  const { data } = await api.post<Story>('/stories', payload)
  return data
}

export async function getStories(limit = 20, offset = 0): Promise<StoryListItem[]> {
  const { data } = await api.get<StoryListItem[]>('/stories', {
    params: { limit, offset },
  })
  return data
}

export async function getStory(storyId: string): Promise<Story> {
  const { data } = await api.get<Story>(`/stories/${storyId}`)
  return data
}

export async function deleteStory(storyId: string): Promise<void> {
  await api.delete(`/stories/${storyId}`)
}

export interface AssetReadUrlResponse {
  url: string
  expires_at: string
}

export async function getAssetUrl(assetId: string): Promise<AssetReadUrlResponse> {
  const { data } = await api.get<AssetReadUrlResponse>(`/assets/${assetId}/url`)
  return data
}

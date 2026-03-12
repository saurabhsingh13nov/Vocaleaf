import { api } from './api'

export interface Child {
  id: string
  user_id: string
  name: string
  age: number | null
  favorite_themes: Record<string, unknown> | null
  favorite_characters: Record<string, unknown> | null
  bedtime_preferences: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface CreateChildPayload {
  name: string
  age?: number | null
  favorite_themes?: Record<string, unknown> | null
  favorite_characters?: Record<string, unknown> | null
  bedtime_preferences?: Record<string, unknown> | null
}

export interface UpdateChildPayload {
  name?: string
  age?: number | null
  favorite_themes?: Record<string, unknown> | null
  favorite_characters?: Record<string, unknown> | null
  bedtime_preferences?: Record<string, unknown> | null
}

export async function getChildren(): Promise<Child[]> {
  const { data } = await api.get<Child[]>('/children')
  return data
}

export async function createChild(payload: CreateChildPayload): Promise<Child> {
  const { data } = await api.post<Child>('/children', payload)
  return data
}

export async function updateChild(childId: string, payload: UpdateChildPayload): Promise<Child> {
  const { data } = await api.put<Child>(`/children/${childId}`, payload)
  return data
}

export async function deleteChild(childId: string): Promise<void> {
  await api.delete(`/children/${childId}`)
}

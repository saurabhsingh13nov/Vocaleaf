import { api } from './api'

export interface User {
  id: string
  primary_email: string | null
  full_name: string | null
  avatar_url: string | null
  status: string
  email_verified_at: string | null
  created_at: string
}

export interface RegisterPayload {
  email: string
  password: string
  full_name: string
}

export interface LoginPayload {
  email: string
  password: string
}

export interface MessageResponse {
  message: string
}

export async function register(payload: RegisterPayload) {
  const response = await api.post<User>('/auth/register', payload)
  return response.data
}

export async function login(payload: LoginPayload) {
  const response = await api.post<User>('/auth/login', payload)
  return response.data
}

export async function logout() {
  const response = await api.post<MessageResponse>('/auth/logout')
  return response.data
}

export async function refreshSession() {
  const response = await api.post<MessageResponse>('/auth/refresh')
  return response.data
}

export async function fetchCurrentUser() {
  const response = await api.get<User>('/auth/me')
  return response.data
}

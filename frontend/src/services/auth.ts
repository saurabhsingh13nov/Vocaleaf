import { api } from './api'

export type UserRole = 'customer' | 'staff' | 'admin'

export interface User {
  id: string
  primary_email: string | null
  full_name: string | null
  avatar_url: string | null
  status: string
  role: UserRole
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

export interface AuthSessionResponse {
  access_token: string
  refresh_token: string
  user: User
}

export interface RefreshSessionResponse {
  access_token: string
}

function unwrapUser(session: AuthSessionResponse) {
  return session.user
}

export async function register(payload: RegisterPayload) {
  const response = await api.post<AuthSessionResponse>('/auth/register', payload)
  return unwrapUser(response.data)
}

export async function login(payload: LoginPayload) {
  const response = await api.post<AuthSessionResponse>('/auth/login', payload)
  return unwrapUser(response.data)
}

export async function googleAuth(credential: string) {
  const response = await api.post<AuthSessionResponse>('/auth/google', { credential })
  return unwrapUser(response.data)
}

export async function linkGoogleAccount(credential: string, password: string) {
  const response = await api.post<AuthSessionResponse>('/auth/link-google', { credential, password })
  return unwrapUser(response.data)
}

export async function logout() {
  const response = await api.post<MessageResponse>('/auth/logout')
  return response.data
}

export async function refreshSession() {
  const response = await api.post<RefreshSessionResponse>('/auth/refresh')
  return response.data
}

export async function fetchCurrentUser() {
  const response = await api.get<User>('/auth/me')
  return response.data
}

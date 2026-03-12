import axios from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useAuthStore } from '@/stores/auth'
import type { User } from '@/services/auth'
import {
  fetchCurrentUser,
  login,
  logout,
  refreshSession,
  register,
} from '@/services/auth'

vi.mock('@/services/auth', () => ({
  fetchCurrentUser: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  refreshSession: vi.fn(),
  register: vi.fn(),
}))

const mockedFetchCurrentUser = vi.mocked(fetchCurrentUser)
const mockedLogin = vi.mocked(login)
const mockedLogout = vi.mocked(logout)
const mockedRefreshSession = vi.mocked(refreshSession)
const mockedRegister = vi.mocked(register)

const sampleUser: User = {
  id: 'baf6f9f5-f8a8-4c50-a610-486b98f0194f',
  primary_email: 'parent@example.com',
  full_name: 'Parent Reader',
  avatar_url: null,
  status: 'active',
  email_verified_at: null,
  created_at: '2026-03-11T20:00:00Z',
}

function makeAxiosError(status: number, detail?: string) {
  const error = new axios.AxiosError('Request failed')
  error.response = {
    config: {} as never,
    data: detail ? { detail } : {},
    headers: {},
    status,
    statusText: 'Error',
  }
  return error
}

describe('useAuthStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('stores the user after login', async () => {
    mockedLogin.mockResolvedValue(sampleUser)
    const authStore = useAuthStore()

    const result = await authStore.login({
      email: sampleUser.primary_email ?? '',
      password: 'securepass123',
    })

    expect(result).toEqual(sampleUser)
    expect(authStore.user).toEqual(sampleUser)
    expect(authStore.isLoading).toBe(false)
    expect(mockedLogin).toHaveBeenCalledWith({
      email: sampleUser.primary_email,
      password: 'securepass123',
    })
  })

  it('stores the user after register', async () => {
    mockedRegister.mockResolvedValue(sampleUser)
    const authStore = useAuthStore()

    const result = await authStore.register({
      email: sampleUser.primary_email ?? '',
      full_name: sampleUser.full_name ?? '',
      password: 'securepass123',
    })

    expect(result).toEqual(sampleUser)
    expect(authStore.user).toEqual(sampleUser)
    expect(authStore.isLoading).toBe(false)
  })

  it('clears the user after logout', async () => {
    mockedLogout.mockResolvedValue({ message: 'Logged out' })
    const authStore = useAuthStore()
    authStore.user = sampleUser

    await authStore.logout()

    expect(mockedLogout).toHaveBeenCalled()
    expect(authStore.user).toBeNull()
    expect(authStore.isLoading).toBe(false)
  })

  it('stores the current user when fetchUser succeeds', async () => {
    mockedFetchCurrentUser.mockResolvedValue(sampleUser)
    const authStore = useAuthStore()

    const result = await authStore.fetchUser()

    expect(result).toEqual(sampleUser)
    expect(authStore.user).toEqual(sampleUser)
    expect(authStore.isInitialized).toBe(true)
    expect(mockedRefreshSession).not.toHaveBeenCalled()
  })

  it('refreshes the session and retries when fetchUser gets a 401', async () => {
    mockedFetchCurrentUser
      .mockRejectedValueOnce(makeAxiosError(401, 'Not authenticated'))
      .mockResolvedValueOnce(sampleUser)
    mockedRefreshSession.mockResolvedValue({ message: 'Token refreshed' })
    const authStore = useAuthStore()

    const result = await authStore.fetchUser()

    expect(result).toEqual(sampleUser)
    expect(mockedRefreshSession).toHaveBeenCalledTimes(1)
    expect(mockedFetchCurrentUser).toHaveBeenCalledTimes(2)
    expect(authStore.user).toEqual(sampleUser)
    expect(authStore.isInitialized).toBe(true)
  })

  it('clears the user and returns null when refresh also fails', async () => {
    mockedFetchCurrentUser.mockRejectedValue(makeAxiosError(401, 'Not authenticated'))
    mockedRefreshSession.mockRejectedValue(makeAxiosError(401, 'Refresh expired'))
    const authStore = useAuthStore()
    authStore.user = sampleUser

    const result = await authStore.fetchUser()

    expect(result).toBeNull()
    expect(authStore.user).toBeNull()
    expect(authStore.isInitialized).toBe(true)
  })

  it('clearUser resets auth state and marks the store initialized', () => {
    const authStore = useAuthStore()
    authStore.user = sampleUser
    authStore.isInitialized = false

    authStore.clearUser()

    expect(authStore.user).toBeNull()
    expect(authStore.isInitialized).toBe(true)
  })

  it('returns backend detail from getErrorMessage', () => {
    const authStore = useAuthStore()

    expect(authStore.getErrorMessage(makeAxiosError(400, 'Email already registered'))).toBe(
      'Email already registered',
    )
  })

  it('returns a fallback message for unknown errors', () => {
    const authStore = useAuthStore()

    expect(authStore.getErrorMessage(new Error('boom'))).toBe(
      'Something went wrong. Please try again.',
    )
  })
})

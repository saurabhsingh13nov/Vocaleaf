import { beforeEach, describe, expect, it, vi } from 'vitest'

import router from '@/router'
import { useAuthStore } from '@/stores/auth'
import { pinia } from '@/stores/pinia'
import type { User } from '@/services/auth'

const sampleUser: User = {
  id: '3b9df182-0efa-41d7-8c73-fa8920cbad53',
  primary_email: 'reader@example.com',
  full_name: 'Reader Parent',
  avatar_url: null,
  status: 'active',
  role: 'customer',
  email_verified_at: null,
  created_at: '2026-03-11T20:00:00Z',
}

describe('router auth guards', () => {
  beforeEach(async () => {
    vi.restoreAllMocks()

    const authStore = useAuthStore(pinia)
    authStore.user = null
    authStore.isInitialized = true
    authStore.isLoading = false

    await router.replace('/')
  })

  it('redirects unauthenticated users away from dashboard', async () => {
    const authStore = useAuthStore(pinia)
    authStore.clearUser()

    await router.push('/dashboard')

    expect(router.currentRoute.value.name).toBe('login')
  })

  it('redirects authenticated users away from login', async () => {
    const authStore = useAuthStore(pinia)
    authStore.user = sampleUser
    authStore.isInitialized = true

    await router.push('/register')
    await router.push('/login')

    expect(router.currentRoute.value.name).toBe('dashboard')
  })

  it('redirects authenticated users away from register', async () => {
    const authStore = useAuthStore(pinia)
    authStore.user = sampleUser
    authStore.isInitialized = true

    await router.push('/register')

    expect(router.currentRoute.value.name).toBe('dashboard')
  })

  it('allows unauthenticated users to access login', async () => {
    const authStore = useAuthStore(pinia)
    authStore.clearUser()

    await router.push('/login')

    expect(router.currentRoute.value.name).toBe('login')
  })

  it('initializes auth state on first guarded navigation', async () => {
    const authStore = useAuthStore(pinia)
    authStore.user = null
    authStore.isInitialized = false

    const fetchUserSpy = vi.spyOn(authStore, 'fetchUser').mockImplementation(async () => {
      authStore.user = sampleUser
      authStore.isInitialized = true
      return sampleUser
    })

    await router.push('/dashboard')

    expect(fetchUserSpy).toHaveBeenCalledTimes(1)
    expect(router.currentRoute.value.name).toBe('dashboard')
  })

  it('redirects unauthenticated users away from voice profiles', async () => {
    const authStore = useAuthStore(pinia)
    authStore.clearUser()

    await router.push('/voice-profiles')

    expect(router.currentRoute.value.name).toBe('login')
  })

  it('redirects unauthenticated users away from story creation', async () => {
    const authStore = useAuthStore(pinia)
    authStore.clearUser()

    await router.push('/stories/new')

    expect(router.currentRoute.value.name).toBe('login')
  })

  it('redirects unauthenticated users away from story detail', async () => {
    const authStore = useAuthStore(pinia)
    authStore.clearUser()

    await router.push('/stories/story-123')

    expect(router.currentRoute.value.name).toBe('login')
  })

  it('redirects non-staff users away from admin', async () => {
    const authStore = useAuthStore(pinia)
    authStore.user = sampleUser
    authStore.isInitialized = true

    await router.push('/admin')

    expect(router.currentRoute.value.name).toBe('dashboard')
  })

  it('allows staff users to access admin', async () => {
    const authStore = useAuthStore(pinia)
    authStore.user = { ...sampleUser, role: 'staff' }
    authStore.isInitialized = true

    await router.push('/admin')

    expect(router.currentRoute.value.name).toBe('admin')
  })

  it('clears user state and redirects to login when initialization throws', async () => {
    const authStore = useAuthStore(pinia)
    authStore.user = sampleUser
    authStore.isInitialized = false

    const fetchUserSpy = vi.spyOn(authStore, 'fetchUser').mockRejectedValue(new Error('network'))
    const clearUserSpy = vi.spyOn(authStore, 'clearUser')

    await router.push('/dashboard')

    expect(fetchUserSpy).toHaveBeenCalledTimes(1)
    expect(clearUserSpy).toHaveBeenCalledTimes(1)
    expect(router.currentRoute.value.name).toBe('login')
    expect(authStore.user).toBeNull()
    expect(authStore.isInitialized).toBe(true)
  })
})

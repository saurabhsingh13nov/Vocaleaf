import axios from 'axios'
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  fetchCurrentUser,
  login as loginRequest,
  logout as logoutRequest,
  refreshSession,
  register as registerRequest,
  type LoginPayload,
  type RegisterPayload,
  type User,
} from '@/services/auth'

function getErrorMessage(error: unknown) {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail

    if (typeof detail === 'string' && detail.trim().length > 0) {
      return detail
    }
  }

  return 'Something went wrong. Please try again.'
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const isLoading = ref(false)
  const isInitialized = ref(false)

  const isAuthenticated = computed(() => user.value !== null)

  async function register(payload: RegisterPayload) {
    isLoading.value = true

    try {
      const registeredUser = await registerRequest(payload)
      user.value = registeredUser
      return registeredUser
    } finally {
      isLoading.value = false
    }
  }

  async function login(payload: LoginPayload) {
    isLoading.value = true

    try {
      const loggedInUser = await loginRequest(payload)
      user.value = loggedInUser
      return loggedInUser
    } finally {
      isLoading.value = false
    }
  }

  async function logout() {
    isLoading.value = true

    try {
      await logoutRequest()
      user.value = null
    } finally {
      isLoading.value = false
    }
  }

  async function fetchUser() {
    if (isLoading.value) {
      return user.value
    }

    isLoading.value = true

    try {
      const currentUser = await fetchCurrentUser()
      user.value = currentUser
      return currentUser
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 401) {
        try {
          await refreshSession()
          const refreshedUser = await fetchCurrentUser()
          user.value = refreshedUser
          return refreshedUser
        } catch {
          user.value = null
          return null
        }
      }

      throw error
    } finally {
      isInitialized.value = true
      isLoading.value = false
    }
  }

  function clearUser() {
    user.value = null
    isInitialized.value = true
  }

  return {
    clearUser,
    fetchUser,
    getErrorMessage,
    isAuthenticated,
    isInitialized,
    isLoading,
    login,
    logout,
    register,
    user,
  }
})

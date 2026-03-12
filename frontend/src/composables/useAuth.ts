import { storeToRefs } from 'pinia'

import { useAuthStore } from '@/stores/auth'

export function useAuth() {
  const authStore = useAuthStore()
  const { isAuthenticated, isInitialized, isLoading, user } = storeToRefs(authStore)

  return {
    ...authStore,
    isAuthenticated,
    isInitialized,
    isLoading,
    user,
  }
}

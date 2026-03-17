import axios from 'axios'
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { getSubscriptionSummary, type SubscriptionSummary, type UsageMetric } from '@/services/subscription'

function getErrorMessage(error: unknown) {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail

    if (typeof detail === 'string' && detail.trim().length > 0) {
      return detail
    }
  }

  return 'Something went wrong. Please try again.'
}

export const useSubscriptionStore = defineStore('subscription', () => {
  const summary = ref<SubscriptionSummary | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const planName = computed(() => summary.value?.plan.name ?? null)
  const maxPagesPerStory = computed(() => summary.value?.plan.max_pages_per_story ?? null)

  function metric(usageType: string): UsageMetric | null {
    return summary.value?.usage[usageType] ?? null
  }

  async function fetchSummary() {
    isLoading.value = true
    error.value = null

    try {
      summary.value = await getSubscriptionSummary()
      return summary.value
    } catch (e) {
      error.value = getErrorMessage(e)
      throw e
    } finally {
      isLoading.value = false
    }
  }

  function reset() {
    summary.value = null
    error.value = null
    isLoading.value = false
  }

  return {
    error,
    fetchSummary,
    isLoading,
    maxPagesPerStory,
    metric,
    planName,
    reset,
    summary,
  }
})

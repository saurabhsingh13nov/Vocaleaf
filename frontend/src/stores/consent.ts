import axios from 'axios'
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  acceptConsents,
  getConsentStatus,
  type ConsentStatusItem,
  type ConsentStatusResponse,
  type ConsentType,
} from '@/services/consents'

function getErrorMessage(error: unknown) {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail

    if (typeof detail === 'string' && detail.trim().length > 0) {
      return detail
    }
  }

  return 'Something went wrong. Please try again.'
}

export const useConsentStore = defineStore('consent', () => {
  const status = ref<ConsentStatusResponse | null>(null)
  const isLoading = ref(false)
  const isSaving = ref(false)
  const error = ref<string | null>(null)

  const requiresLegalConsent = computed(() => status.value?.requires_legal_consent ?? false)
  const hasVoiceCloningConsent = computed(() => status.value?.has_voice_cloning_consent ?? false)

  function itemFor(consentType: ConsentType): ConsentStatusItem | null {
    return status.value?.items.find((item) => item.consent_type === consentType) ?? null
  }

  function requiredVersionFor(consentType: ConsentType): string | null {
    return itemFor(consentType)?.required_version ?? null
  }

  async function fetchStatus() {
    isLoading.value = true
    error.value = null

    try {
      status.value = await getConsentStatus()
      return status.value
    } catch (e) {
      error.value = getErrorMessage(e)
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function acceptLegalConsents() {
    const termsVersion = requiredVersionFor('terms_of_service')
    const privacyVersion = requiredVersionFor('privacy_policy')
    if (!termsVersion || !privacyVersion) {
      throw new Error('Legal consent versions are not available.')
    }

    isSaving.value = true
    error.value = null
    try {
      status.value = await acceptConsents([
        { consent_type: 'terms_of_service', accepted_version: termsVersion },
        { consent_type: 'privacy_policy', accepted_version: privacyVersion },
      ])
      return status.value
    } catch (e) {
      error.value = getErrorMessage(e)
      throw e
    } finally {
      isSaving.value = false
    }
  }

  async function acceptVoiceCloningConsent() {
    const version = requiredVersionFor('voice_cloning')
    if (!version) {
      throw new Error('Voice consent version is not available.')
    }

    isSaving.value = true
    error.value = null
    try {
      status.value = await acceptConsents([
        { consent_type: 'voice_cloning', accepted_version: version },
      ])
      return status.value
    } catch (e) {
      error.value = getErrorMessage(e)
      throw e
    } finally {
      isSaving.value = false
    }
  }

  function reset() {
    status.value = null
    error.value = null
    isLoading.value = false
    isSaving.value = false
  }

  return {
    acceptLegalConsents,
    acceptVoiceCloningConsent,
    error,
    fetchStatus,
    hasVoiceCloningConsent,
    isLoading,
    isSaving,
    itemFor,
    requiredVersionFor,
    requiresLegalConsent,
    reset,
    status,
  }
})

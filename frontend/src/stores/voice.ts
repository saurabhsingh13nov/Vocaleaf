import axios from 'axios'
import { ref } from 'vue'
import { defineStore } from 'pinia'

import {
  cloneVoiceProfile as cloneVoiceProfileRequest,
  confirmVoiceSampleUpload,
  createVoiceProfile as createVoiceProfileRequest,
  deleteVoiceProfile as deleteVoiceProfileRequest,
  deleteVoiceSample as deleteVoiceSampleRequest,
  getVoiceProfile as getVoiceProfileRequest,
  getVoiceProfiles,
  normalizeVoiceSampleMimeType,
  requestVoiceSampleUpload,
  uploadVoiceSampleFile,
  type CreateVoiceProfilePayload,
  type VoiceProfile,
  type VoiceSample,
} from '@/services/voice'
import { useSubscriptionStore } from '@/stores/subscription'

function getErrorMessage(error: unknown) {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail

    if (typeof detail === 'string' && detail.trim().length > 0) {
      return detail
    }
  }

  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message
  }

  return 'Something went wrong. Please try again.'
}

interface UploadVoiceSampleInput {
  file: Blob
  mimeType: string
  fileSizeBytes: number
  durationSeconds: number
}

const PROFILE_POLL_INTERVAL_MS = 5000

export const useVoiceStore = defineStore('voice', () => {
  const subscriptionStore = useSubscriptionStore()
  const profiles = ref<VoiceProfile[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const cloningProfileIds = ref<string[]>([])
  const pollingTimers = new Map<string, number>()

  function mergeProfile(profile: VoiceProfile) {
    const index = profiles.value.findIndex((entry) => entry.id === profile.id)

    if (index === -1) {
      profiles.value.unshift(profile)
      return
    }

    profiles.value.splice(index, 1, profile)
  }

  async function fetchProfiles() {
    isLoading.value = true
    error.value = null

    try {
      profiles.value = await getVoiceProfiles()
      return profiles.value
    } catch (e) {
      error.value = 'Failed to load voice profiles.'
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function createProfile(payload: CreateVoiceProfilePayload) {
    isLoading.value = true
    error.value = null

    try {
      const profile = await createVoiceProfileRequest(payload)
      mergeProfile(profile)
      return profile
    } catch (e) {
      error.value = getErrorMessage(e)
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function uploadSample(profileId: string, payload: UploadVoiceSampleInput) {
    isLoading.value = true
    error.value = null

    try {
      const normalizedMimeType = normalizeVoiceSampleMimeType(payload.mimeType)
      const init = await requestVoiceSampleUpload(profileId, {
        mime_type: normalizedMimeType,
        file_size_bytes: payload.fileSizeBytes,
        duration_seconds: payload.durationSeconds,
      })
      await uploadVoiceSampleFile(init.upload_url, payload.file, normalizedMimeType)
      const sample = await confirmVoiceSampleUpload(profileId, init.sample_id)
      mergeSample(profileId, sample)
      return sample
    } catch (e) {
      error.value = getErrorMessage(e)
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function deleteProfile(profileId: string) {
    isLoading.value = true
    error.value = null

    try {
      stopClonePolling(profileId)
      await deleteVoiceProfileRequest(profileId)
      profiles.value = profiles.value.filter((entry) => entry.id !== profileId)
    } catch (e) {
      error.value = getErrorMessage(e)
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function deleteSample(profileId: string, sampleId: string) {
    isLoading.value = true
    error.value = null

    try {
      await deleteVoiceSampleRequest(profileId, sampleId)
      removeSample(profileId, sampleId)
    } catch (e) {
      error.value = getErrorMessage(e)
      throw e
    } finally {
      isLoading.value = false
    }
  }

  function mergeSample(profileId: string, sample: VoiceSample) {
    const profile = profiles.value.find((entry) => entry.id === profileId)

    if (!profile) {
      return
    }

    profile.samples = [sample, ...profile.samples.filter((entry) => entry.id !== sample.id)]
  }

  function removeSample(profileId: string, sampleId: string) {
    const profile = profiles.value.find((entry) => entry.id === profileId)

    if (!profile) {
      return
    }

    profile.samples = profile.samples.filter((entry) => entry.id !== sampleId)
  }

  async function fetchProfile(profileId: string) {
    const profile = await getVoiceProfileRequest(profileId)
    mergeProfile(profile)
    return profile
  }

  function scheduleClonePoll(profileId: string) {
    stopClonePolling(profileId)

    const timerId = window.setTimeout(async () => {
      try {
        const profile = await fetchProfile(profileId)
        if (profile.status === 'processing') {
          scheduleClonePoll(profileId)
          return
        }
        if (profile.status === 'ready') {
          subscriptionStore.fetchSummary().catch(() => undefined)
        }
      } catch (e) {
        error.value = 'Failed to refresh voice profile status.'
      }

      cloningProfileIds.value = cloningProfileIds.value.filter((entry) => entry !== profileId)
      stopClonePolling(profileId)
    }, PROFILE_POLL_INTERVAL_MS)

    pollingTimers.set(profileId, timerId)
  }

  function stopClonePolling(profileId: string) {
    const timerId = pollingTimers.get(profileId)
    if (timerId !== undefined) {
      window.clearTimeout(timerId)
      pollingTimers.delete(profileId)
    }
  }

  function stopAllClonePolling() {
    for (const profileId of Array.from(pollingTimers.keys())) {
      stopClonePolling(profileId)
    }
    cloningProfileIds.value = []
  }

  function isCloningProfile(profileId: string) {
    return cloningProfileIds.value.includes(profileId)
  }

  async function cloneProfile(profileId: string) {
    isLoading.value = true
    error.value = null

    try {
      const profile = await cloneVoiceProfileRequest(profileId)
      mergeProfile(profile)
      if (profile.status === 'processing') {
        if (!cloningProfileIds.value.includes(profileId)) {
          cloningProfileIds.value = [...cloningProfileIds.value, profileId]
        }
        scheduleClonePoll(profileId)
      }
      return profile
    } catch (e) {
      error.value = getErrorMessage(e)
      throw e
    } finally {
      isLoading.value = false
    }
  }

  return {
    cloneProfile,
    cloningProfileIds,
    createProfile,
    deleteProfile,
    deleteSample,
    error,
    fetchProfile,
    fetchProfiles,
    getErrorMessage,
    isCloningProfile,
    isLoading,
    profiles,
    stopAllClonePolling,
    uploadSample,
  }
})

import axios from 'axios'
import { ref } from 'vue'
import { defineStore } from 'pinia'

import {
  confirmVoiceSampleUpload,
  createVoiceProfile as createVoiceProfileRequest,
  deleteVoiceProfile as deleteVoiceProfileRequest,
  deleteVoiceSample as deleteVoiceSampleRequest,
  getVoiceProfiles,
  normalizeVoiceSampleMimeType,
  requestVoiceSampleUpload,
  uploadVoiceSampleFile,
  type CreateVoiceProfilePayload,
  type VoiceProfile,
  type VoiceSample,
} from '@/services/voice'

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

export const useVoiceStore = defineStore('voice', () => {
  const profiles = ref<VoiceProfile[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

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
      profiles.value.unshift(profile)
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

  return {
    createProfile,
    deleteProfile,
    deleteSample,
    error,
    fetchProfiles,
    getErrorMessage,
    isLoading,
    profiles,
    uploadSample,
  }
})

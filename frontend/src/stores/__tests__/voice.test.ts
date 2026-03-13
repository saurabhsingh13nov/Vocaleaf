import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useVoiceStore } from '@/stores/voice'
import {
  cloneVoiceProfile,
  confirmVoiceSampleUpload,
  createVoiceProfile,
  deleteVoiceProfile,
  deleteVoiceSample,
  getVoiceProfile,
  getVoiceProfiles,
  requestVoiceSampleUpload,
  uploadVoiceSampleFile,
} from '@/services/voice'

vi.mock('@/services/voice', () => ({
  cloneVoiceProfile: vi.fn(),
  confirmVoiceSampleUpload: vi.fn(),
  createVoiceProfile: vi.fn(),
  deleteVoiceProfile: vi.fn(),
  deleteVoiceSample: vi.fn(),
  getAudioDurationSeconds: vi.fn(),
  getVoiceProfile: vi.fn(),
  getVoiceProfiles: vi.fn(),
  isSupportedVoiceSampleMimeType: vi.fn(() => true),
  normalizeVoiceSampleMimeType: vi.fn((mimeType: string) => mimeType.split(';', 1)[0]),
  requestVoiceSampleUpload: vi.fn(),
  uploadVoiceSampleFile: vi.fn(),
}))

const mockedCloneVoiceProfile = vi.mocked(cloneVoiceProfile)
const mockedGetVoiceProfiles = vi.mocked(getVoiceProfiles)
const mockedGetVoiceProfile = vi.mocked(getVoiceProfile)
const mockedCreateVoiceProfile = vi.mocked(createVoiceProfile)
const mockedDeleteVoiceProfile = vi.mocked(deleteVoiceProfile)
const mockedDeleteVoiceSample = vi.mocked(deleteVoiceSample)
const mockedRequestVoiceSampleUpload = vi.mocked(requestVoiceSampleUpload)
const mockedUploadVoiceSampleFile = vi.mocked(uploadVoiceSampleFile)
const mockedConfirmVoiceSampleUpload = vi.mocked(confirmVoiceSampleUpload)

describe('useVoiceStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.runOnlyPendingTimers()
    vi.useRealTimers()
  })

  it('stores fetched voice profiles', async () => {
    mockedGetVoiceProfiles.mockResolvedValue([
      {
        id: 'profile-1',
        user_id: 'user-1',
        display_name: 'Bedtime Voice',
        status: 'pending',
        consent_confirmed: true,
        default_for_user: false,
        created_at: '2026-03-13T20:00:00Z',
        updated_at: '2026-03-13T20:00:00Z',
        samples: [],
      },
    ])
    const store = useVoiceStore()

    await store.fetchProfiles()

    expect(store.profiles).toHaveLength(1)
    expect(store.profiles[0]?.display_name).toBe('Bedtime Voice')
  })

  it('creates a voice profile and prepends it to state', async () => {
    mockedCreateVoiceProfile.mockResolvedValue({
      id: 'profile-1',
      user_id: 'user-1',
      display_name: 'Recorded Voice',
      status: 'pending',
      consent_confirmed: true,
      default_for_user: true,
      created_at: '2026-03-13T20:00:00Z',
      updated_at: '2026-03-13T20:00:00Z',
      samples: [],
    })
    const store = useVoiceStore()

    await store.createProfile({
      display_name: 'Recorded Voice',
      consent_confirmed: true,
      default_for_user: true,
    })

    expect(mockedCreateVoiceProfile).toHaveBeenCalledWith({
      display_name: 'Recorded Voice',
      consent_confirmed: true,
      default_for_user: true,
    })
    expect(store.profiles[0]?.default_for_user).toBe(true)
  })

  it('uploads a sample through signed URL flow and merges it into the profile', async () => {
    mockedRequestVoiceSampleUpload.mockResolvedValue({
      sample_id: 'sample-1',
      asset_id: 'asset-1',
      upload_url: 'https://upload.example',
      expires_at: '2026-03-13T21:00:00Z',
    })
    mockedUploadVoiceSampleFile.mockResolvedValue(undefined)
    mockedConfirmVoiceSampleUpload.mockResolvedValue({
      id: 'sample-1',
      asset_id: 'asset-1',
      duration_seconds: 7.5,
      status: 'uploaded',
      created_at: '2026-03-13T20:30:00Z',
    })
    const store = useVoiceStore()
    store.profiles = [
      {
        id: 'profile-1',
        user_id: 'user-1',
        display_name: 'Bedtime Voice',
        status: 'pending',
        consent_confirmed: true,
        default_for_user: false,
        created_at: '2026-03-13T20:00:00Z',
        updated_at: '2026-03-13T20:00:00Z',
        samples: [],
      },
    ]

    const file = new Blob(['voice-sample'], { type: 'audio/webm' })
    await store.uploadSample('profile-1', {
      file,
      mimeType: 'audio/webm',
      fileSizeBytes: file.size,
      durationSeconds: 7.5,
    })

    expect(mockedRequestVoiceSampleUpload).toHaveBeenCalledWith('profile-1', {
      mime_type: 'audio/webm',
      file_size_bytes: file.size,
      duration_seconds: 7.5,
    })
    expect(mockedUploadVoiceSampleFile).toHaveBeenCalledWith(
      'https://upload.example',
      file,
      'audio/webm',
    )
    expect(mockedConfirmVoiceSampleUpload).toHaveBeenCalledWith('profile-1', 'sample-1')
    expect(store.profiles[0]?.samples[0]?.id).toBe('sample-1')
  })

  it('deletes a profile and removes it from local state', async () => {
    mockedDeleteVoiceProfile.mockResolvedValue(undefined)
    const store = useVoiceStore()
    store.profiles = [
      {
        id: 'profile-1',
        user_id: 'user-1',
        display_name: 'Bedtime Voice',
        status: 'pending',
        consent_confirmed: true,
        default_for_user: false,
        created_at: '2026-03-13T20:00:00Z',
        updated_at: '2026-03-13T20:00:00Z',
        samples: [],
      },
    ]

    await store.deleteProfile('profile-1')

    expect(mockedDeleteVoiceProfile).toHaveBeenCalledWith('profile-1')
    expect(store.profiles).toHaveLength(0)
  })

  it('deletes a sample and removes it from local state', async () => {
    mockedDeleteVoiceSample.mockResolvedValue(undefined)
    const store = useVoiceStore()
    store.profiles = [
      {
        id: 'profile-1',
        user_id: 'user-1',
        display_name: 'Bedtime Voice',
        status: 'pending',
        consent_confirmed: true,
        default_for_user: false,
        created_at: '2026-03-13T20:00:00Z',
        updated_at: '2026-03-13T20:00:00Z',
        samples: [
          {
            id: 'sample-1',
            asset_id: 'asset-1',
            duration_seconds: 3.7,
            status: 'uploaded',
            created_at: '2026-03-13T20:10:00Z',
          },
        ],
      },
    ]

    await store.deleteSample('profile-1', 'sample-1')

    expect(mockedDeleteVoiceSample).toHaveBeenCalledWith('profile-1', 'sample-1')
    expect(store.profiles[0]?.samples).toHaveLength(0)
  })

  it('starts polling after clone and stores the refreshed profile', async () => {
    mockedCloneVoiceProfile.mockResolvedValue({
      id: 'profile-1',
      user_id: 'user-1',
      display_name: 'Bedtime Voice',
      status: 'processing',
      consent_confirmed: true,
      default_for_user: false,
      created_at: '2026-03-13T20:00:00Z',
      updated_at: '2026-03-13T20:05:00Z',
      samples: [
        {
          id: 'sample-1',
          asset_id: 'asset-1',
          duration_seconds: 3.7,
          status: 'uploaded',
          created_at: '2026-03-13T20:10:00Z',
        },
      ],
    })
    mockedGetVoiceProfile.mockResolvedValue({
      id: 'profile-1',
      user_id: 'user-1',
      display_name: 'Bedtime Voice',
      status: 'ready',
      consent_confirmed: true,
      default_for_user: false,
      created_at: '2026-03-13T20:00:00Z',
      updated_at: '2026-03-13T20:10:00Z',
      samples: [
        {
          id: 'sample-1',
          asset_id: 'asset-1',
          duration_seconds: 3.7,
          status: 'accepted',
          created_at: '2026-03-13T20:10:00Z',
        },
      ],
    })
    const store = useVoiceStore()
    store.profiles = [
      {
        id: 'profile-1',
        user_id: 'user-1',
        display_name: 'Bedtime Voice',
        status: 'pending',
        consent_confirmed: true,
        default_for_user: false,
        created_at: '2026-03-13T20:00:00Z',
        updated_at: '2026-03-13T20:00:00Z',
        samples: [
          {
            id: 'sample-1',
            asset_id: 'asset-1',
            duration_seconds: 3.7,
            status: 'uploaded',
            created_at: '2026-03-13T20:10:00Z',
          },
        ],
      },
    ]

    await store.cloneProfile('profile-1')
    expect(mockedCloneVoiceProfile).toHaveBeenCalledWith('profile-1')
    expect(store.profiles[0]?.status).toBe('processing')

    await vi.advanceTimersByTimeAsync(5000)

    expect(mockedGetVoiceProfile).toHaveBeenCalledWith('profile-1')
    expect(store.profiles[0]?.status).toBe('ready')
    expect(store.isCloningProfile('profile-1')).toBe(false)
  })
})

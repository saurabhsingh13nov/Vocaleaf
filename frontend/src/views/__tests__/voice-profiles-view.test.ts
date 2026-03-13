import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import VoiceProfilesView from '@/views/VoiceProfilesView.vue'
import {
  cloneVoiceProfile,
  createVoiceProfile,
  deleteVoiceProfile,
  deleteVoiceSample,
  getVoiceProfile,
  getVoiceProfiles,
} from '@/services/voice'

vi.mock('vue-router', async () => {
  const actual = await vi.importActual<typeof import('vue-router')>('vue-router')
  return {
    ...actual,
    RouterLink: {
      template: '<a><slot /></a>',
      props: ['to'],
    },
  }
})

vi.mock('@/services/voice', () => ({
  cloneVoiceProfile: vi.fn(),
  confirmVoiceSampleUpload: vi.fn(),
  createVoiceProfile: vi.fn(),
  deleteVoiceProfile: vi.fn(),
  deleteVoiceSample: vi.fn(),
  getAudioDurationSeconds: vi.fn(),
  getVoiceProfile: vi.fn(),
  getVoiceProfiles: vi.fn().mockResolvedValue([]),
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

describe('VoiceProfilesView', () => {
  function mountView() {
    return mount(VoiceProfilesView, {
      global: {
        stubs: {
          RouterLink: true,
        },
      },
    })
  }

  beforeEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
    setActivePinia(createPinia())
    mockedGetVoiceProfiles.mockResolvedValue([])
    mockedGetVoiceProfile.mockResolvedValue({
      id: 'profile-1',
      user_id: 'user-1',
      display_name: 'Quiet Story Voice',
      status: 'ready',
      consent_confirmed: true,
      default_for_user: false,
      created_at: '2026-03-13T20:00:00Z',
      updated_at: '2026-03-13T20:00:00Z',
      samples: [],
    })
  })

  it('renders the empty state when no profiles exist', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('No voice profiles yet')
  })

  it('requires consent before creating a profile', async () => {
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('input[name="display_name"]').setValue('Quiet Story Voice')
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(mockedCreateVoiceProfile).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Consent is required before creating a voice profile')
  })

  it('creates a profile when consent is checked', async () => {
    mockedCreateVoiceProfile.mockResolvedValue({
      id: 'profile-1',
      user_id: 'user-1',
      display_name: 'Quiet Story Voice',
      status: 'pending',
      consent_confirmed: true,
      default_for_user: false,
      created_at: '2026-03-13T20:00:00Z',
      updated_at: '2026-03-13T20:00:00Z',
      samples: [],
    })

    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('input[name="display_name"]').setValue('Quiet Story Voice')
    await wrapper.get('input[type="checkbox"]').setValue(true)
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(mockedCreateVoiceProfile).toHaveBeenCalledWith({
      display_name: 'Quiet Story Voice',
      consent_confirmed: true,
      default_for_user: false,
    })
    expect(wrapper.text()).toContain('Quiet Story Voice')
  })

  it('deletes a profile after confirmation', async () => {
    mockedGetVoiceProfiles.mockResolvedValue([
      {
        id: 'profile-1',
        user_id: 'user-1',
        display_name: 'Quiet Story Voice',
        status: 'pending',
        consent_confirmed: true,
        default_for_user: false,
        created_at: '2026-03-13T20:00:00Z',
        updated_at: '2026-03-13T20:00:00Z',
        samples: [],
      },
    ])
    mockedDeleteVoiceProfile.mockResolvedValue(undefined)

    const wrapper = mountView()
    await flushPromises()

    const deleteButton = wrapper.findAll('button').find((entry) => entry.text() === 'Delete')
    expect(deleteButton).toBeTruthy()
    await deleteButton!.trigger('click')
    await flushPromises()

    const confirmButton = document.body.querySelector('[data-testid="confirm-modal-confirm"]') as HTMLButtonElement | null
    expect(confirmButton?.textContent).toBe('Delete profile')
    confirmButton?.click()
    await flushPromises()

    expect(mockedDeleteVoiceProfile).toHaveBeenCalledWith('profile-1')
    expect(wrapper.text()).not.toContain('Quiet Story Voice')
  })

  it('deletes a sample after confirmation', async () => {
    mockedGetVoiceProfiles.mockResolvedValue([
      {
        id: 'profile-1',
        user_id: 'user-1',
        display_name: 'Quiet Story Voice',
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
            status: 'pending',
            created_at: '2026-03-13T20:10:00Z',
          },
        ],
      },
    ])
    mockedDeleteVoiceSample.mockResolvedValue(undefined)

    const wrapper = mountView()
    await flushPromises()

    const deleteButtons = wrapper.findAll('button').filter((entry) => entry.text() === 'Delete')
    expect(deleteButtons.length).toBeGreaterThan(1)
    await deleteButtons[1]!.trigger('click')
    await flushPromises()

    const confirmButton = document.body.querySelector('[data-testid="confirm-modal-confirm"]') as HTMLButtonElement | null
    expect(confirmButton?.textContent).toBe('Delete sample')
    confirmButton?.click()
    await flushPromises()

    expect(mockedDeleteVoiceSample).toHaveBeenCalledWith('profile-1', 'sample-1')
    expect(wrapper.text()).not.toContain('3.7 sec')
  })

  it('shows awaiting clone for pending profiles that already have samples', async () => {
    mockedGetVoiceProfiles.mockResolvedValue([
      {
        id: 'profile-1',
        user_id: 'user-1',
        display_name: 'Quiet Story Voice',
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
    ])

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('Awaiting clone')
    expect(wrapper.text()).not.toContain('PENDING')
  })

  it('shows add samples for pending profiles with no samples yet', async () => {
    mockedGetVoiceProfiles.mockResolvedValue([
      {
        id: 'profile-1',
        user_id: 'user-1',
        display_name: 'Quiet Story Voice',
        status: 'pending',
        consent_confirmed: true,
        default_for_user: false,
        created_at: '2026-03-13T20:00:00Z',
        updated_at: '2026-03-13T20:00:00Z',
        samples: [],
      },
    ])

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('Add samples')
    expect(wrapper.text()).not.toContain('PENDING')
  })

  it('shows a clone button when a profile has uploaded samples', async () => {
    mockedGetVoiceProfiles.mockResolvedValue([
      {
        id: 'profile-1',
        user_id: 'user-1',
        display_name: 'Quiet Story Voice',
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
    ])
    mockedCloneVoiceProfile.mockResolvedValue({
      id: 'profile-1',
      user_id: 'user-1',
      display_name: 'Quiet Story Voice',
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

    const wrapper = mountView()
    await flushPromises()

    const cloneButton = wrapper.findAll('button').find((entry) => entry.text() === 'Clone Voice')
    expect(cloneButton).toBeTruthy()
    await cloneButton!.trigger('click')
    await flushPromises()

    expect(mockedCloneVoiceProfile).toHaveBeenCalledWith('profile-1')
    expect(wrapper.text()).toContain('Cloning...')
  })
})

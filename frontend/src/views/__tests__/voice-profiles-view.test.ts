import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import VoiceProfilesView from '@/views/VoiceProfilesView.vue'
import { getConsentStatus, acceptConsents } from '@/services/consents'
import { getSubscriptionSummary } from '@/services/subscription'
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

vi.mock('@/services/consents', () => ({
  acceptConsents: vi.fn(),
  getConsentStatus: vi.fn(),
}))

vi.mock('@/services/subscription', () => ({
  getSubscriptionSummary: vi.fn(),
}))

const mockedAcceptConsents = vi.mocked(acceptConsents)
const mockedCloneVoiceProfile = vi.mocked(cloneVoiceProfile)
const mockedGetConsentStatus = vi.mocked(getConsentStatus)
const mockedGetVoiceProfiles = vi.mocked(getVoiceProfiles)
const mockedGetVoiceProfile = vi.mocked(getVoiceProfile)
const mockedCreateVoiceProfile = vi.mocked(createVoiceProfile)
const mockedDeleteVoiceProfile = vi.mocked(deleteVoiceProfile)
const mockedDeleteVoiceSample = vi.mocked(deleteVoiceSample)
const mockedGetSubscriptionSummary = vi.mocked(getSubscriptionSummary)

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
    mockedAcceptConsents.mockResolvedValue({
      items: [
        {
          consent_type: 'terms_of_service',
          required_version: '2026-03-16',
          accepted_version: '2026-03-16',
          accepted_at: '2026-03-13T20:00:00Z',
          is_current: true,
        },
        {
          consent_type: 'privacy_policy',
          required_version: '2026-03-16',
          accepted_version: '2026-03-16',
          accepted_at: '2026-03-13T20:00:00Z',
          is_current: true,
        },
        {
          consent_type: 'voice_cloning',
          required_version: '2026-03-16',
          accepted_version: '2026-03-16',
          accepted_at: '2026-03-13T20:00:00Z',
          is_current: true,
        },
      ],
      requires_legal_consent: false,
      has_voice_cloning_consent: true,
    })
    mockedGetConsentStatus.mockResolvedValue({
      items: [
        {
          consent_type: 'terms_of_service',
          required_version: '2026-03-16',
          accepted_version: '2026-03-16',
          accepted_at: '2026-03-13T20:00:00Z',
          is_current: true,
        },
        {
          consent_type: 'privacy_policy',
          required_version: '2026-03-16',
          accepted_version: '2026-03-16',
          accepted_at: '2026-03-13T20:00:00Z',
          is_current: true,
        },
        {
          consent_type: 'voice_cloning',
          required_version: '2026-03-16',
          accepted_version: '2026-03-16',
          accepted_at: '2026-03-13T20:00:00Z',
          is_current: true,
        },
      ],
      requires_legal_consent: false,
      has_voice_cloning_consent: true,
    })
    mockedGetSubscriptionSummary.mockResolvedValue({
      id: 'subscription-1',
      status: 'active',
      current_period_start: '2026-03-01T00:00:00Z',
      current_period_end: '2026-03-31T00:00:00Z',
      plan: {
        id: 'plan-1',
        code: 'free',
        name: 'free',
        monthly_story_limit: 3,
        max_pages_per_story: 6,
        image_quality_mode: 'standard',
        voice_clone_limit: 1,
        monthly_audio_chars_limit: 15000,
        price_cents: 0,
      },
      usage: {
        stories_created: { used: 0, limit: 3, remaining: 3, unit: 'story' },
        voice_clones_created: { used: 0, limit: 1, remaining: 1, unit: 'voice_clone' },
        audio_chars_synthesized: { used: 0, limit: 15000, remaining: 15000, unit: 'character' },
        images_generated: { used: 0, limit: null, remaining: null, unit: 'page_image' },
      },
    })
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

  it('renders the updated voice guidance steps', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('Record clearly')
    expect(wrapper.text()).toContain('Add a few samples')
    expect(wrapper.text()).toContain('Clone when ready')
    expect(wrapper.text()).not.toContain('Phase 8 flow')
  })

  it('creates a profile without requiring consent first', async () => {
    mockedCreateVoiceProfile.mockResolvedValue({
      id: 'profile-1',
      user_id: 'user-1',
      display_name: 'Quiet Story Voice',
      status: 'pending',
      consent_confirmed: false,
      default_for_user: false,
      created_at: '2026-03-13T20:00:00Z',
      updated_at: '2026-03-13T20:00:00Z',
      samples: [],
    })

    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('input[name="display_name"]').setValue('Quiet Story Voice')
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(mockedCreateVoiceProfile).toHaveBeenCalledWith({
      display_name: 'Quiet Story Voice',
      default_for_user: false,
    })
    expect(wrapper.text()).toContain('Quiet Story Voice')
  })

  it('creates a profile with default voice selection', async () => {
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
      default_for_user: true,
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

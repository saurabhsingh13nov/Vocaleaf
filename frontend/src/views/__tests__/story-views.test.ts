import { computed, nextTick, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { User } from '@/services/auth'
import DashboardView from '@/views/DashboardView.vue'
import StoryCreateView from '@/views/StoryCreateView.vue'
import StoryDetailView from '@/views/StoryDetailView.vue'
import { useAuth } from '@/composables/useAuth'
import { createStory, deleteStory, getStory, getStories } from '@/services/stories'
import { getChildren } from '@/services/children'
import { getVoiceProfiles } from '@/services/voice'

const pushMock = vi.fn()
const routeRef = ref({ params: { storyId: 'story-1' } })
const useAuthMock = vi.mocked(useAuth)

vi.mock('@/composables/useAuth', () => ({
  useAuth: vi.fn(),
}))

vi.mock('vue-router', async () => {
  const actual = await vi.importActual<typeof import('vue-router')>('vue-router')
  return {
    ...actual,
    RouterLink: {
      template: '<a><slot /></a>',
      props: ['to'],
    },
    useRouter: () => ({ push: pushMock }),
    useRoute: () => routeRef.value,
  }
})

vi.mock('@/services/stories', () => ({
  createStory: vi.fn(),
  deleteStory: vi.fn(),
  getStory: vi.fn(),
  getStories: vi.fn().mockResolvedValue([]),
}))

vi.mock('@/services/children', () => ({
  getChildren: vi.fn().mockResolvedValue([]),
  createChild: vi.fn(),
  updateChild: vi.fn(),
  deleteChild: vi.fn(),
}))

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

const mockedCreateStory = vi.mocked(createStory)
const mockedDeleteStory = vi.mocked(deleteStory)
const mockedGetStory = vi.mocked(getStory)
const mockedGetStories = vi.mocked(getStories)
const mockedGetChildren = vi.mocked(getChildren)
const mockedGetVoiceProfiles = vi.mocked(getVoiceProfiles)

const sampleUser: User = {
  id: 'cc4e3be9-0e56-4d1b-9128-655ddcf06092',
  primary_email: 'parent@example.com',
  full_name: 'Parent Reader',
  avatar_url: null,
  status: 'active',
  email_verified_at: null,
  created_at: '2026-03-11T20:00:00Z',
}

function makeAuthState() {
  const user = ref<User | null>(sampleUser)

  return {
    clearUser: vi.fn(),
    fetchUser: vi.fn(),
    getErrorMessage: vi.fn(() => 'Friendly error message'),
    isAuthenticated: computed(() => user.value !== null),
    isInitialized: ref(true),
    isLoading: ref(false),
    link: vi.fn(),
    linkWithGoogle: vi.fn(),
    login: vi.fn(),
    loginWithGoogle: vi.fn(),
    logout: vi.fn(),
    register: vi.fn(),
    user,
  } as unknown as ReturnType<typeof useAuth>
}

describe('story views', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
    setActivePinia(createPinia())
    routeRef.value = { params: { storyId: 'story-1' } }
    useAuthMock.mockReturnValue(makeAuthState())
    mockedGetStories.mockResolvedValue([])
    mockedGetChildren.mockResolvedValue([
      {
        id: 'child-1',
        user_id: 'user-1',
        name: 'Luna',
        age: 5,
        favorite_themes: null,
        favorite_characters: null,
        bedtime_preferences: null,
        created_at: '2026-03-13T20:00:00Z',
        updated_at: '2026-03-13T20:00:00Z',
      },
    ])
    mockedGetVoiceProfiles.mockResolvedValue([
      {
        id: 'voice-1',
        user_id: 'user-1',
        display_name: 'Bedtime Voice',
        status: 'ready',
        consent_confirmed: true,
        default_for_user: false,
        created_at: '2026-03-13T20:00:00Z',
        updated_at: '2026-03-13T20:00:00Z',
        samples: [],
      },
    ])
  })

  it('submits the create story form and navigates to detail', async () => {
    mockedCreateStory.mockResolvedValue({
      id: 'story-1',
      user_id: 'user-1',
      child_id: 'child-1',
      voice_profile_id: 'voice-1',
      title: null,
      prompt: 'A lantern walk',
      theme: 'Bedtime',
      status: 'generating',
      target_page_count: 7,
      reading_level: 'Preschool',
      language: 'en',
      art_style: 'Dreamy',
      latest_error_message: null,
      created_at: '2026-03-13T20:00:00Z',
      updated_at: '2026-03-13T20:00:00Z',
      pages: [],
    })

    const wrapper = mount(StoryCreateView, {
      global: {
        stubs: {
          RouterLink: true,
        },
      },
    })
    await flushPromises()

    await wrapper.get('select[name="child_id"]').setValue('child-1')
    await wrapper.get('textarea[name="prompt"]').setValue('A lantern walk')
    const bedtimeButton = wrapper.findAll('button').find((entry) => entry.text() === 'Bedtime')
    await bedtimeButton?.trigger('click')
    const sevenPagesButton = wrapper.findAll('button').find((entry) => entry.text() === '7')
    await sevenPagesButton?.trigger('click')
    await wrapper.get('select[name="reading_level"]').setValue('Preschool')
    await wrapper.get('select[name="voice_profile_id"]').setValue('voice-1')
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(mockedCreateStory).toHaveBeenCalledWith(
      expect.objectContaining({
        child_id: 'child-1',
        prompt: 'A lantern walk',
        theme: 'Bedtime',
        target_page_count: 7,
        voice_profile_id: 'voice-1',
      }),
    )
    expect(pushMock).toHaveBeenCalledWith({ name: 'story-detail', params: { storyId: 'story-1' } })
  })

  it('renders generated story pages in the detail view', async () => {
    mockedGetStory.mockResolvedValue({
      id: 'story-1',
      user_id: 'user-1',
      child_id: 'child-1',
      voice_profile_id: null,
      title: 'Lantern Walk',
      prompt: 'A lantern walk',
      theme: 'Bedtime',
      status: 'ready',
      target_page_count: 6,
      reading_level: 'Preschool',
      language: 'en',
      art_style: 'Dreamy',
      latest_error_message: null,
      created_at: '2026-03-13T20:00:00Z',
      updated_at: '2026-03-13T20:02:00Z',
      pages: [
        {
          id: 'page-1',
          page_number: 1,
          text_content: 'The lantern glowed softly beneath the moon.',
          image_prompt: 'A lantern beneath the moon',
          continuity_notes: 'Keep the lantern warm and golden.',
          status: 'text_ready',
          image_asset_id: null,
          audio_asset_id: null,
          duration_ms: null,
          created_at: '2026-03-13T20:01:00Z',
          updated_at: '2026-03-13T20:02:00Z',
        },
      ],
    })

    const wrapper = mount(StoryDetailView, {
      global: {
        stubs: {
          RouterLink: true,
        },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Lantern Walk')
    expect(wrapper.text()).toContain('The lantern glowed softly beneath the moon.')
    expect(wrapper.text()).toContain('Illustrating')
  })

  it('renders a ready story as the dashboard hero', async () => {
    mockedGetStories.mockResolvedValue([
      {
        id: 'story-1',
        child_id: 'child-1',
        title: 'Lantern Walk',
        theme: 'Bedtime',
        status: 'ready',
        target_page_count: 6,
        art_style: 'Dreamy',
        latest_error_message: null,
        created_at: '2026-03-13T20:00:00Z',
        updated_at: '2026-03-13T20:02:00Z',
      },
    ])

    const wrapper = mount(DashboardView, {
      global: {
        stubs: {
          RouterLink: {
            template: '<a><slot /></a>',
            props: ['to'],
          },
        },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Welcome back, Parent')
    expect(wrapper.text()).toContain('Lantern Walk')
    expect(wrapper.text()).toContain('Read story')
    expect(wrapper.text()).toContain('Story setup')
    expect(wrapper.text()).not.toContain('Cookie-backed auth')
  })

  it('prioritizes a generating story in the dashboard hero', async () => {
    mockedGetStories.mockResolvedValue([
      {
        id: 'story-1',
        child_id: 'child-1',
        title: 'Moonlight Rescue',
        theme: 'Adventure',
        status: 'generating',
        target_page_count: 6,
        art_style: 'Dreamy',
        latest_error_message: null,
        created_at: '2026-03-13T20:00:00Z',
        updated_at: '2026-03-13T20:05:00Z',
      },
      {
        id: 'story-2',
        child_id: 'child-1',
        title: 'Lantern Walk',
        theme: 'Bedtime',
        status: 'ready',
        target_page_count: 6,
        art_style: 'Dreamy',
        latest_error_message: null,
        created_at: '2026-03-13T19:00:00Z',
        updated_at: '2026-03-13T19:05:00Z',
      },
    ])

    const wrapper = mount(DashboardView, {
      global: {
        stubs: {
          RouterLink: {
            template: '<a><slot /></a>',
            props: ['to'],
          },
        },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Moonlight Rescue')
    expect(wrapper.get('[data-testid="dashboard-hero-primary"]').text()).toBe('Continue story')

    await wrapper.get('[data-testid="dashboard-hero-primary"]').trigger('click')
    await flushPromises()

    expect(pushMock).toHaveBeenCalledWith({ name: 'story-detail', params: { storyId: 'story-1' } })
  })

  it('deletes a failed story from the dashboard after confirmation', async () => {
    mockedGetStories.mockResolvedValue([
      {
        id: 'story-1',
        child_id: 'child-1',
        title: 'Broken Story',
        theme: 'Bedtime',
        status: 'failed',
        target_page_count: 6,
        art_style: 'Dreamy',
        latest_error_message: 'Worker failed',
        created_at: '2026-03-13T20:00:00Z',
        updated_at: '2026-03-13T20:02:00Z',
      },
    ])
    mockedDeleteStory.mockResolvedValue(undefined)

    const wrapper = mount(DashboardView, {
      global: {
        stubs: {
          RouterLink: {
            template: '<a><slot /></a>',
            props: ['to'],
          },
        },
      },
    })
    await flushPromises()

    await wrapper.get('button[aria-label="Delete story"]').trigger('click')
    await nextTick()

    const confirmButton = document.body.querySelector('[data-testid="confirm-modal-confirm"]') as HTMLButtonElement | null
    expect(confirmButton?.textContent).toBe('Delete story')
    confirmButton?.click()
    await flushPromises()

    expect(mockedDeleteStory).toHaveBeenCalledWith('story-1')
  })

  it('deletes a ready story from the dashboard after confirmation', async () => {
    mockedGetStories.mockResolvedValue([
      {
        id: 'story-1',
        child_id: 'child-1',
        title: 'Ready Story',
        theme: 'Bedtime',
        status: 'ready',
        target_page_count: 6,
        art_style: 'Dreamy',
        latest_error_message: null,
        created_at: '2026-03-13T20:00:00Z',
        updated_at: '2026-03-13T20:02:00Z',
      },
    ])
    mockedDeleteStory.mockResolvedValue(undefined)

    const wrapper = mount(DashboardView, {
      global: {
        stubs: {
          RouterLink: {
            template: '<a><slot /></a>',
            props: ['to'],
          },
        },
      },
    })
    await flushPromises()

    await wrapper.get('button[aria-label="Delete story"]').trigger('click')
    await nextTick()

    expect(wrapper.text()).toContain('Ready Story')
    const confirmButton = document.body.querySelector('[data-testid="confirm-modal-confirm"]') as HTMLButtonElement | null
    expect(confirmButton?.textContent).toBe('Delete story')
    confirmButton?.click()
    await flushPromises()

    expect(mockedDeleteStory).toHaveBeenCalledWith('story-1')
  })

  it('deletes a failed story from the detail view and returns to dashboard', async () => {
    mockedGetStory.mockResolvedValue({
      id: 'story-1',
      user_id: 'user-1',
      child_id: 'child-1',
      voice_profile_id: null,
      title: 'Broken Story',
      prompt: 'A lantern walk',
      theme: 'Bedtime',
      status: 'failed',
      target_page_count: 6,
      reading_level: 'Preschool',
      language: 'en',
      art_style: 'Dreamy',
      latest_error_message: 'Anthropic authentication failed.',
      created_at: '2026-03-13T20:00:00Z',
      updated_at: '2026-03-13T20:02:00Z',
      pages: [],
    })
    mockedDeleteStory.mockResolvedValue(undefined)

    const wrapper = mount(StoryDetailView, {
      global: {
        stubs: {
          RouterLink: true,
        },
      },
    })
    await flushPromises()

    await wrapper.get('button[aria-label="Delete story"]').trigger('click')
    await flushPromises()

    const confirmButton = document.body.querySelector('[data-testid="confirm-modal-confirm"]') as HTMLButtonElement | null
    expect(confirmButton?.textContent).toBe('Delete story')
    confirmButton?.click()
    await flushPromises()

    expect(mockedDeleteStory).toHaveBeenCalledWith('story-1')
    expect(pushMock).toHaveBeenCalledWith({ name: 'dashboard' })
  })
})

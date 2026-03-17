import { computed, nextTick, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { User } from '@/services/auth'
import { getSubscriptionSummary } from '@/services/subscription'
import DashboardView from '@/views/DashboardView.vue'
import StoryCreateView from '@/views/StoryCreateView.vue'
import StoryDetailView from '@/views/StoryDetailView.vue'
import { useAuth } from '@/composables/useAuth'
import {
  createStory,
  deleteStory,
  getAssetUrl,
  getStory,
  getStories,
  retryStoryMissingOutputs,
  retryStoryPageMissingOutputs,
} from '@/services/stories'
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
  getAssetUrl: vi.fn().mockResolvedValue({ url: 'https://assets.example/file.mp3', expires_at: '2026-03-13T20:10:00Z' }),
  getStory: vi.fn(),
  getStories: vi.fn().mockResolvedValue([]),
  retryStoryMissingOutputs: vi.fn(),
  retryStoryPageMissingOutputs: vi.fn(),
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

vi.mock('@/services/subscription', () => ({
  getSubscriptionSummary: vi.fn(),
}))

const mockedCreateStory = vi.mocked(createStory)
const mockedDeleteStory = vi.mocked(deleteStory)
const mockedGetAssetUrl = vi.mocked(getAssetUrl)
const mockedGetStory = vi.mocked(getStory)
const mockedGetStories = vi.mocked(getStories)
const mockedGetSubscriptionSummary = vi.mocked(getSubscriptionSummary)
const mockedRetryStoryMissingOutputs = vi.mocked(retryStoryMissingOutputs)
const mockedRetryStoryPageMissingOutputs = vi.mocked(retryStoryPageMissingOutputs)
const mockedGetChildren = vi.mocked(getChildren)
const mockedGetVoiceProfiles = vi.mocked(getVoiceProfiles)
const mediaPlayMock = vi.fn().mockResolvedValue(undefined)
const mediaPauseMock = vi.fn()

const sampleUser: User = {
  id: 'cc4e3be9-0e56-4d1b-9128-655ddcf06092',
  primary_email: 'parent@example.com',
  full_name: 'Parent Reader',
  avatar_url: null,
  status: 'active',
  role: 'customer',
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
    vi.useRealTimers()
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      value: 1024,
      writable: true,
    })
    routeRef.value = { params: { storyId: 'story-1' } }
    useAuthMock.mockReturnValue(makeAuthState())
    Object.defineProperty(window.HTMLMediaElement.prototype, 'play', {
      configurable: true,
      value: mediaPlayMock,
    })
    Object.defineProperty(window.HTMLMediaElement.prototype, 'pause', {
      configurable: true,
      value: mediaPauseMock,
    })
    mockedGetStories.mockResolvedValue([])
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
    mockedGetAssetUrl.mockResolvedValue({ url: 'https://assets.example/file.mp3', expires_at: '2026-03-13T20:10:00Z' })
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
      can_resume_missing_outputs: false,
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
    const sixPagesButton = wrapper.findAll('button').find((entry) => entry.text() === '6')
    await sixPagesButton?.trigger('click')
    await wrapper.get('select[name="reading_level"]').setValue('Preschool')
    await wrapper.get('select[name="voice_profile_id"]').setValue('voice-1')
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(mockedCreateStory).toHaveBeenCalledWith(
      expect.objectContaining({
        child_id: 'child-1',
        prompt: 'A lantern walk',
        theme: 'Bedtime',
        target_page_count: 6,
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
      can_resume_missing_outputs: false,
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
          retryable_outputs: [],
          output_errors: {},
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
    expect(wrapper.find('[data-testid="reader-autoplay-toggle"]').exists()).toBe(false)
  })

  it('renders per-page narration when audio is available', async () => {
    mockedGetStory.mockResolvedValue({
      id: 'story-1',
      user_id: 'user-1',
      child_id: 'child-1',
      voice_profile_id: 'voice-1',
      title: 'Lantern Walk',
      prompt: 'A lantern walk',
      theme: 'Bedtime',
      status: 'ready',
      target_page_count: 1,
      reading_level: 'Preschool',
      language: 'en',
      art_style: 'Dreamy',
      latest_error_message: null,
      can_resume_missing_outputs: false,
      created_at: '2026-03-13T20:00:00Z',
      updated_at: '2026-03-13T20:02:00Z',
      pages: [
        {
          id: 'page-1',
          page_number: 1,
          text_content: 'The lantern glowed softly beneath the moon.',
          image_prompt: 'A lantern beneath the moon',
          continuity_notes: 'Keep the lantern warm and golden.',
          status: 'complete',
          image_asset_id: null,
          audio_asset_id: 'audio-1',
          duration_ms: 4200,
          retryable_outputs: [],
          output_errors: {},
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

    expect(mockedGetAssetUrl).toHaveBeenCalledWith('audio-1')
    expect(wrapper.text()).toContain('Page narration')
    expect(wrapper.find('audio').exists()).toBe(true)
    expect(wrapper.find('[data-testid="reader-autoplay-toggle"]').exists()).toBe(true)
  })

  it('shows one narration line at a time in book view until full text is expanded', async () => {
    mockedGetStory.mockResolvedValue({
      id: 'story-1',
      user_id: 'user-1',
      child_id: 'child-1',
      voice_profile_id: 'voice-1',
      title: 'Sunlit Meadow',
      prompt: 'A meadow walk',
      theme: 'Bedtime',
      status: 'ready',
      target_page_count: 1,
      reading_level: 'Preschool',
      language: 'en',
      art_style: 'Dreamy',
      latest_error_message: null,
      can_resume_missing_outputs: false,
      created_at: '2026-03-13T20:00:00Z',
      updated_at: '2026-03-13T20:02:00Z',
      pages: [
        {
          id: 'page-1',
          page_number: 1,
          text_content: 'Akshat skipped across the meadow with a lantern glowing in his hands. Fireflies circled above him as the rabbit and tortoise cheered from the clover.',
          image_prompt: 'A lantern beneath the moon',
          continuity_notes: 'Keep the lantern warm and golden.',
          status: 'complete',
          image_asset_id: null,
          audio_asset_id: 'audio-1',
          duration_ms: 6000,
          retryable_outputs: [],
          output_errors: {},
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

    const bookViewButton = wrapper.findAll('button').find((entry) => entry.text() === 'Book view')
    await bookViewButton?.trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="reader-line"]').text()).toContain('Akshat skipped across the meadow with a lantern glowing in his hands.')
    expect(wrapper.text()).not.toContain('Fireflies circled above him as the rabbit and tortoise cheered from the clover.')

    await wrapper.get('[data-testid="reader-full-text-toggle"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Fireflies circled above him as the rabbit and tortoise cheered from the clover.')
  })

  it('uses the image overlay control for reader audio in book view', async () => {
    mockedGetStory.mockResolvedValue({
      id: 'story-1',
      user_id: 'user-1',
      child_id: 'child-1',
      voice_profile_id: 'voice-1',
      title: 'Lantern Walk',
      prompt: 'A lantern walk',
      theme: 'Bedtime',
      status: 'ready',
      target_page_count: 1,
      reading_level: 'Preschool',
      language: 'en',
      art_style: 'Dreamy',
      latest_error_message: null,
      can_resume_missing_outputs: false,
      created_at: '2026-03-13T20:00:00Z',
      updated_at: '2026-03-13T20:02:00Z',
      pages: [
        {
          id: 'page-1',
          page_number: 1,
          text_content: 'The lantern glowed softly beneath the moon.',
          image_prompt: 'A lantern beneath the moon',
          continuity_notes: 'Keep the lantern warm and golden.',
          status: 'complete',
          image_asset_id: null,
          audio_asset_id: 'audio-1',
          duration_ms: 4200,
          retryable_outputs: [],
          output_errors: {},
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

    const bookViewButton = wrapper.findAll('button').find((entry) => entry.text() === 'Book view')
    await bookViewButton?.trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="reader-audio-overlay-toggle"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Page narration')

    await wrapper.get('[data-testid="reader-audio-overlay-toggle"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="reader-audio-popover"]').text()).toContain('Play audio')
    expect(wrapper.get('[data-testid="reader-audio-popover"]').text()).toContain('1.25x')
  })

  it('disables autoplay until narrated pages are ready', async () => {
    mockedGetStory.mockResolvedValue({
      id: 'story-1',
      user_id: 'user-1',
      child_id: 'child-1',
      voice_profile_id: 'voice-1',
      title: 'Lantern Walk',
      prompt: 'A lantern walk',
      theme: 'Bedtime',
      status: 'generating',
      target_page_count: 1,
      reading_level: 'Preschool',
      language: 'en',
      art_style: 'Dreamy',
      latest_error_message: null,
      can_resume_missing_outputs: false,
      created_at: '2026-03-13T20:00:00Z',
      updated_at: '2026-03-13T20:02:00Z',
      pages: [
        {
          id: 'page-1',
          page_number: 1,
          text_content: 'The lantern glowed softly beneath the moon.',
          image_prompt: 'A lantern beneath the moon',
          continuity_notes: 'Keep the lantern warm and golden.',
          status: 'image_ready',
          image_asset_id: null,
          audio_asset_id: 'audio-1',
          duration_ms: 4200,
          retryable_outputs: [],
          output_errors: {},
          created_at: '2026-03-13T20:01:00Z',
          updated_at: '2026-03-13T20:02:00Z',
        },
      ],
    })
    mockedGetAssetUrl.mockRejectedValueOnce(new Error('signed url pending'))

    const wrapper = mount(StoryDetailView, {
      global: {
        stubs: {
          RouterLink: true,
        },
      },
    })
    await flushPromises()

    const autoplayButton = wrapper.get('[data-testid="reader-autoplay-toggle"]')
    expect(autoplayButton.attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="reader-autoplay-hint"]').text()).toContain('Autoplay unlocks once narration is ready for every page.')
  })

  it('advances pages automatically in autoplay mode', async () => {
    vi.useFakeTimers()
    mockedGetStory.mockResolvedValue({
      id: 'story-1',
      user_id: 'user-1',
      child_id: 'child-1',
      voice_profile_id: 'voice-1',
      title: 'Lantern Walk',
      prompt: 'A lantern walk',
      theme: 'Bedtime',
      status: 'ready',
      target_page_count: 2,
      reading_level: 'Preschool',
      language: 'en',
      art_style: 'Dreamy',
      latest_error_message: null,
      can_resume_missing_outputs: false,
      created_at: '2026-03-13T20:00:00Z',
      updated_at: '2026-03-13T20:02:00Z',
      pages: [
        {
          id: 'page-1',
          page_number: 1,
          text_content: 'The lantern glowed softly beneath the moon.',
          image_prompt: 'A lantern beneath the moon',
          continuity_notes: 'Keep the lantern warm and golden.',
          status: 'complete',
          image_asset_id: null,
          audio_asset_id: 'audio-1',
          duration_ms: 4200,
          retryable_outputs: [],
          output_errors: {},
          created_at: '2026-03-13T20:01:00Z',
          updated_at: '2026-03-13T20:02:00Z',
        },
        {
          id: 'page-2',
          page_number: 2,
          text_content: 'The rabbit and tortoise waved from the clover.',
          image_prompt: 'Forest friends waving from the clover',
          continuity_notes: 'Keep the meadow bright and warm.',
          status: 'complete',
          image_asset_id: null,
          audio_asset_id: 'audio-2',
          duration_ms: 3900,
          retryable_outputs: [],
          output_errors: {},
          created_at: '2026-03-13T20:01:00Z',
          updated_at: '2026-03-13T20:02:00Z',
        },
      ],
    })
    mockedGetAssetUrl
      .mockResolvedValueOnce({ url: 'https://assets.example/audio-1.mp3', expires_at: '2026-03-13T20:10:00Z' })
      .mockResolvedValueOnce({ url: 'https://assets.example/audio-2.mp3', expires_at: '2026-03-13T20:10:00Z' })

    const wrapper = mount(StoryDetailView, {
      global: {
        stubs: {
          RouterLink: true,
        },
      },
    })
    await flushPromises()

    await wrapper.get('[data-testid="reader-autoplay-toggle"]').trigger('click')
    await flushPromises()

    expect(mediaPlayMock).toHaveBeenCalled()

    const audio = wrapper.get('audio').element as HTMLAudioElement
    Object.defineProperty(audio, 'duration', {
      configurable: true,
      value: 4.2,
    })
    Object.defineProperty(audio, 'ended', {
      configurable: true,
      get: () => false,
    })
    audio.currentTime = 4.15
    audio.dispatchEvent(new Event('pause'))
    await nextTick()
    audio.dispatchEvent(new Event('ended'))
    await nextTick()
    vi.advanceTimersByTime(1000)
    await flushPromises()

    expect(wrapper.get('[data-testid="reader-current-page"]').text()).toContain('Page 2')
    expect(mediaPlayMock.mock.calls.length).toBeGreaterThanOrEqual(2)
  })

  it('renders autoplay as an immersive image-only mode on mobile', async () => {
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      value: 390,
      writable: true,
    })

    mockedGetStory.mockResolvedValue({
      id: 'story-1',
      user_id: 'user-1',
      child_id: 'child-1',
      voice_profile_id: 'voice-1',
      title: 'Lantern Walk',
      prompt: 'A lantern walk',
      theme: 'Bedtime',
      status: 'ready',
      target_page_count: 1,
      reading_level: 'Preschool',
      language: 'en',
      art_style: 'Dreamy',
      latest_error_message: null,
      can_resume_missing_outputs: false,
      created_at: '2026-03-13T20:00:00Z',
      updated_at: '2026-03-13T20:02:00Z',
      pages: [
        {
          id: 'page-1',
          page_number: 1,
          text_content: 'The lantern glowed softly beneath the moon.',
          image_prompt: 'A lantern beneath the moon',
          continuity_notes: 'Keep the lantern warm and golden.',
          status: 'complete',
          image_asset_id: null,
          audio_asset_id: 'audio-1',
          duration_ms: 4200,
          retryable_outputs: [],
          output_errors: {},
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

    await wrapper.get('[data-testid="reader-autoplay-toggle"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="reader-line"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="reader-current-page"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="reader-exit-autoplay"]').exists()).toBe(true)
    expect(wrapper.find('.story-reader__pagination').exists()).toBe(false)
    expect(wrapper.find('[data-testid="reader-audio-overlay-toggle"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="reader-full-text-toggle"]').exists()).toBe(false)
  })

  it('stops autoplay on a manual pause instead of advancing pages', async () => {
    vi.useFakeTimers()
    mockedGetStory.mockResolvedValue({
      id: 'story-1',
      user_id: 'user-1',
      child_id: 'child-1',
      voice_profile_id: 'voice-1',
      title: 'Lantern Walk',
      prompt: 'A lantern walk',
      theme: 'Bedtime',
      status: 'ready',
      target_page_count: 2,
      reading_level: 'Preschool',
      language: 'en',
      art_style: 'Dreamy',
      latest_error_message: null,
      can_resume_missing_outputs: false,
      created_at: '2026-03-13T20:00:00Z',
      updated_at: '2026-03-13T20:02:00Z',
      pages: [
        {
          id: 'page-1',
          page_number: 1,
          text_content: 'The lantern glowed softly beneath the moon.',
          image_prompt: 'A lantern beneath the moon',
          continuity_notes: 'Keep the lantern warm and golden.',
          status: 'complete',
          image_asset_id: null,
          audio_asset_id: 'audio-1',
          duration_ms: 4200,
          retryable_outputs: [],
          output_errors: {},
          created_at: '2026-03-13T20:01:00Z',
          updated_at: '2026-03-13T20:02:00Z',
        },
        {
          id: 'page-2',
          page_number: 2,
          text_content: 'The rabbit and tortoise waved from the clover.',
          image_prompt: 'Forest friends waving from the clover',
          continuity_notes: 'Keep the meadow bright and warm.',
          status: 'complete',
          image_asset_id: null,
          audio_asset_id: 'audio-2',
          duration_ms: 3900,
          retryable_outputs: [],
          output_errors: {},
          created_at: '2026-03-13T20:01:00Z',
          updated_at: '2026-03-13T20:02:00Z',
        },
      ],
    })
    mockedGetAssetUrl
      .mockResolvedValueOnce({ url: 'https://assets.example/audio-1.mp3', expires_at: '2026-03-13T20:10:00Z' })
      .mockResolvedValueOnce({ url: 'https://assets.example/audio-2.mp3', expires_at: '2026-03-13T20:10:00Z' })

    const wrapper = mount(StoryDetailView, {
      global: {
        stubs: {
          RouterLink: true,
        },
      },
    })
    await flushPromises()

    await wrapper.get('[data-testid="reader-autoplay-toggle"]').trigger('click')
    await flushPromises()
    vi.advanceTimersByTime(1)
    await flushPromises()

    const audio = wrapper.get('audio').element as HTMLAudioElement
    Object.defineProperty(audio, 'duration', {
      configurable: true,
      value: 4.2,
    })
    Object.defineProperty(audio, 'ended', {
      configurable: true,
      get: () => false,
    })
    audio.currentTime = 1.5
    audio.dispatchEvent(new Event('pause'))
    await nextTick()
    vi.advanceTimersByTime(1500)
    await flushPromises()

    expect(wrapper.get('[data-testid="reader-current-page"]').text()).toContain('Page 1')

    await wrapper.get('[data-testid="reader-audio-overlay-toggle"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="reader-overlay-playback-toggle"]').text()).toContain('Play autoplay')
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
      can_resume_missing_outputs: false,
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

  it('retries missing outputs for the whole story from detail view', async () => {
    mockedGetStory.mockResolvedValue({
      id: 'story-1',
      user_id: 'user-1',
      child_id: 'child-1',
      voice_profile_id: 'voice-1',
      title: 'Broken Story',
      prompt: 'A lantern walk',
      theme: 'Bedtime',
      status: 'failed',
      target_page_count: 1,
      reading_level: 'Preschool',
      language: 'en',
      art_style: 'Dreamy',
      latest_error_message: 'Gemini image generation returned no images.',
      can_resume_missing_outputs: true,
      created_at: '2026-03-13T20:00:00Z',
      updated_at: '2026-03-13T20:02:00Z',
      pages: [
        {
          id: 'page-1',
          page_number: 1,
          text_content: 'The lantern glowed softly beneath the moon.',
          image_prompt: 'A lantern beneath the moon',
          continuity_notes: 'Keep the lantern warm and golden.',
          status: 'failed',
          image_asset_id: null,
          audio_asset_id: null,
          duration_ms: null,
          retryable_outputs: ['image'],
          output_errors: { image: 'Gemini image generation returned no images.' },
          created_at: '2026-03-13T20:01:00Z',
          updated_at: '2026-03-13T20:02:00Z',
        },
      ],
    })
    mockedRetryStoryMissingOutputs.mockResolvedValue({
      id: 'story-1',
      user_id: 'user-1',
      child_id: 'child-1',
      voice_profile_id: 'voice-1',
      title: 'Broken Story',
      prompt: 'A lantern walk',
      theme: 'Bedtime',
      status: 'generating',
      target_page_count: 1,
      reading_level: 'Preschool',
      language: 'en',
      art_style: 'Dreamy',
      latest_error_message: null,
      can_resume_missing_outputs: false,
      created_at: '2026-03-13T20:00:00Z',
      updated_at: '2026-03-13T20:03:00Z',
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
          retryable_outputs: [],
          output_errors: {},
          created_at: '2026-03-13T20:01:00Z',
          updated_at: '2026-03-13T20:03:00Z',
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

    const retryButton = wrapper.findAll('button').find((entry) => entry.text().includes('Resume missing parts'))
    await retryButton?.trigger('click')
    await flushPromises()

    expect(mockedRetryStoryMissingOutputs).toHaveBeenCalledWith('story-1')
  })

  it('retries missing outputs for a single page from detail view', async () => {
    mockedGetStory.mockResolvedValue({
      id: 'story-1',
      user_id: 'user-1',
      child_id: 'child-1',
      voice_profile_id: 'voice-1',
      title: 'Broken Story',
      prompt: 'A lantern walk',
      theme: 'Bedtime',
      status: 'failed',
      target_page_count: 1,
      reading_level: 'Preschool',
      language: 'en',
      art_style: 'Dreamy',
      latest_error_message: 'Quota exceeded.',
      can_resume_missing_outputs: true,
      created_at: '2026-03-13T20:00:00Z',
      updated_at: '2026-03-13T20:02:00Z',
      pages: [
        {
          id: 'page-1',
          page_number: 1,
          text_content: 'The lantern glowed softly beneath the moon.',
          image_prompt: 'A lantern beneath the moon',
          continuity_notes: 'Keep the lantern warm and golden.',
          status: 'failed',
          image_asset_id: 'image-1',
          audio_asset_id: null,
          duration_ms: null,
          retryable_outputs: ['audio'],
          output_errors: { audio: 'Quota exceeded.' },
          created_at: '2026-03-13T20:01:00Z',
          updated_at: '2026-03-13T20:02:00Z',
        },
      ],
    })
    mockedRetryStoryPageMissingOutputs.mockResolvedValue({
      id: 'story-1',
      user_id: 'user-1',
      child_id: 'child-1',
      voice_profile_id: 'voice-1',
      title: 'Broken Story',
      prompt: 'A lantern walk',
      theme: 'Bedtime',
      status: 'generating',
      target_page_count: 1,
      reading_level: 'Preschool',
      language: 'en',
      art_style: 'Dreamy',
      latest_error_message: null,
      can_resume_missing_outputs: false,
      created_at: '2026-03-13T20:00:00Z',
      updated_at: '2026-03-13T20:03:00Z',
      pages: [
        {
          id: 'page-1',
          page_number: 1,
          text_content: 'The lantern glowed softly beneath the moon.',
          image_prompt: 'A lantern beneath the moon',
          continuity_notes: 'Keep the lantern warm and golden.',
          status: 'image_ready',
          image_asset_id: 'image-1',
          audio_asset_id: null,
          duration_ms: null,
          retryable_outputs: [],
          output_errors: {},
          created_at: '2026-03-13T20:01:00Z',
          updated_at: '2026-03-13T20:03:00Z',
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

    const retryButton = wrapper.findAll('button').find((entry) => entry.text().includes('Retry narration'))
    await retryButton?.trigger('click')
    await flushPromises()

    expect(mockedRetryStoryPageMissingOutputs).toHaveBeenCalledWith('story-1', 'page-1')
  })
})

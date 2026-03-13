import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useStoriesStore } from '@/stores/stories'
import { createStory, getStory, getStories } from '@/services/stories'

vi.mock('@/services/stories', () => ({
  createStory: vi.fn(),
  getStory: vi.fn(),
  getStories: vi.fn(),
}))

const mockedCreateStory = vi.mocked(createStory)
const mockedGetStory = vi.mocked(getStory)
const mockedGetStories = vi.mocked(getStories)

describe('useStoriesStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.runOnlyPendingTimers()
    vi.useRealTimers()
  })

  it('stores fetched stories', async () => {
    mockedGetStories.mockResolvedValue([
      {
        id: 'story-1',
        child_id: 'child-1',
        title: 'Moonlight Rescue',
        theme: 'Adventure',
        status: 'ready',
        target_page_count: 6,
        art_style: 'Watercolor',
        latest_error_message: null,
        created_at: '2026-03-13T20:00:00Z',
        updated_at: '2026-03-13T20:05:00Z',
      },
    ])

    const store = useStoriesStore()
    await store.fetchStories()

    expect(store.stories).toHaveLength(1)
    expect(store.stories[0]?.title).toBe('Moonlight Rescue')
  })

  it('creates a story and starts polling when generation is in progress', async () => {
    mockedCreateStory.mockResolvedValue({
      id: 'story-1',
      user_id: 'user-1',
      child_id: 'child-1',
      voice_profile_id: null,
      title: null,
      prompt: 'A lantern walk',
      theme: 'Bedtime',
      status: 'generating',
      target_page_count: 6,
      reading_level: 'Preschool',
      language: 'en',
      art_style: 'Dreamy',
      latest_error_message: null,
      created_at: '2026-03-13T20:00:00Z',
      updated_at: '2026-03-13T20:00:00Z',
      pages: [],
    })
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
          text_content: 'The lantern glowed softly.',
          image_prompt: 'A glowing lantern by a forest path',
          continuity_notes: 'Keep the fox scarf visible.',
          status: 'text_ready',
          image_asset_id: null,
          audio_asset_id: null,
          duration_ms: null,
          created_at: '2026-03-13T20:01:00Z',
          updated_at: '2026-03-13T20:02:00Z',
        },
      ],
    })

    const store = useStoriesStore()
    await store.createStory({
      child_id: 'child-1',
      prompt: 'A lantern walk',
      theme: 'Bedtime',
    })

    expect(store.generatingStoryIds).toContain('story-1')

    await vi.advanceTimersByTimeAsync(4000)

    expect(mockedGetStory).toHaveBeenCalledWith('story-1')
    expect(store.currentStory?.status).toBe('ready')
    expect(store.generatingStoryIds).not.toContain('story-1')
  })

  it('stores a failed poll refresh as a user-facing error', async () => {
    mockedCreateStory.mockResolvedValue({
      id: 'story-1',
      user_id: 'user-1',
      child_id: 'child-1',
      voice_profile_id: null,
      title: null,
      prompt: 'A lantern walk',
      theme: 'Bedtime',
      status: 'generating',
      target_page_count: 6,
      reading_level: 'Preschool',
      language: 'en',
      art_style: 'Dreamy',
      latest_error_message: null,
      created_at: '2026-03-13T20:00:00Z',
      updated_at: '2026-03-13T20:00:00Z',
      pages: [],
    })
    mockedGetStory.mockRejectedValue(new Error('network'))

    const store = useStoriesStore()
    await store.createStory({
      child_id: 'child-1',
      prompt: 'A lantern walk',
    })

    await vi.advanceTimersByTimeAsync(4000)

    expect(store.error).toBe('Failed to refresh story status.')
  })
})

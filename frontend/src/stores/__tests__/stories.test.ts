import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useStoriesStore } from '@/stores/stories'
import {
  createStory,
  deleteStory,
  getAssetUrl,
  getStory,
  getStories,
  retryStoryMissingOutputs,
  retryStoryPageMissingOutputs,
} from '@/services/stories'

vi.mock('@/services/stories', () => ({
  createStory: vi.fn(),
  deleteStory: vi.fn(),
  getAssetUrl: vi.fn(),
  getStory: vi.fn(),
  getStories: vi.fn(),
  retryStoryMissingOutputs: vi.fn(),
  retryStoryPageMissingOutputs: vi.fn(),
}))

const mockedCreateStory = vi.mocked(createStory)
const mockedDeleteStory = vi.mocked(deleteStory)
const mockedGetAssetUrl = vi.mocked(getAssetUrl)
const mockedGetStory = vi.mocked(getStory)
const mockedGetStories = vi.mocked(getStories)
const mockedRetryStoryMissingOutputs = vi.mocked(retryStoryMissingOutputs)
const mockedRetryStoryPageMissingOutputs = vi.mocked(retryStoryPageMissingOutputs)

describe('useStoriesStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.useFakeTimers()
    mockedGetAssetUrl.mockResolvedValue({ url: 'https://assets.example/file', expires_at: '2026-03-13T20:10:00Z' })
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

  it('deletes a story and clears local state', async () => {
    mockedDeleteStory.mockResolvedValue(undefined)

    const store = useStoriesStore()
    store.stories = [
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
    ]
    store.currentStory = {
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
      latest_error_message: 'Worker failed',
      created_at: '2026-03-13T20:00:00Z',
      updated_at: '2026-03-13T20:02:00Z',
      pages: [],
    }
    store.generatingStoryIds = ['story-1']

    await store.deleteStory('story-1')

    expect(mockedDeleteStory).toHaveBeenCalledWith('story-1')
    expect(store.stories).toEqual([])
    expect(store.currentStory).toBeNull()
    expect(store.generatingStoryIds).toEqual([])
  })

  it('fetches missing audio asset URLs when loading story detail', async () => {
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
      created_at: '2026-03-13T20:00:00Z',
      updated_at: '2026-03-13T20:02:00Z',
      pages: [
        {
          id: 'page-1',
          page_number: 1,
          text_content: 'The lantern glowed softly.',
          image_prompt: 'A glowing lantern by a forest path',
          continuity_notes: 'Keep the fox scarf visible.',
          status: 'complete',
          image_asset_id: null,
          audio_asset_id: 'audio-1',
          duration_ms: 2400,
          created_at: '2026-03-13T20:01:00Z',
          updated_at: '2026-03-13T20:02:00Z',
        },
      ],
    })

    const store = useStoriesStore()
    await store.fetchStory('story-1')
    await Promise.resolve()

    expect(mockedGetAssetUrl).toHaveBeenCalledWith('audio-1')
    expect(store.audioUrls['audio-1']).toBe('https://assets.example/file')
  })

  it('retries missing outputs and restarts polling when the story becomes generating again', async () => {
    mockedRetryStoryMissingOutputs.mockResolvedValue({
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
          text_content: 'The lantern glowed softly.',
          image_prompt: 'A glowing lantern by a forest path',
          continuity_notes: 'Keep the fox scarf visible.',
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

    const store = useStoriesStore()
    await store.retryStoryMissingOutputs('story-1')

    expect(mockedRetryStoryMissingOutputs).toHaveBeenCalledWith('story-1')
    expect(store.generatingStoryIds).toContain('story-1')
  })

  it('retries missing outputs for a single page', async () => {
    mockedRetryStoryPageMissingOutputs.mockResolvedValue({
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
          text_content: 'The lantern glowed softly.',
          image_prompt: 'A glowing lantern by a forest path',
          continuity_notes: 'Keep the fox scarf visible.',
          status: 'image_ready',
          image_asset_id: 'image-1',
          audio_asset_id: null,
          duration_ms: null,
          retryable_outputs: ['audio'],
          output_errors: { audio: 'Quota exceeded' },
          created_at: '2026-03-13T20:01:00Z',
          updated_at: '2026-03-13T20:02:00Z',
        },
      ],
    })

    const store = useStoriesStore()
    await store.retryStoryPageMissingOutputs('story-1', 'page-1')

    expect(mockedRetryStoryPageMissingOutputs).toHaveBeenCalledWith('story-1', 'page-1')
    expect(store.generatingStoryIds).toContain('story-1')
  })
})

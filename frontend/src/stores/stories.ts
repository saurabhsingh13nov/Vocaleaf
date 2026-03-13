import axios from 'axios'
import { ref } from 'vue'
import { defineStore } from 'pinia'

import {
  createStory as createStoryRequest,
  getStory as getStoryRequest,
  getStories as getStoriesRequest,
  type CreateStoryPayload,
  type Story,
  type StoryListItem,
} from '@/services/stories'

const STORY_POLL_INTERVAL_MS = 4000

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

function toListItem(story: Story): StoryListItem {
  return {
    id: story.id,
    child_id: story.child_id,
    title: story.title,
    theme: story.theme,
    status: story.status,
    target_page_count: story.target_page_count,
    art_style: story.art_style,
    latest_error_message: story.latest_error_message,
    created_at: story.created_at,
    updated_at: story.updated_at,
  }
}

export const useStoriesStore = defineStore('stories', () => {
  const stories = ref<StoryListItem[]>([])
  const currentStory = ref<Story | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const generatingStoryIds = ref<string[]>([])
  const pollingTimers = new Map<string, number>()

  function mergeStoryListItem(story: StoryListItem) {
    const index = stories.value.findIndex((entry) => entry.id === story.id)

    if (index === -1) {
      stories.value.unshift(story)
      return
    }

    stories.value.splice(index, 1, story)
  }

  function mergeStoryDetail(story: Story) {
    currentStory.value = story
    mergeStoryListItem(toListItem(story))
  }

  function clearGeneratingState(storyId: string) {
    generatingStoryIds.value = generatingStoryIds.value.filter((entry) => entry !== storyId)
    stopGenerationPolling(storyId)
  }

  async function fetchStories(limit = 20, offset = 0) {
    isLoading.value = true
    error.value = null

    try {
      stories.value = await getStoriesRequest(limit, offset)
      for (const story of stories.value) {
        if (story.status === 'generating') {
          scheduleGenerationPoll(story.id)
        } else {
          clearGeneratingState(story.id)
        }
      }
      return stories.value
    } catch (e) {
      error.value = 'Failed to load stories.'
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function createStory(payload: CreateStoryPayload) {
    isLoading.value = true
    error.value = null

    try {
      const story = await createStoryRequest(payload)
      mergeStoryDetail(story)
      if (story.status === 'generating') {
        scheduleGenerationPoll(story.id)
      }
      return story
    } catch (e) {
      error.value = getErrorMessage(e)
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function fetchStory(storyId: string) {
    error.value = null

    try {
      const story = await getStoryRequest(storyId)
      mergeStoryDetail(story)
      if (story.status === 'generating') {
        scheduleGenerationPoll(story.id)
      } else {
        clearGeneratingState(story.id)
      }
      return story
    } catch (e) {
      error.value = getErrorMessage(e)
      throw e
    }
  }

  function scheduleGenerationPoll(storyId: string) {
    stopGenerationPolling(storyId)
    if (!generatingStoryIds.value.includes(storyId)) {
      generatingStoryIds.value = [...generatingStoryIds.value, storyId]
    }

    const timerId = window.setTimeout(async () => {
      try {
        const story = await getStoryRequest(storyId)
        mergeStoryDetail(story)
        if (story.status === 'generating') {
          scheduleGenerationPoll(storyId)
          return
        }
      } catch (e) {
        error.value = 'Failed to refresh story status.'
      }

      clearGeneratingState(storyId)
    }, STORY_POLL_INTERVAL_MS)

    pollingTimers.set(storyId, timerId)
  }

  function stopGenerationPolling(storyId: string) {
    const timerId = pollingTimers.get(storyId)
    if (timerId !== undefined) {
      window.clearTimeout(timerId)
      pollingTimers.delete(storyId)
    }
  }

  function stopAllPolling() {
    for (const storyId of Array.from(pollingTimers.keys())) {
      stopGenerationPolling(storyId)
    }
    generatingStoryIds.value = []
  }

  function isGeneratingStory(storyId: string) {
    return generatingStoryIds.value.includes(storyId)
  }

  return {
    createStory,
    currentStory,
    error,
    fetchStories,
    fetchStory,
    generatingStoryIds,
    getErrorMessage,
    isGeneratingStory,
    isLoading,
    stories,
    stopAllPolling,
    stopGenerationPolling,
  }
})

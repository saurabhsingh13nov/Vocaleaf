import { computed, nextTick, onBeforeUnmount, ref, watch, type ComputedRef } from 'vue'

import type { StoryPage } from '@/services/stories'

export type ReaderMode = 'grid' | 'book' | 'autoplay'

const AUTOPLAY_GAP_MS = 1000
const MIN_COMFORTABLE_LINE_WORDS = 6

function wordCount(text: string) {
  return text.trim().split(/\s+/).filter(Boolean).length
}

function splitNarrationLines(text: string | null | undefined) {
  const normalized = (text ?? '').replace(/\s+/g, ' ').trim()
  if (!normalized) return [] as string[]

  const fragments = (normalized.match(/[^.!?]+(?:[.!?]+(?:["'])?)?|[^.!?]+$/g) ?? [normalized])
    .map((fragment) => fragment.trim())
    .filter(Boolean)

  if (fragments.length <= 1) return fragments

  const merged: string[] = []
  let buffer = ''

  for (const fragment of fragments) {
    const candidate = buffer ? `${buffer} ${fragment}` : fragment

    if (wordCount(candidate) < MIN_COMFORTABLE_LINE_WORDS) {
      buffer = candidate
      continue
    }

    merged.push(candidate)
    buffer = ''
  }

  if (buffer) {
    if (merged.length === 0) {
      merged.push(buffer)
    } else {
      merged[merged.length - 1] = `${merged[merged.length - 1]} ${buffer}`
    }
  }

  return merged
}

type StoryPageCollection = ComputedRef<StoryPage[]>

export function useStoryReader(
  pages: StoryPageCollection,
  getAudioUrl: (page: StoryPage) => string | null,
) {
  const viewMode = ref<ReaderMode>('grid')
  const currentPageIndex = ref(0)
  const activeLineIndex = ref(0)
  const autoplayRunning = ref(false)
  const audioPlaying = ref(false)
  const audioCurrentTimeSeconds = ref(0)
  const audioDurationSeconds = ref(0)
  const audioPlaybackRate = ref(1)
  const audioControlsExpanded = ref(false)
  const audioElement = ref<HTMLAudioElement | null>(null)
  const expandedPages = ref<Record<string, boolean>>({})

  let autoplayDelayTimer: number | null = null
  let suppressPauseHandling = false

  const currentPage = computed(() => pages.value[currentPageIndex.value] ?? null)
  const narrationLinesByPage = computed<Record<string, string[]>>(() => (
    Object.fromEntries(
      pages.value.map((page) => [page.id, splitNarrationLines(page.text_content)]),
    )
  ))
  const currentNarrationLines = computed(() => (
    currentPage.value ? narrationLinesByPage.value[currentPage.value.id] ?? [] : []
  ))
  const currentNarrationLine = computed(() => {
    const lines = currentNarrationLines.value
    if (lines.length === 0) return null
    return lines[Math.min(activeLineIndex.value, lines.length - 1)] ?? lines[0]
  })
  const autoplayAvailable = computed(() => (
    pages.value.length > 0 && pages.value.every((page) => Boolean(getAudioUrl(page)))
  ))
  const autoplayBlockedReason = computed(() => {
    if (pages.value.length === 0) return 'Autoplay becomes available once story pages are ready.'
    if (!autoplayAvailable.value) return 'Autoplay unlocks once narration is ready for every page.'
    return null
  })
  const isCurrentTranscriptExpanded = computed(() => (
    currentPage.value ? expandedPages.value[currentPage.value.id] === true : false
  ))

  function clearAutoplayDelay() {
    if (autoplayDelayTimer !== null) {
      window.clearTimeout(autoplayDelayTimer)
      autoplayDelayTimer = null
    }
  }

  function isTrackCompleting(element: HTMLAudioElement | null) {
    if (!element) return false
    if (element.ended) return true
    if (!Number.isFinite(element.duration) || element.duration <= 0) return false
    return element.currentTime >= Math.max(element.duration - 0.15, 0)
  }

  function syncAudioStateFromElement() {
    const element = audioElement.value

    if (!element) {
      audioPlaying.value = false
      audioCurrentTimeSeconds.value = 0
      audioDurationSeconds.value = 0
      return
    }

    audioPlaying.value = !element.paused && !element.ended
    audioCurrentTimeSeconds.value = element.currentTime

    if (Number.isFinite(element.duration) && element.duration > 0) {
      audioDurationSeconds.value = element.duration
      return
    }

    const fallbackDurationSeconds = currentPage.value?.duration_ms
      ? currentPage.value.duration_ms / 1000
      : 0
    audioDurationSeconds.value = fallbackDurationSeconds
  }

  function withSuppressedPauseHandling(callback: () => void) {
    suppressPauseHandling = true
    callback()
    window.setTimeout(() => {
      suppressPauseHandling = false
    }, 0)
  }

  function pauseCurrentAudio({ resetTime = false } = {}) {
    const element = audioElement.value
    if (!element) return

    withSuppressedPauseHandling(() => {
      element.pause()
      if (resetTime) element.currentTime = 0
    })
    syncAudioStateFromElement()
  }

  function resetActiveLine() {
    activeLineIndex.value = 0
  }

  async function playCurrentAudio({ restart = false } = {}) {
    const element = audioElement.value
    if (!element || !currentPage.value) return

    clearAutoplayDelay()
    resetActiveLine()

    if (restart) {
      withSuppressedPauseHandling(() => {
        element.pause()
        element.currentTime = 0
      })
    }

    try {
      await element.play()
      autoplayRunning.value = true
      syncAudioStateFromElement()
    } catch {
      autoplayRunning.value = false
    }
  }

  function syncActiveLineToPlayback() {
    const element = audioElement.value
    const page = currentPage.value
    const lines = currentNarrationLines.value

    if (!element || !page || lines.length <= 1) {
      resetActiveLine()
      return
    }

    const durationMs = page.duration_ms ?? (
      Number.isFinite(element.duration) && element.duration > 0
        ? element.duration * 1000
        : 0
    )

    if (durationMs <= 0) {
      resetActiveLine()
      return
    }

    const progress = Math.min(Math.max((element.currentTime * 1000) / durationMs, 0), 0.999999)
    activeLineIndex.value = Math.min(Math.floor(progress * lines.length), lines.length - 1)
  }

  function handleAudioPlay() {
    clearAutoplayDelay()
    audioPlaying.value = true
    if (viewMode.value === 'autoplay') {
      autoplayRunning.value = true
    }
  }

  function handleAudioPause() {
    if (suppressPauseHandling) return
    if (isTrackCompleting(audioElement.value)) return
    audioPlaying.value = false
    if (viewMode.value === 'autoplay') {
      clearAutoplayDelay()
      autoplayRunning.value = false
    }
  }

  function handleAudioTimeUpdate() {
    syncAudioStateFromElement()
    syncActiveLineToPlayback()
  }

  function handleAudioLoadedMetadata() {
    syncAudioStateFromElement()
  }

  function handleAudioEnded() {
    const lines = currentNarrationLines.value
    if (lines.length > 0) {
      activeLineIndex.value = lines.length - 1
    }
    audioPlaying.value = false
    syncAudioStateFromElement()

    if (viewMode.value !== 'autoplay' || !autoplayRunning.value) return

    if (currentPageIndex.value >= pages.value.length - 1) {
      clearAutoplayDelay()
      autoplayRunning.value = false
      return
    }

    clearAutoplayDelay()
    autoplayDelayTimer = window.setTimeout(() => {
      currentPageIndex.value += 1
    }, AUTOPLAY_GAP_MS)
  }

  function bindAudioElement(element: HTMLAudioElement | null) {
    audioElement.value = element
  }

  function attachAudioListeners(element: HTMLAudioElement | null, action: 'add' | 'remove') {
    if (!element) return

    const method = action === 'add' ? element.addEventListener.bind(element) : element.removeEventListener.bind(element)
    method('loadedmetadata', handleAudioLoadedMetadata)
    method('play', handleAudioPlay)
    method('pause', handleAudioPause)
    method('timeupdate', handleAudioTimeUpdate)
    method('ended', handleAudioEnded)
  }

  function setViewMode(mode: ReaderMode) {
    if (mode === 'autoplay' && !autoplayAvailable.value) return

    closeAudioControls()
    viewMode.value = mode

    if (mode === 'autoplay') {
      autoplayRunning.value = true
      void nextTick(() => playCurrentAudio({ restart: true }))
      return
    }

    clearAutoplayDelay()
    autoplayRunning.value = false
    pauseCurrentAudio()
    audioControlsExpanded.value = false
  }

  function toggleAutoplayPlayback() {
    if (viewMode.value !== 'autoplay') {
      setViewMode('autoplay')
      return
    }

    if (autoplayRunning.value) {
      clearAutoplayDelay()
      autoplayRunning.value = false
      pauseCurrentAudio()
      return
    }

    autoplayRunning.value = true
    void nextTick(() => {
      audioElement.value?.play().catch(() => {
        autoplayRunning.value = false
      })
    })
  }

  function toggleAudioPlayback() {
    const element = audioElement.value
    if (!element) return

    if (!element.paused && !element.ended) {
      element.pause()
      return
    }

    void element.play().catch(() => {
      audioPlaying.value = false
    })
  }

  function toggleAudioControls() {
    audioControlsExpanded.value = !audioControlsExpanded.value
  }

  function closeAudioControls() {
    audioControlsExpanded.value = false
  }

  function setAudioPlaybackRate(rate: number) {
    audioPlaybackRate.value = rate

    if (audioElement.value) {
      audioElement.value.playbackRate = rate
    }
  }

  function seekAudio(seconds: number) {
    const element = audioElement.value
    if (!element) return

    element.currentTime = seconds
    audioCurrentTimeSeconds.value = seconds
    syncActiveLineToPlayback()
  }

  function goToPage(index: number) {
    if (index < 0 || index >= pages.value.length) return

    currentPageIndex.value = index
    closeAudioControls()

    if (viewMode.value === 'autoplay') {
      clearAutoplayDelay()
      autoplayRunning.value = true
    } else {
      resetActiveLine()
    }
  }

  function toggleCurrentTranscript() {
    const page = currentPage.value
    if (!page) return

    expandedPages.value = {
      ...expandedPages.value,
      [page.id]: !expandedPages.value[page.id],
    }
  }

  function resetReader() {
    clearAutoplayDelay()
    pauseCurrentAudio({ resetTime: true })
    autoplayRunning.value = false
    audioPlaying.value = false
    viewMode.value = 'grid'
    currentPageIndex.value = 0
    activeLineIndex.value = 0
    audioCurrentTimeSeconds.value = 0
    audioDurationSeconds.value = 0
    audioControlsExpanded.value = false
    expandedPages.value = {}
  }

  watch(audioElement, (nextElement, previousElement) => {
    attachAudioListeners(previousElement, 'remove')
    attachAudioListeners(nextElement, 'add')

    if (nextElement) {
      nextElement.playbackRate = audioPlaybackRate.value
      syncAudioStateFromElement()
    } else {
      syncAudioStateFromElement()
    }

    if (nextElement && viewMode.value === 'autoplay' && autoplayRunning.value) {
      void nextTick(() => playCurrentAudio({ restart: true }))
    }
  })

  watch(currentPage, () => {
    resetActiveLine()
    closeAudioControls()
    audioCurrentTimeSeconds.value = 0
    audioDurationSeconds.value = currentPage.value?.duration_ms
      ? currentPage.value.duration_ms / 1000
      : 0
  })

  watch(
    () => pages.value.length,
    (length) => {
      if (length === 0) {
        currentPageIndex.value = 0
        clearAutoplayDelay()
        autoplayRunning.value = false
        return
      }

      if (currentPageIndex.value >= length) {
        currentPageIndex.value = length - 1
      }
    },
  )

  watch(autoplayAvailable, (isAvailable) => {
    if (isAvailable || viewMode.value !== 'autoplay') return
    clearAutoplayDelay()
    autoplayRunning.value = false
    viewMode.value = 'book'
    pauseCurrentAudio()
  })

  onBeforeUnmount(() => {
    clearAutoplayDelay()
    attachAudioListeners(audioElement.value, 'remove')
    pauseCurrentAudio()
  })

  return {
    activeLineIndex,
    audioElement,
    audioControlsExpanded,
    audioCurrentTimeSeconds,
    audioDurationSeconds,
    audioPlaybackRate,
    audioPlaying,
    autoplayAvailable,
    autoplayBlockedReason,
    closeAudioControls,
    seekAudio,
    setAudioPlaybackRate,
    bindAudioElement,
    currentNarrationLine,
    currentNarrationLines,
    currentPage,
    currentPageIndex,
    goToPage,
    isCurrentTranscriptExpanded,
    narrationLinesByPage,
    resetReader,
    setViewMode,
    toggleAudioControls,
    toggleAudioPlayback,
    toggleAutoplayPlayback,
    toggleCurrentTranscript,
    viewMode,
    autoplayRunning,
  }
}

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, onUnmounted, ref, watch, type ComponentPublicInstance } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import ConfirmModal from '@/components/ConfirmModal.vue'
import { useStoryReader } from '@/composables/useStoryReader'
import { useChildrenStore } from '@/stores/children'
import { useStoriesStore } from '@/stores/stories'

const route = useRoute()
const router = useRouter()
const storiesStore = useStoriesStore()
const childrenStore = useChildrenStore()
const deleteModalOpen = ref(false)
const isDeleting = ref(false)
const isRetryingStory = ref(false)
const retryingPageId = ref<string | null>(null)
const parallaxElements = ref<HTMLElement[]>([])
const lightboxOpen = ref(false)
const lightboxIndex = ref(0)
const viewportWidth = ref(typeof window === 'undefined' ? 1024 : window.innerWidth)

const storyId = computed(() => String(route.params.storyId ?? ''))
const story = computed(() => (
  storiesStore.currentStory?.id === storyId.value
    ? storiesStore.currentStory
    : null
))
const childName = computed(() => {
  const child = childrenStore.children.find((entry) => entry.id === story.value?.child_id)
  return child?.name ?? 'Your child'
})
const sortedPages = computed(() => {
  if (!story.value) return []
  return [...story.value.pages].sort((a, b) => a.page_number - b.page_number)
})
const totalPages = computed(() => sortedPages.value.length)
const imagesReadyCount = computed(() =>
  sortedPages.value.filter((page) => page.image_asset_id).length
)
const audioReadyCount = computed(() =>
  sortedPages.value.filter((page) => page.audio_asset_id).length
)
const hasNarration = computed(() => (
  story.value?.voice_profile_id !== null
  && (
    story.value?.status === 'generating'
    || sortedPages.value.some((page) => Boolean(page.audio_asset_id) || page.status === 'complete' || page.status === 'audio_ready')
  )
))
const completedProgressUnits = computed(() => (
  imagesReadyCount.value + (hasNarration.value ? audioReadyCount.value : 0)
))
const totalProgressUnits = computed(() => totalPages.value * (hasNarration.value ? 2 : 1))
const progressPercent = computed(() => (
  totalProgressUnits.value > 0
    ? Math.round((completedProgressUnits.value / totalProgressUnits.value) * 100)
    : 0
))
const isGenerating = computed(() => story.value?.status === 'generating')
const progressSummary = computed(() => {
  if (totalPages.value === 0) return ''
  if (hasNarration.value) {
    return `${imagesReadyCount.value} of ${totalPages.value} illustrated · ${audioReadyCount.value} of ${totalPages.value} narrated`
  }
  return `${imagesReadyCount.value} of ${totalPages.value} illustrated`
})
const pagesWithImages = computed(() => (
  sortedPages.value.filter((page) => page.image_asset_id && storiesStore.imageUrls[page.image_asset_id])
))
const canResumeMissingOutputs = computed(() => Boolean(story.value?.can_resume_missing_outputs))

function getImageUrl(page: { image_asset_id: string | null }) {
  if (!page.image_asset_id) return null
  return storiesStore.imageUrls[page.image_asset_id] ?? null
}

function getAudioUrl(page: { audio_asset_id: string | null }) {
  if (!page.audio_asset_id) return null
  return storiesStore.audioUrls[page.audio_asset_id] ?? null
}

const {
  activeLineIndex,
  audioControlsExpanded,
  audioCurrentTimeSeconds,
  audioDurationSeconds,
  audioPlaybackRate,
  audioPlaying,
  autoplayAvailable,
  autoplayBlockedReason,
  autoplayRunning,
  bindAudioElement,
  closeAudioControls,
  currentNarrationLine,
  currentNarrationLines,
  currentPage,
  currentPageIndex,
  goToPage,
  isCurrentTranscriptExpanded,
  resetReader,
  seekAudio,
  setAudioPlaybackRate,
  setViewMode,
  toggleAudioControls,
  toggleAudioPlayback,
  toggleAutoplayPlayback,
  toggleCurrentTranscript,
  viewMode,
} = useStoryReader(sortedPages, getAudioUrl)

const currentPageAudioUrl = computed(() => (
  currentPage.value ? getAudioUrl(currentPage.value) : null
))
const currentPageImageUrl = computed(() => (
  currentPage.value ? getImageUrl(currentPage.value) : null
))
const currentLineLabel = computed(() => {
  if (currentNarrationLines.value.length === 0) return 'Narration line'
  return `Narration line ${Math.min(activeLineIndex.value + 1, currentNarrationLines.value.length)} of ${currentNarrationLines.value.length}`
})
const showFullTextToggle = computed(() => (
  currentNarrationLines.value.length > 1 && viewMode.value !== 'autoplay'
))
const autoplayHint = computed(() => (
  hasNarration.value ? autoplayBlockedReason.value : null
))
const isMobileViewport = computed(() => viewportWidth.value < 768)
const immersiveAutoplay = computed(() => (
  viewMode.value === 'autoplay' && isMobileViewport.value
))
const showReaderPagination = computed(() => !immersiveAutoplay.value)
const showReaderStageMeta = computed(() => !immersiveAutoplay.value)
const showOverlayAudioControl = computed(() => Boolean(currentPageAudioUrl.value))
const audioSpeedOptions = [1, 1.25, 1.5]

function retryableOutputs(page: { retryable_outputs?: Array<'image' | 'audio'> }) {
  return page.retryable_outputs ?? []
}

function pageOutputError(page: { output_errors?: Partial<Record<'image' | 'audio', string>> }, output: 'image' | 'audio') {
  return page.output_errors?.[output] ?? null
}

function pageRetryLabel(page: { retryable_outputs?: Array<'image' | 'audio'> }) {
  const outputs = retryableOutputs(page)
  if (outputs.length > 1) return 'Retry missing parts'
  if (outputs[0] === 'audio') return 'Retry narration'
  return 'Retry page illustration'
}

function isRetryingPage(pageId: string) {
  return retryingPageId.value === pageId
}

function showNarrationPending(page: { status: string; audio_asset_id: string | null }) {
  return hasNarration.value && !page.audio_asset_id && page.status === 'image_ready'
}

function showNarrationLoading(page: { audio_asset_id: string | null }) {
  return Boolean(page.audio_asset_id && !getAudioUrl(page))
}

function statusTone(status: string) {
  switch (status) {
    case 'ready':
      return 'bg-emerald-100 text-emerald-700'
    case 'failed':
      return 'bg-red-100 text-red-700'
    case 'generating':
      return 'bg-amber-100 text-amber-700'
    default:
      return 'bg-stone-200 text-stone-700'
  }
}

function statusLabel(status: string) {
  switch (status) {
    case 'generating':
      return 'Generating'
    case 'ready':
      return 'Ready'
    case 'failed':
      return 'Failed'
    default:
      return status
  }
}

function pageStatusLabel(status: string) {
  switch (status) {
    case 'text_ready':
      return 'Text ready'
    case 'image_ready':
      return 'Illustrated'
    case 'audio_ready':
      return 'Narrated'
    case 'complete':
      return 'Illustrated & narrated'
    case 'failed':
      return 'Failed'
    default:
      return status
  }
}

function pageStatusTone(status: string) {
  switch (status) {
    case 'complete':
      return 'bg-emerald-100 text-emerald-700'
    case 'audio_ready':
    case 'image_ready':
      return 'bg-sky-100 text-sky-700'
    case 'text_ready':
      return 'bg-amber-100 text-amber-700'
    case 'failed':
      return 'bg-red-100 text-red-700'
    default:
      return 'bg-stone-200 text-stone-700'
  }
}

function formatDate(value: string | null | undefined) {
  if (!value) return 'Unknown'
  return new Date(value).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

function formatDuration(durationMs: number | null) {
  if (!durationMs || durationMs <= 0) return 'Length available after playback'

  const totalSeconds = Math.round(durationMs / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60

  if (minutes === 0) return `${seconds} sec`
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
}

function formatPlaybackTime(seconds: number) {
  if (!Number.isFinite(seconds) || seconds <= 0) return '0:00'

  const roundedSeconds = Math.floor(seconds)
  const minutes = Math.floor(roundedSeconds / 60)
  const remainder = roundedSeconds % 60
  return `${minutes}:${remainder.toString().padStart(2, '0')}`
}

function openLightbox(pageIndex: number) {
  const page = sortedPages.value[pageIndex]
  if (!page?.image_asset_id || !storiesStore.imageUrls[page.image_asset_id]) return
  lightboxIndex.value = pagesWithImages.value.findIndex((entry) => entry.id === page.id)
  if (lightboxIndex.value === -1) return
  lightboxOpen.value = true
}

function closeLightbox() {
  lightboxOpen.value = false
}

function lightboxPrev() {
  if (lightboxIndex.value > 0) lightboxIndex.value -= 1
}

function lightboxNext() {
  if (lightboxIndex.value < pagesWithImages.value.length - 1) lightboxIndex.value += 1
}

function handleLightboxKeydown(event: KeyboardEvent) {
  if (!lightboxOpen.value) return
  if (event.key === 'Escape') closeLightbox()
  if (event.key === 'ArrowLeft') lightboxPrev()
  if (event.key === 'ArrowRight') lightboxNext()
}

function handleScroll() {
  if (window.innerWidth < 1024) return

  requestAnimationFrame(() => {
    for (const element of parallaxElements.value) {
      if (!element) continue
      const rect = element.getBoundingClientRect()
      const viewportCenter = window.innerHeight / 2
      const elementCenter = rect.top + rect.height / 2
      const offset = (elementCenter - viewportCenter) * -0.08
      element.style.transform = `translateY(${offset}px)`
    }
  })
}

function handleResize() {
  viewportWidth.value = window.innerWidth
}

function resolveTemplateElement(element: Element | ComponentPublicInstance | null) {
  if (element instanceof Element) return element
  if (element && '$el' in element && element.$el instanceof Element) return element.$el
  return null
}

function setParallaxRef(element: Element | ComponentPublicInstance | null, index: number) {
  const resolvedElement = resolveTemplateElement(element)
  if (resolvedElement instanceof HTMLElement) {
    parallaxElements.value[index] = resolvedElement
  }
}

function bindReaderAudioRef(element: Element | ComponentPublicInstance | null) {
  const resolvedElement = resolveTemplateElement(element)
  bindAudioElement(resolvedElement instanceof HTMLAudioElement ? resolvedElement : null)
}

function goToPreviousPage() {
  goToPage(currentPageIndex.value - 1)
}

function goToNextPage() {
  goToPage(currentPageIndex.value + 1)
}

function switchViewMode(mode: 'grid' | 'book' | 'autoplay') {
  setViewMode(mode)
}

function exitImmersiveAutoplay() {
  switchViewMode('book')
}

function handleAudioSeekInput(event: Event) {
  const target = event.target as HTMLInputElement | null
  if (!target) return

  const nextTime = Number.parseFloat(target.value)
  if (Number.isNaN(nextTime)) return
  seekAudio(nextTime)
}

function toggleOverlayPlayback() {
  if (viewMode.value === 'autoplay') {
    toggleAutoplayPlayback()
    return
  }

  toggleAudioPlayback()
}

async function loadStory(nextStoryId: string) {
  await Promise.allSettled([
    childrenStore.fetchChildren(),
    storiesStore.fetchStory(nextStoryId),
  ])
}

async function retryStoryMissingOutputs() {
  if (!story.value || !canResumeMissingOutputs.value) return

  isRetryingStory.value = true
  try {
    await storiesStore.retryStoryMissingOutputs(story.value.id)
  } finally {
    isRetryingStory.value = false
  }
}

async function retryPageMissingOutputs(pageId: string) {
  if (!story.value) return

  retryingPageId.value = pageId
  try {
    await storiesStore.retryStoryPageMissingOutputs(story.value.id, pageId)
  } finally {
    retryingPageId.value = null
  }
}

function openDeleteModal() {
  if (story.value) {
    deleteModalOpen.value = true
  }
}

function cancelDelete() {
  if (!isDeleting.value) {
    deleteModalOpen.value = false
  }
}

async function confirmDelete() {
  if (!story.value) return

  isDeleting.value = true

  try {
    await storiesStore.deleteStory(story.value.id)
    deleteModalOpen.value = false
    await router.push({ name: 'dashboard' })
  } catch {
    // Keep the modal open so the inline page error remains visible.
  } finally {
    isDeleting.value = false
  }
}

watch(
  storyId,
  (nextStoryId, previousStoryId) => {
    resetReader()
    if (previousStoryId) storiesStore.stopGenerationPolling(previousStoryId)
    if (nextStoryId) loadStory(nextStoryId)
  },
  { immediate: true },
)

watch(immersiveAutoplay, () => {
  closeAudioControls()
})

onMounted(() => {
  window.addEventListener('keydown', handleLightboxKeydown)
  window.addEventListener('scroll', handleScroll, { passive: true })
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  if (storyId.value) storiesStore.stopGenerationPolling(storyId.value)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleLightboxKeydown)
  window.removeEventListener('scroll', handleScroll)
  window.removeEventListener('resize', handleResize)
})
</script>

<template>
  <main class="min-h-screen px-4 py-6 sm:px-6 sm:py-8">
    <div class="app-shell space-y-6">
      <div class="page-header">
        <div>
          <p class="page-kicker">Story</p>
          <h1 class="page-title">
            {{ story && 'pages' in story ? story.title || 'Untitled Story' : 'Story Detail' }}
          </h1>
          <p class="page-subtitle">
            {{ childName }}'s story updates here as generation progresses.
          </p>
        </div>

        <RouterLink :to="{ name: 'dashboard' }" class="nav-link">&larr; Dashboard</RouterLink>
      </div>

      <div
        v-if="storiesStore.error"
        class="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        role="alert"
      >
        {{ storiesStore.error }}
      </div>

      <section v-if="story" class="surface-card px-6 py-6 sm:px-8">
        <div class="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p class="page-kicker">Overview</p>
            <h2 class="mt-2 text-3xl font-semibold text-[var(--app-ink)]">
              {{ story.title || 'Untitled Story' }}
            </h2>
            <p class="mt-3 text-sm leading-6 text-[var(--app-muted)]">
              {{ story.theme || 'Custom prompt' }} · {{ story.target_page_count ?? 0 }} pages · Created {{ formatDate(story.created_at) }}
            </p>
          </div>

          <div class="flex flex-wrap items-center gap-3">
            <div
              v-if="isGenerating && totalPages > 0"
              class="progress-ring-container"
            >
              <svg class="progress-ring" viewBox="0 0 48 48">
                <circle
                  class="progress-ring__bg"
                  cx="24" cy="24" r="20"
                  fill="none"
                  stroke="var(--app-border)"
                  stroke-width="3"
                />
                <circle
                  class="progress-ring__fill"
                  cx="24" cy="24" r="20"
                  fill="none"
                  stroke="var(--app-accent)"
                  stroke-width="3"
                  stroke-linecap="round"
                  :stroke-dasharray="125.66"
                  :stroke-dashoffset="125.66 - (125.66 * progressPercent) / 100"
                />
              </svg>
              <span class="progress-ring__text">{{ progressPercent }}%</span>
            </div>

            <span class="status-pill" :class="statusTone(story.status)">
              {{ statusLabel(story.status) }}
            </span>
            <span v-if="story.art_style" class="status-pill bg-[var(--app-accent-soft)] text-[var(--app-accent-strong)]">
              {{ story.art_style }}
            </span>
            <button
              v-if="canResumeMissingOutputs"
              type="button"
              class="secondary-button"
              :disabled="isRetryingStory || storiesStore.isLoading"
              @click="retryStoryMissingOutputs"
            >
              {{ isRetryingStory ? 'Resuming…' : 'Resume missing parts' }}
            </button>
            <button
              type="button"
              class="secondary-button border-red-200 text-[var(--app-danger)] hover:border-red-300 hover:bg-red-50"
              aria-label="Delete story"
              :disabled="storiesStore.isLoading"
              @click="openDeleteModal"
            >
              Delete story
            </button>
          </div>
        </div>

        <div
          v-if="story.latest_error_message"
          class="mt-5 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          {{ story.latest_error_message }}
        </div>

        <div v-if="isGenerating && totalPages === 0" class="mt-8 space-y-5">
          <div class="surface-card-muted px-5 py-5">
            <div class="generating-animation">
              <span class="dot" />
              <span class="dot" />
              <span class="dot" />
            </div>
            <p class="mt-4 text-center text-sm text-[var(--app-muted)]">Writing your story…</p>
          </div>

          <div class="grid gap-4 md:grid-cols-2">
            <article
              v-for="placeholder in story.target_page_count ?? 4"
              :key="placeholder"
              class="surface-card-muted animate-pulse px-5 py-5"
            >
              <p class="page-kicker">Page {{ placeholder }}</p>
              <div class="mt-4 h-4 w-2/3 rounded-full bg-[var(--app-border)]" />
              <div class="mt-3 space-y-2">
                <div class="h-3 rounded-full bg-[var(--app-border)]" />
                <div class="h-3 rounded-full bg-[var(--app-border)]" />
                <div class="h-3 w-4/5 rounded-full bg-[var(--app-border)]" />
              </div>
            </article>
          </div>
        </div>

        <div v-else-if="sortedPages.length > 0" class="mt-8">
          <div class="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p class="text-sm font-semibold text-[var(--app-muted)]">
                {{ progressSummary }}
              </p>
              <p
                v-if="hasNarration && autoplayHint"
                class="mt-1 text-xs leading-5 text-[var(--app-muted-soft)]"
                data-testid="reader-autoplay-hint"
              >
                {{ autoplayHint }}
              </p>
            </div>
            <div class="reader-mode-toggle">
              <button
                type="button"
                class="reader-mode-toggle__button"
                :class="{ 'reader-mode-toggle__button--active': viewMode === 'grid' }"
                @click="switchViewMode('grid')"
              >
                All pages
              </button>
              <button
                type="button"
                class="reader-mode-toggle__button"
                :class="{ 'reader-mode-toggle__button--active': viewMode === 'book' }"
                @click="switchViewMode('book')"
              >
                Book view
              </button>
              <button
                v-if="hasNarration"
                type="button"
                class="reader-mode-toggle__button"
                :class="{ 'reader-mode-toggle__button--active': viewMode === 'autoplay' }"
                :disabled="!autoplayAvailable"
                :title="autoplayHint ?? undefined"
                data-testid="reader-autoplay-toggle"
                @click="switchViewMode('autoplay')"
              >
                Autoplay
              </button>
            </div>
          </div>

          <div v-if="viewMode === 'grid'" class="space-y-6">
            <article
              v-for="(page, index) in sortedPages"
              :key="page.id"
              class="story-spread"
              :class="{ 'story-spread--flipped': page.page_number % 2 === 0 }"
            >
              <div class="story-image-card-wrapper">
                <div
                  v-if="page.status === 'text_ready' && !getImageUrl(page)"
                  class="story-image-card story-image-card--loading"
                >
                  <span class="story-image-card__shimmer-label">Illustrating<span class="animate-dots" /></span>
                </div>

                <div
                  v-else-if="getImageUrl(page)"
                  class="story-image-card story-image-card--ready"
                  @click="openLightbox(index)"
                >
                  <img
                    :src="getImageUrl(page)!"
                    :alt="`Illustration for page ${page.page_number}`"
                    class="story-image-card__img"
                    :ref="(element) => setParallaxRef(element, index)"
                  />
                </div>

                <div
                  v-else-if="page.status === 'failed'"
                  class="story-image-card story-image-card--failed"
                >
                  <p class="text-sm font-semibold text-[var(--app-danger)]">Image generation failed</p>
                  <p v-if="pageOutputError(page, 'image')" class="mt-2 text-xs leading-5 text-[var(--app-danger)]">
                    {{ pageOutputError(page, 'image') }}
                  </p>
                  <button
                    v-if="retryableOutputs(page).includes('image')"
                    type="button"
                    class="secondary-button mt-3 text-xs"
                    :disabled="isRetryingPage(page.id) || storiesStore.isLoading"
                    @click="retryPageMissingOutputs(page.id)"
                  >
                    {{ isRetryingPage(page.id) ? 'Retrying…' : pageRetryLabel(page) }}
                  </button>
                </div>

                <div v-else class="story-image-card story-image-card--loading">
                  <span class="text-sm text-[var(--app-muted)]">Waiting…</span>
                </div>
              </div>

              <div class="story-spread__text">
                <div class="flex items-center justify-between gap-3">
                  <p class="page-kicker">Page {{ page.page_number }}</p>
                  <span class="status-pill" :class="pageStatusTone(page.status)">
                    {{ pageStatusLabel(page.status) }}
                  </span>
                </div>

                <p class="story-page-text mt-4 text-[var(--app-ink)]">
                  {{ page.text_content }}
                </p>

                <div
                  v-if="retryableOutputs(page).includes('image') && !getImageUrl(page)"
                  class="mt-5 rounded-[1.5rem] border border-red-200 bg-red-50 px-4 py-4"
                >
                  <div class="flex items-center justify-between gap-3">
                    <p class="text-sm font-semibold text-[var(--app-danger)]">Illustration needs attention</p>
                    <button
                      type="button"
                      class="secondary-button text-xs"
                      :disabled="isRetryingPage(page.id) || storiesStore.isLoading"
                      @click="retryPageMissingOutputs(page.id)"
                    >
                      {{ isRetryingPage(page.id) ? 'Retrying…' : pageRetryLabel(page) }}
                    </button>
                  </div>
                  <p v-if="pageOutputError(page, 'image')" class="mt-2 text-sm leading-6 text-[var(--app-danger)]">
                    {{ pageOutputError(page, 'image') }}
                  </p>
                </div>

                <div
                  v-if="getAudioUrl(page) || showNarrationPending(page) || showNarrationLoading(page)"
                  class="mt-5 rounded-[1.5rem] border border-[var(--app-border)] bg-[var(--app-surface-muted)] px-4 py-4"
                >
                  <div class="flex items-center justify-between gap-3">
                    <p class="text-sm font-semibold text-[var(--app-ink)]">Page narration</p>
                    <p class="text-xs text-[var(--app-muted)]">{{ formatDuration(page.duration_ms) }}</p>
                  </div>

                  <audio
                    v-if="getAudioUrl(page)"
                    :src="getAudioUrl(page)!"
                    controls
                    preload="none"
                    class="mt-3 w-full"
                  />

                  <p v-else-if="showNarrationLoading(page)" class="mt-3 text-sm text-[var(--app-muted)]">
                    Loading narration…
                  </p>

                  <p v-else class="mt-3 text-sm text-[var(--app-muted)]">
                    Narrating this page now…
                  </p>
                </div>

                <div
                  v-else-if="retryableOutputs(page).includes('audio')"
                  class="mt-5 rounded-[1.5rem] border border-red-200 bg-red-50 px-4 py-4"
                >
                  <div class="flex items-center justify-between gap-3">
                    <p class="text-sm font-semibold text-[var(--app-danger)]">Narration needs attention</p>
                    <button
                      type="button"
                      class="secondary-button text-xs"
                      :disabled="isRetryingPage(page.id) || storiesStore.isLoading"
                      @click="retryPageMissingOutputs(page.id)"
                    >
                      {{ isRetryingPage(page.id) ? 'Retrying…' : pageRetryLabel(page) }}
                    </button>
                  </div>
                  <p v-if="pageOutputError(page, 'audio')" class="mt-2 text-sm leading-6 text-[var(--app-danger)]">
                    {{ pageOutputError(page, 'audio') }}
                  </p>
                </div>
              </div>
            </article>
          </div>

          <div v-else class="relative">
            <Transition name="page-slide" mode="out-in">
              <article
                :key="currentPage?.id"
                class="story-reader"
                :class="{ 'story-reader--immersive': immersiveAutoplay }"
              >
                <div class="story-reader__stage">
                  <div
                    v-if="showReaderStageMeta"
                    class="story-reader__stage-meta"
                  >
                    <p class="page-kicker" data-testid="reader-current-page">Page {{ currentPage?.page_number }}</p>
                    <div class="flex flex-wrap items-center gap-2">
                      <span
                        v-if="currentPage"
                        class="status-pill"
                        :class="pageStatusTone(currentPage.status)"
                      >
                        {{ pageStatusLabel(currentPage.status) }}
                      </span>
                      <span
                        v-if="viewMode === 'autoplay'"
                        class="status-pill bg-[var(--app-accent-soft)] text-[var(--app-accent-strong)]"
                      >
                        Autoplay
                      </span>
                    </div>
                  </div>

                  <div
                    v-if="currentPage?.status === 'text_ready' && !currentPageImageUrl"
                    class="story-image-card story-image-card--loading story-reader__image-card"
                  >
                    <span class="story-image-card__shimmer-label">Illustrating<span class="animate-dots" /></span>
                  </div>
                  <div
                    v-else-if="currentPage && currentPageImageUrl"
                    class="story-image-card story-image-card--ready story-reader__image-card"
                    @click="openLightbox(currentPageIndex)"
                  >
                    <img
                      :src="currentPageImageUrl"
                      :alt="`Illustration for page ${currentPage.page_number}`"
                      class="story-image-card__img"
                    />
                  </div>
                  <div
                    v-else-if="currentPage?.status === 'failed'"
                    class="story-image-card story-image-card--failed story-reader__image-card"
                  >
                    <p class="text-sm font-semibold text-[var(--app-danger)]">Image generation failed</p>
                    <p
                      v-if="currentPage && pageOutputError(currentPage, 'image')"
                      class="mt-2 text-xs leading-5 text-[var(--app-danger)]"
                    >
                      {{ pageOutputError(currentPage, 'image') }}
                    </p>
                    <button
                      v-if="currentPage && retryableOutputs(currentPage).includes('image')"
                      type="button"
                      class="secondary-button mt-3 text-xs"
                      :disabled="isRetryingPage(currentPage.id) || storiesStore.isLoading"
                      @click="retryPageMissingOutputs(currentPage.id)"
                    >
                      {{ isRetryingPage(currentPage.id) ? 'Retrying…' : pageRetryLabel(currentPage) }}
                    </button>
                  </div>
                  <div v-else class="story-image-card story-image-card--loading story-reader__image-card">
                    <span class="text-sm text-[var(--app-muted)]">Waiting…</span>
                  </div>

                  <div
                    v-if="immersiveAutoplay"
                    class="story-reader__immersive-topbar"
                  >
                    <button
                      type="button"
                      class="story-reader__immersive-exit"
                      data-testid="reader-exit-autoplay"
                      @click="exitImmersiveAutoplay"
                    >
                      Exit autoplay
                    </button>
                  </div>

                  <div
                    v-if="showOverlayAudioControl"
                    class="story-reader__audio-overlay"
                    @click.stop
                  >
                    <button
                      type="button"
                      class="story-reader__audio-fab"
                      data-testid="reader-audio-overlay-toggle"
                      @click.stop="toggleAudioControls"
                    >
                      <svg viewBox="0 0 24 24" aria-hidden="true" class="story-reader__audio-fab-icon">
                        <path
                          d="M5 9.5V14.5H8.5L13 19V5L8.5 9.5H5Z"
                          fill="none"
                          stroke="currentColor"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          stroke-width="1.8"
                        />
                        <path
                          d="M16 9.5C17.3333 10.6667 17.3333 13.3333 16 14.5"
                          fill="none"
                          stroke="currentColor"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          stroke-width="1.8"
                        />
                        <path
                          d="M18.75 7.25C21.4167 9.75 21.4167 14.25 18.75 16.75"
                          fill="none"
                          stroke="currentColor"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          stroke-width="1.8"
                        />
                      </svg>
                    </button>

                    <div
                      v-if="audioControlsExpanded"
                      class="story-reader__audio-popover"
                      data-testid="reader-audio-popover"
                    >
                      <div class="story-reader__audio-popover-header">
                        <button
                          type="button"
                          class="secondary-button"
                          data-testid="reader-overlay-playback-toggle"
                          @click="toggleOverlayPlayback"
                        >
                          {{
                            audioPlaying
                              ? viewMode === 'autoplay' ? 'Pause autoplay' : 'Pause audio'
                              : viewMode === 'autoplay' ? 'Play autoplay' : 'Play audio'
                          }}
                        </button>
                        <span class="text-xs font-semibold text-[var(--app-muted)]">
                          {{ formatPlaybackTime(audioCurrentTimeSeconds) }} / {{ formatPlaybackTime(audioDurationSeconds) }}
                        </span>
                      </div>

                      <input
                        type="range"
                        min="0"
                        :max="Math.max(audioDurationSeconds, 1)"
                        step="0.1"
                        :value="audioCurrentTimeSeconds"
                        class="story-reader__audio-slider"
                        data-testid="reader-audio-slider"
                        @input="handleAudioSeekInput"
                      >

                      <div class="story-reader__audio-speed-row">
                        <span class="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--app-muted-soft)]">Speed</span>
                        <div class="story-reader__audio-speed-buttons">
                          <button
                            v-for="speed in audioSpeedOptions"
                            :key="speed"
                            type="button"
                            class="story-reader__speed-button"
                            :class="{ 'story-reader__speed-button--active': audioPlaybackRate === speed }"
                            @click="setAudioPlaybackRate(speed)"
                          >
                            {{ speed }}x
                          </button>
                        </div>
                      </div>
                    </div>

                    <audio
                      v-if="currentPageAudioUrl"
                      :ref="bindReaderAudioRef"
                      :src="currentPageAudioUrl"
                      preload="metadata"
                      class="hidden"
                    />
                  </div>
                </div>

                <div
                  class="story-reader__panel"
                  :class="{ 'story-reader__panel--immersive': immersiveAutoplay }"
                >
                  <div class="story-reader__line-card">
                    <p class="story-reader__line-label">
                      {{ currentLineLabel }}
                    </p>
                    <p
                      class="story-reader__line"
                      data-testid="reader-line"
                    >
                      {{ currentNarrationLine || currentPage?.text_content || 'Narration text will appear here once the page is ready.' }}
                    </p>
                    <button
                      v-if="showFullTextToggle"
                      type="button"
                      class="text-button story-reader__toggle"
                      data-testid="reader-full-text-toggle"
                      @click="toggleCurrentTranscript"
                    >
                      {{ isCurrentTranscriptExpanded ? 'Hide full text' : 'View full text' }}
                    </button>

                    <div
                      v-if="isCurrentTranscriptExpanded"
                      class="story-reader__transcript"
                    >
                      <p
                        v-for="(line, index) in currentNarrationLines"
                        :key="`${currentPage?.id ?? 'page'}-${index}`"
                        class="story-reader__transcript-line"
                        :class="{ 'story-reader__transcript-line--active': index === activeLineIndex }"
                      >
                        {{ line }}
                      </p>
                    </div>
                  </div>

                  <div
                    v-if="currentPage && showNarrationLoading(currentPage) && !immersiveAutoplay"
                    class="story-reader__audio-status"
                  >
                    Loading narration…
                  </div>

                  <div
                    v-else-if="currentPage && showNarrationPending(currentPage) && !immersiveAutoplay"
                    class="story-reader__audio-status"
                  >
                    Narrating this page now…
                  </div>

                  <div
                    v-if="currentPage && retryableOutputs(currentPage).includes('image') && !currentPageImageUrl"
                    class="mt-5 rounded-[1.5rem] border border-red-200 bg-red-50 px-4 py-4"
                  >
                    <div class="flex items-center justify-between gap-3">
                      <p class="text-sm font-semibold text-[var(--app-danger)]">Illustration needs attention</p>
                      <button
                        type="button"
                        class="secondary-button text-xs"
                        :disabled="isRetryingPage(currentPage.id) || storiesStore.isLoading"
                        @click="retryPageMissingOutputs(currentPage.id)"
                      >
                        {{ isRetryingPage(currentPage.id) ? 'Retrying…' : pageRetryLabel(currentPage) }}
                      </button>
                    </div>
                    <p v-if="pageOutputError(currentPage, 'image')" class="mt-2 text-sm leading-6 text-[var(--app-danger)]">
                      {{ pageOutputError(currentPage, 'image') }}
                    </p>
                  </div>

                  <div
                    v-else-if="currentPage && retryableOutputs(currentPage).includes('audio')"
                    class="mt-5 rounded-[1.5rem] border border-red-200 bg-red-50 px-4 py-4"
                  >
                    <div class="flex items-center justify-between gap-3">
                      <p class="text-sm font-semibold text-[var(--app-danger)]">Narration needs attention</p>
                      <button
                        type="button"
                        class="secondary-button text-xs"
                        :disabled="isRetryingPage(currentPage.id) || storiesStore.isLoading"
                        @click="retryPageMissingOutputs(currentPage.id)"
                      >
                        {{ isRetryingPage(currentPage.id) ? 'Retrying…' : pageRetryLabel(currentPage) }}
                      </button>
                    </div>
                    <p v-if="pageOutputError(currentPage, 'audio')" class="mt-2 text-sm leading-6 text-[var(--app-danger)]">
                      {{ pageOutputError(currentPage, 'audio') }}
                    </p>
                  </div>
                </div>
              </article>
            </Transition>

            <div
              v-if="showReaderPagination"
              class="story-reader__pagination"
            >
              <button
                type="button"
                class="secondary-button"
                :disabled="currentPageIndex === 0"
                @click="goToPreviousPage"
              >
                &larr; Previous
              </button>
              <span class="text-sm text-[var(--app-muted)]">
                {{ currentPageIndex + 1 }} of {{ totalPages }}
              </span>
              <button
                type="button"
                class="secondary-button"
                :disabled="currentPageIndex >= totalPages - 1"
                @click="goToNextPage"
              >
                Next &rarr;
              </button>
            </div>
          </div>
        </div>

        <div v-else-if="story.status === 'failed'" class="mt-8 empty-panel px-6 py-10 text-center">
          <p class="text-lg font-semibold text-[var(--app-ink)]">Story generation failed</p>
          <p class="mx-auto mt-3 max-w-xl text-sm leading-6 text-[var(--app-muted)]">
            The story record is still saved. Review the error above and retry once the text worker is healthy again.
          </p>
        </div>
      </section>
    </div>
  </main>

  <Teleport to="body">
    <Transition name="lightbox">
      <div
        v-if="lightboxOpen && pagesWithImages.length > 0"
        class="lightbox-overlay"
        @click.self="closeLightbox"
      >
        <button type="button" class="lightbox-close" @click="closeLightbox" aria-label="Close">
          &times;
        </button>

        <button
          v-if="lightboxIndex > 0"
          type="button"
          class="lightbox-nav lightbox-nav--prev"
          @click="lightboxPrev"
          aria-label="Previous image"
        >
          &lsaquo;
        </button>

        <img
          :src="storiesStore.imageUrls[pagesWithImages[lightboxIndex]?.image_asset_id!]"
          :alt="`Page ${pagesWithImages[lightboxIndex]?.page_number}`"
          class="lightbox-image"
        />

        <button
          v-if="lightboxIndex < pagesWithImages.length - 1"
          type="button"
          class="lightbox-nav lightbox-nav--next"
          @click="lightboxNext"
          aria-label="Next image"
        >
          &rsaquo;
        </button>

        <p class="lightbox-indicator">
          Page {{ pagesWithImages[lightboxIndex]?.page_number }} of {{ totalPages }}
        </p>
      </div>
    </Transition>
  </Teleport>

  <ConfirmModal
    v-if="deleteModalOpen && story"
    title="Delete story"
    :message="`Are you sure you want to delete ${story.title || story.theme || 'this story'}? This will permanently remove the story and all of its pages. This can't be undone.`"
    confirm-label="Delete story"
    pending-confirm-label="Deleting..."
    :warning-text="story.status === 'generating' ? 'This story is still being generated. Deleting it will stop generation in progress.' : null"
    :is-pending="isDeleting"
    @cancel="cancelDelete"
    @confirm="confirmDelete"
  />
</template>

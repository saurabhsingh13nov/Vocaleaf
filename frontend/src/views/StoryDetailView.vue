<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import ConfirmModal from '@/components/ConfirmModal.vue'
import { useChildrenStore } from '@/stores/children'
import { useStoriesStore } from '@/stores/stories'

const route = useRoute()
const router = useRouter()
const storiesStore = useStoriesStore()
const childrenStore = useChildrenStore()
const deleteModalOpen = ref(false)
const isDeleting = ref(false)

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
const currentPage = computed(() => sortedPages.value[currentPageIndex.value] ?? null)
const imagesReadyCount = computed(() =>
  sortedPages.value.filter((p) => p.image_asset_id).length
)
const progressPercent = computed(() =>
  totalPages.value > 0 ? Math.round((imagesReadyCount.value / totalPages.value) * 100) : 0
)
const isGenerating = computed(() => story.value?.status === 'generating')
const allImagesReady = computed(() =>
  totalPages.value > 0 && imagesReadyCount.value === totalPages.value
)

// View mode: 'book' (one page at a time) or 'grid' (all pages)
const viewMode = ref<'book' | 'grid'>('grid')
const currentPageIndex = ref(0)

// Lightbox
const lightboxOpen = ref(false)
const lightboxIndex = ref(0)

const pagesWithImages = computed(() =>
  sortedPages.value.filter((p) => p.image_asset_id && storiesStore.imageUrls[p.image_asset_id])
)

function openLightbox(pageIndex: number) {
  const page = sortedPages.value[pageIndex]
  if (!page?.image_asset_id || !storiesStore.imageUrls[page.image_asset_id]) return
  lightboxIndex.value = pagesWithImages.value.findIndex((p) => p.id === page.id)
  if (lightboxIndex.value === -1) return
  lightboxOpen.value = true
}

function closeLightbox() {
  lightboxOpen.value = false
}

function lightboxPrev() {
  if (lightboxIndex.value > 0) lightboxIndex.value--
}

function lightboxNext() {
  if (lightboxIndex.value < pagesWithImages.value.length - 1) lightboxIndex.value++
}

function handleLightboxKeydown(e: KeyboardEvent) {
  if (!lightboxOpen.value) return
  if (e.key === 'Escape') closeLightbox()
  if (e.key === 'ArrowLeft') lightboxPrev()
  if (e.key === 'ArrowRight') lightboxNext()
}

// Book navigation
function goToPage(index: number) {
  if (index >= 0 && index < totalPages.value) {
    currentPageIndex.value = index
  }
}

// Parallax
const parallaxElements = ref<HTMLElement[]>([])

function handleScroll() {
  if (window.innerWidth < 1024) return
  requestAnimationFrame(() => {
    for (const el of parallaxElements.value) {
      if (!el) continue
      const rect = el.getBoundingClientRect()
      const viewportCenter = window.innerHeight / 2
      const elementCenter = rect.top + rect.height / 2
      const offset = (elementCenter - viewportCenter) * -0.08
      el.style.transform = `translateY(${offset}px)`
    }
  })
}

function setParallaxRef(el: any, index: number) {
  if (el) parallaxElements.value[index] = el
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
    case 'failed':
      return 'Failed'
    default:
      return status
  }
}

function pageStatusTone(status: string) {
  switch (status) {
    case 'image_ready':
      return 'bg-emerald-100 text-emerald-700'
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

function getImageUrl(page: { image_asset_id: string | null }) {
  if (!page.image_asset_id) return null
  return storiesStore.imageUrls[page.image_asset_id] ?? null
}

async function loadStory(nextStoryId: string) {
  await Promise.allSettled([
    childrenStore.fetchChildren(),
    storiesStore.fetchStory(nextStoryId),
  ])
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
    if (previousStoryId) storiesStore.stopGenerationPolling(previousStoryId)
    if (nextStoryId) loadStory(nextStoryId)
  },
  { immediate: true },
)

onMounted(() => {
  window.addEventListener('keydown', handleLightboxKeydown)
  window.addEventListener('scroll', handleScroll, { passive: true })
})

onBeforeUnmount(() => {
  if (storyId.value) storiesStore.stopGenerationPolling(storyId.value)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleLightboxKeydown)
  window.removeEventListener('scroll', handleScroll)
})
</script>

<template>
  <main class="min-h-screen px-4 py-6 sm:px-6 sm:py-8">
    <div class="app-shell space-y-6">
      <!-- Header -->
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

      <!-- Error -->
      <div
        v-if="storiesStore.error"
        class="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        role="alert"
      >
        {{ storiesStore.error }}
      </div>

      <section v-if="story" class="surface-card px-6 py-6 sm:px-8">
        <!-- Story metadata row -->
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
            <!-- Progress ring (during generation with pages) -->
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

        <!-- Error message -->
        <div
          v-if="story.latest_error_message"
          class="mt-5 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          {{ story.latest_error_message }}
        </div>

        <!-- Generating placeholder (no pages yet) -->
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

        <!-- Pages with content -->
        <div v-else-if="sortedPages.length > 0" class="mt-8">
          <!-- View mode toggle -->
          <div class="mb-6 flex items-center justify-between">
            <p class="text-sm font-semibold text-[var(--app-muted)]">
              {{ imagesReadyCount }} of {{ totalPages }} illustrated
            </p>
            <div class="flex gap-1 rounded-full border border-[var(--app-border)] bg-[var(--app-surface-muted)] p-0.5">
              <button
                type="button"
                class="rounded-full px-3 py-1 text-xs font-semibold transition"
                :class="viewMode === 'grid' ? 'bg-[var(--app-surface-strong)] text-[var(--app-ink)] shadow-sm' : 'text-[var(--app-muted)]'"
                @click="viewMode = 'grid'"
              >
                All pages
              </button>
              <button
                type="button"
                class="rounded-full px-3 py-1 text-xs font-semibold transition"
                :class="viewMode === 'book' ? 'bg-[var(--app-surface-strong)] text-[var(--app-ink)] shadow-sm' : 'text-[var(--app-muted)]'"
                @click="viewMode = 'book'"
              >
                Book view
              </button>
            </div>
          </div>

          <!-- Grid view -->
          <div v-if="viewMode === 'grid'" class="space-y-6">
            <article
              v-for="(page, index) in sortedPages"
              :key="page.id"
              class="story-spread"
              :class="{ 'story-spread--flipped': page.page_number % 2 === 0 }"
            >
              <!-- Image card -->
              <div class="story-image-card-wrapper">
                <!-- Generating shimmer -->
                <div
                  v-if="page.status === 'text_ready' && !getImageUrl(page)"
                  class="story-image-card story-image-card--loading"
                >
                  <span class="story-image-card__shimmer-label">Illustrating<span class="animate-dots" /></span>
                </div>

                <!-- Ready image -->
                <div
                  v-else-if="getImageUrl(page)"
                  class="story-image-card story-image-card--ready"
                  @click="openLightbox(index)"
                >
                  <img
                    :src="getImageUrl(page)!"
                    :alt="`Illustration for page ${page.page_number}`"
                    class="story-image-card__img"
                    :ref="(el) => setParallaxRef(el as HTMLElement, index)"
                  />
                </div>

                <!-- Failed -->
                <div
                  v-else-if="page.status === 'failed'"
                  class="story-image-card story-image-card--failed"
                >
                  <p class="text-sm font-semibold text-[var(--app-danger)]">Image generation failed</p>
                  <button type="button" class="secondary-button mt-3 text-xs" disabled>
                    Retry (coming soon)
                  </button>
                </div>

                <!-- Pending / other -->
                <div v-else class="story-image-card story-image-card--loading">
                  <span class="text-sm text-[var(--app-muted)]">Waiting…</span>
                </div>
              </div>

              <!-- Text content -->
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
              </div>
            </article>
          </div>

          <!-- Book view (one page at a time) -->
          <div v-else class="relative">
            <Transition name="page-slide" mode="out-in">
              <article :key="currentPage?.id" class="story-spread">
                <div class="story-image-card-wrapper">
                  <div
                    v-if="currentPage?.status === 'text_ready' && !getImageUrl(currentPage)"
                    class="story-image-card story-image-card--loading"
                  >
                    <span class="story-image-card__shimmer-label">Illustrating<span class="animate-dots" /></span>
                  </div>
                  <div
                    v-else-if="currentPage && getImageUrl(currentPage)"
                    class="story-image-card story-image-card--ready"
                    @click="openLightbox(currentPageIndex)"
                  >
                    <img
                      :src="getImageUrl(currentPage)!"
                      :alt="`Illustration for page ${currentPage.page_number}`"
                      class="story-image-card__img"
                    />
                  </div>
                  <div
                    v-else-if="currentPage?.status === 'failed'"
                    class="story-image-card story-image-card--failed"
                  >
                    <p class="text-sm font-semibold text-[var(--app-danger)]">Image generation failed</p>
                  </div>
                  <div v-else class="story-image-card story-image-card--loading">
                    <span class="text-sm text-[var(--app-muted)]">Waiting…</span>
                  </div>
                </div>

                <div class="story-spread__text">
                  <p class="page-kicker">Page {{ currentPage?.page_number }}</p>
                  <p class="story-page-text mt-4 text-[var(--app-ink)]">
                    {{ currentPage?.text_content }}
                  </p>
                </div>
              </article>
            </Transition>

            <div class="mt-6 flex items-center justify-center gap-4">
              <button
                type="button"
                class="secondary-button"
                :disabled="currentPageIndex === 0"
                @click="goToPage(currentPageIndex - 1)"
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
                @click="goToPage(currentPageIndex + 1)"
              >
                Next &rarr;
              </button>
            </div>
          </div>
        </div>

        <!-- Failed state (no pages) -->
        <div v-else-if="story.status === 'failed'" class="mt-8 empty-panel px-6 py-10 text-center">
          <p class="text-lg font-semibold text-[var(--app-ink)]">Story generation failed</p>
          <p class="mx-auto mt-3 max-w-xl text-sm leading-6 text-[var(--app-muted)]">
            The story record is still saved. Review the error above and retry once the text worker is healthy again.
          </p>
        </div>
      </section>
    </div>
  </main>

  <!-- Lightbox -->
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

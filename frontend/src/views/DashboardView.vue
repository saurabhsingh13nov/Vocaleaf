<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import ConfirmModal from '@/components/ConfirmModal.vue'
import { useAuth } from '@/composables/useAuth'
import type { StoryListItem } from '@/services/stories'
import { getAssetUrl, getStory } from '@/services/stories'
import { useStoriesStore } from '@/stores/stories'

const router = useRouter()
const auth = useAuth()
const storiesStore = useStoriesStore()
const deleteTarget = ref<StoryListItem | null>(null)
const isDeleting = ref(false)

const thumbnailUrls = ref<Record<string, string>>({})

async function fetchThumbnailForStory(storyId: string) {
  if (thumbnailUrls.value[storyId]) return

  try {
    const story = await getStory(storyId)
    const firstPageWithImage = story.pages
      .sort((a, b) => a.page_number - b.page_number)
      .find((page) => page.image_asset_id)

    if (firstPageWithImage?.image_asset_id) {
      const resp = await getAssetUrl(firstPageWithImage.image_asset_id)
      thumbnailUrls.value = { ...thumbnailUrls.value, [storyId]: resp.url }
    }
  } catch {
    // Ignore. A story can exist without a thumbnail.
  }
}

watch(
  () => storiesStore.stories,
  (stories) => {
    for (const story of stories) {
      if (story.status === 'ready') {
        fetchThumbnailForStory(story.id)
      }
    }
  },
  { immediate: true },
)

const displayName = computed(() => auth.user.value?.full_name || 'Story Creator')
const firstName = computed(() => displayName.value.split(' ')[0] || 'Friend')
const sortedStories = computed(() => (
  [...storiesStore.stories].sort(
    (left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at),
  )
))
const latestGeneratingStory = computed(() => (
  sortedStories.value.find((story) => story.status === 'generating') ?? null
))
const latestReadyStory = computed(() => (
  sortedStories.value.find((story) => story.status === 'ready') ?? null
))
const latestFailedStory = computed(() => (
  sortedStories.value.find((story) => story.status === 'failed') ?? null
))
const heroStory = computed(() => latestGeneratingStory.value ?? latestReadyStory.value ?? null)
const heroStoryId = computed(() => heroStory.value?.id ?? null)
const activityStories = computed(() => (
  sortedStories.value.filter((story) => (
    (story.status === 'generating' || story.status === 'failed')
      && story.id !== heroStoryId.value
  ))
))
const readyStories = computed(() => (
  sortedStories.value.filter((story) => (
    story.status === 'ready' && story.id !== heroStoryId.value
  ))
))

function storyTitle(story: StoryListItem) {
  return story.title || story.theme || 'Untitled Story'
}

const heroContent = computed(() => {
  if (latestGeneratingStory.value) {
    return {
      kicker: 'Story in progress',
      title: storyTitle(latestGeneratingStory.value),
      body: 'Your newest story is coming together now. Open it any time to watch pages arrive and keep bedtime moving.',
      primaryLabel: 'Continue story',
      secondaryLabel: 'Create a new story',
      story: latestGeneratingStory.value,
      statusLabel: 'Creating now',
    }
  }

  if (latestReadyStory.value) {
    return {
      kicker: 'Ready tonight',
      title: storyTitle(latestReadyStory.value),
      body: 'Your latest story is ready to read again. Reopen it now or start a brand-new adventure.',
      primaryLabel: 'Read story',
      secondaryLabel: 'Create a new story',
      story: latestReadyStory.value,
      statusLabel: 'Ready to read',
    }
  }

  if (latestFailedStory.value) {
    return {
      kicker: 'Start the next story',
      title: 'Ready for another adventure?',
      body: 'You can start a fresh story right away. Any story that needs attention stays below so nothing gets lost.',
      primaryLabel: 'Create a new story',
      secondaryLabel: null,
      story: null,
      statusLabel: null,
    }
  }

  return {
    kicker: 'Start the next bedtime favorite',
    title: 'Create your first story',
    body: 'Pick a child, choose a theme, and let Vocaleaf begin a personalized story in the background right away.',
    primaryLabel: 'Create your first story',
    secondaryLabel: null,
    story: null,
    statusLabel: null,
  }
})

onMounted(() => {
  storiesStore.fetchStories().catch(() => undefined)
})

onBeforeUnmount(() => {
  storiesStore.stopAllPolling()
})

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

function storyStatusLabel(status: string) {
  switch (status) {
    case 'generating':
      return 'Creating now'
    case 'ready':
      return 'Ready to read'
    case 'failed':
      return 'Needs attention'
    default:
      return status
  }
}

function storyActionLabel(status: string) {
  switch (status) {
    case 'generating':
      return 'Continue story'
    case 'ready':
      return 'Read story'
    case 'failed':
      return 'Review story'
    default:
      return 'Open story'
  }
}

function storyMeta(story: StoryListItem) {
  return `${story.target_page_count ?? 0} pages · ${new Date(story.created_at).toLocaleDateString()}`
}

function storyErrorSummary(story: StoryListItem) {
  if (story.status !== 'failed' || !story.latest_error_message) return null
  return story.latest_error_message
}

async function handleLogout() {
  await auth.logout()
  await router.push({ name: 'login' })
}

async function openStory(storyId: string) {
  await router.push({ name: 'story-detail', params: { storyId } })
}

async function openStoryCreate() {
  await router.push({ name: 'story-create' })
}

function openDeleteModal(story: StoryListItem) {
  deleteTarget.value = { ...story }
}

function cancelDelete() {
  if (!isDeleting.value) {
    deleteTarget.value = null
  }
}

async function confirmDelete() {
  if (!deleteTarget.value) return

  isDeleting.value = true

  try {
    await storiesStore.deleteStory(deleteTarget.value.id)
    deleteTarget.value = null
  } catch {
    // Keep the modal open so the inline page error remains visible.
  } finally {
    isDeleting.value = false
  }
}
</script>

<template>
  <main class="min-h-screen px-4 py-6 sm:px-6 sm:py-8">
    <div class="app-shell space-y-5">
      <header class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p class="page-kicker">Story home</p>
          <h1 class="mt-3 text-4xl font-semibold text-[var(--app-ink)] sm:text-5xl">
            Welcome back, {{ firstName }}
          </h1>
        </div>

        <button
          v-if="auth.user.value?.role === 'staff' || auth.user.value?.role === 'admin'"
          class="header-action-button"
          type="button"
          aria-label="Open admin"
          @click="$router.push({ name: 'admin' })"
        >
          <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke-width="1.7" stroke="currentColor" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M10.5 6h9m-9 6h9m-9 6h9M4.5 6h.008v.008H4.5V6Zm0 6h.008v.008H4.5V12Zm0 6h.008v.008H4.5V18Z" />
          </svg>
          <span>Admin</span>
        </button>

        <button
          class="header-action-button"
          type="button"
          aria-label="Open subscription"
          @click="$router.push({ name: 'subscription' })"
        >
          <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke-width="1.7" stroke="currentColor" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6.75h16.5M6 3.75h12a2.25 2.25 0 0 1 2.25 2.25v12A2.25 2.25 0 0 1 18 20.25H6A2.25 2.25 0 0 1 3.75 18V6A2.25 2.25 0 0 1 6 3.75Z" />
          </svg>
          <span>Plan</span>
        </button>

        <button
          class="header-action-button"
          type="button"
          aria-label="Log out"
          @click="handleLogout"
        >
          <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke-width="1.7" stroke="currentColor" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6A2.25 2.25 0 0 0 5.25 5.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15m3-3-3-3m3 3H9" />
          </svg>
          <span>Log out</span>
        </button>
      </header>

      <section class="story-hub-hero surface-card px-6 py-6 sm:px-8">
        <div class="story-hub-hero__content">
          <div>
            <p class="page-kicker">{{ heroContent.kicker }}</p>
            <h2 class="mt-3 text-4xl font-semibold text-[var(--app-ink)] sm:text-5xl">
              {{ heroContent.title }}
            </h2>
            <p class="page-subtitle max-w-2xl">
              {{ heroContent.body }}
            </p>
          </div>

          <div v-if="heroContent.story" class="story-hub-hero__meta">
            <span class="status-pill" :class="statusTone(heroContent.story.status)">
              {{ heroContent.statusLabel }}
            </span>
            <p class="text-sm leading-6 text-[var(--app-muted)]">
              {{ storyMeta(heroContent.story) }}
            </p>
          </div>

          <div class="story-hub-hero__actions">
            <button
              type="button"
              class="primary-button w-full sm:w-auto"
              data-testid="dashboard-hero-primary"
              @click="heroContent.story ? openStory(heroContent.story.id) : openStoryCreate()"
            >
              {{ heroContent.primaryLabel }}
            </button>
            <button
              v-if="heroContent.secondaryLabel"
              type="button"
              class="secondary-button w-full sm:w-auto"
              data-testid="dashboard-hero-secondary"
              @click="openStoryCreate"
            >
              {{ heroContent.secondaryLabel }}
            </button>
            <button
              v-if="heroContent.story"
              type="button"
              class="story-delete-button"
              aria-label="Delete story"
              :disabled="storiesStore.isLoading"
              @click="openDeleteModal(heroContent.story)"
            >
              <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 7.5h12m-9.75 0v-.75A2.25 2.25 0 0 1 10.5 4.5h3a2.25 2.25 0 0 1 2.25 2.25v.75m-8.25 0h9.75m-8.25 3v6.75a.75.75 0 0 0 .75.75h4.5a.75.75 0 0 0 .75-.75V10.5m-6 0h6" />
              </svg>
            </button>
          </div>
        </div>

        <div
          class="story-hub-hero__art"
          :class="{ 'story-hub-hero__art--ready': Boolean(heroContent.story && thumbnailUrls[heroContent.story.id]) }"
        >
          <img
            v-if="heroContent.story && thumbnailUrls[heroContent.story.id]"
            :src="thumbnailUrls[heroContent.story.id]"
            :alt="storyTitle(heroContent.story)"
            class="story-hub-hero__image"
          />
          <div v-else class="story-hub-hero__placeholder">
            <span class="story-hub-hero__placeholder-copy">
              {{ heroContent.story ? storyStatusLabel(heroContent.story.status) : 'A new story begins here' }}
            </span>
          </div>
        </div>
      </section>

      <div
        v-if="storiesStore.isLoading && storiesStore.stories.length === 0"
        class="surface-card px-6 py-6 text-sm text-[var(--app-muted)] sm:px-8"
      >
        Loading your stories…
      </div>

      <section
        v-if="activityStories.length > 0"
        class="surface-card px-6 py-6 sm:px-8"
      >
        <div>
          <p class="page-kicker">Story activity</p>
          <h2 class="mt-2 text-3xl font-semibold text-[var(--app-ink)]">Keep going</h2>
        </div>

        <div class="mt-6 space-y-4">
          <article
            v-for="story in activityStories"
            :key="story.id"
            class="story-summary-card"
          >
            <div class="story-summary-card__thumb">
              <img
                v-if="thumbnailUrls[story.id]"
                :src="thumbnailUrls[story.id]"
                :alt="storyTitle(story)"
                class="story-summary-card__image"
              />
              <div v-else class="story-summary-card__image story-summary-card__image--placeholder" />
            </div>

            <div class="min-w-0 flex-1">
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <p class="page-kicker">Story</p>
                  <h3 class="mt-2 text-2xl font-semibold leading-tight text-[var(--app-ink)]">
                    {{ storyTitle(story) }}
                  </h3>
                </div>
                <span class="status-pill flex-shrink-0" :class="statusTone(story.status)">
                  {{ storyStatusLabel(story.status) }}
                </span>
              </div>

              <p class="mt-3 text-sm leading-6 text-[var(--app-muted)]">
                {{ storyMeta(story) }}
              </p>
              <p
                v-if="storyErrorSummary(story)"
                class="mt-2 text-sm leading-6 text-[var(--app-danger)]"
              >
                {{ storyErrorSummary(story) }}
              </p>

              <div class="mt-5 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  class="primary-button"
                  @click="openStory(story.id)"
                >
                  {{ storyActionLabel(story.status) }}
                </button>
                <button
                  type="button"
                  class="story-delete-button"
                  aria-label="Delete story"
                  :disabled="storiesStore.isLoading"
                  @click="openDeleteModal(story)"
                >
                  <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" aria-hidden="true">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M6 7.5h12m-9.75 0v-.75A2.25 2.25 0 0 1 10.5 4.5h3a2.25 2.25 0 0 1 2.25 2.25v.75m-8.25 0h9.75m-8.25 3v6.75a.75.75 0 0 0 .75.75h4.5a.75.75 0 0 0 .75-.75V10.5m-6 0h6" />
                  </svg>
                </button>
              </div>
            </div>
          </article>
        </div>
      </section>

      <section
        v-if="readyStories.length > 0"
        class="surface-card px-6 py-6 sm:px-8"
      >
        <div>
          <p class="page-kicker">Library</p>
          <h2 class="mt-2 text-3xl font-semibold text-[var(--app-ink)]">Your stories</h2>
        </div>

        <div class="mt-6 space-y-4">
          <article
            v-for="story in readyStories"
            :key="story.id"
            class="story-summary-card"
          >
            <div class="story-summary-card__thumb">
              <img
                v-if="thumbnailUrls[story.id]"
                :src="thumbnailUrls[story.id]"
                :alt="storyTitle(story)"
                class="story-summary-card__image"
              />
              <div v-else class="story-summary-card__image story-summary-card__image--placeholder" />
            </div>

            <div class="min-w-0 flex-1">
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <p class="page-kicker">Story</p>
                  <h3 class="mt-2 text-2xl font-semibold leading-tight text-[var(--app-ink)]">
                    {{ storyTitle(story) }}
                  </h3>
                </div>
                <span class="status-pill flex-shrink-0" :class="statusTone(story.status)">
                  {{ storyStatusLabel(story.status) }}
                </span>
              </div>

              <p class="mt-3 text-sm leading-6 text-[var(--app-muted)]">
                {{ storyMeta(story) }}
              </p>

              <div class="mt-5 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  class="primary-button"
                  @click="openStory(story.id)"
                >
                  {{ storyActionLabel(story.status) }}
                </button>
                <button
                  type="button"
                  class="story-delete-button"
                  aria-label="Delete story"
                  :disabled="storiesStore.isLoading"
                  @click="openDeleteModal(story)"
                >
                  <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" aria-hidden="true">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M6 7.5h12m-9.75 0v-.75A2.25 2.25 0 0 1 10.5 4.5h3a2.25 2.25 0 0 1 2.25 2.25v.75m-8.25 0h9.75m-8.25 3v6.75a.75.75 0 0 0 .75.75h4.5a.75.75 0 0 0 .75-.75V10.5m-6 0h6" />
                  </svg>
                </button>
              </div>
            </div>
          </article>
        </div>
      </section>

      <section class="surface-card-muted px-6 py-6 sm:px-8">
        <div>
          <p class="page-kicker">Story setup</p>
          <h2 class="mt-2 text-3xl font-semibold text-[var(--app-ink)]">Manage the details once</h2>
          <p class="mt-3 max-w-2xl text-sm leading-6 text-[var(--app-muted)]">
            Update child details or prepare narration voices whenever you need them. The rest of the dashboard stays focused on stories.
          </p>
        </div>

        <div class="mt-6 grid gap-4 md:grid-cols-2">
          <RouterLink :to="{ name: 'children' }" class="dashboard-tile transition hover:-translate-y-0.5">
            <p class="page-kicker">Profiles</p>
            <h3 class="mt-2 text-2xl font-semibold text-[var(--app-ink)]">Child profiles</h3>
            <p class="mt-3 text-sm leading-6 text-[var(--app-muted)]">
              Keep names, ages, and story preferences ready for the next story.
            </p>
          </RouterLink>

          <RouterLink :to="{ name: 'voice-profiles' }" class="dashboard-tile transition hover:-translate-y-0.5">
            <p class="page-kicker">Narration</p>
            <h3 class="mt-2 text-2xl font-semibold text-[var(--app-ink)]">Voice profiles</h3>
            <p class="mt-3 text-sm leading-6 text-[var(--app-muted)]">
              Add or refine narration voices for page-by-page playback later.
            </p>
          </RouterLink>
        </div>
      </section>
    </div>
  </main>

  <ConfirmModal
    v-if="deleteTarget"
    title="Delete story"
    :message="`Are you sure you want to delete ${deleteTarget.title || deleteTarget.theme || 'this story'}? This will permanently remove the story and all of its pages. This can't be undone.`"
    confirm-label="Delete story"
    pending-confirm-label="Deleting..."
    :warning-text="deleteTarget.status === 'generating' ? 'This story is still being generated. Deleting it will stop generation in progress.' : null"
    :is-pending="isDeleting"
    @cancel="cancelDelete"
    @confirm="confirmDelete"
  />
</template>

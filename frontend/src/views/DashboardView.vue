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

// Thumbnail URLs for story list items: story_id → image URL
const thumbnailUrls = ref<Record<string, string>>({})

async function fetchThumbnailForStory(storyId: string) {
  if (thumbnailUrls.value[storyId]) return
  try {
    const story = await getStory(storyId)
    const firstPageWithImage = story.pages
      .sort((a, b) => a.page_number - b.page_number)
      .find((p) => p.image_asset_id)
    if (firstPageWithImage?.image_asset_id) {
      const resp = await getAssetUrl(firstPageWithImage.image_asset_id)
      thumbnailUrls.value = { ...thumbnailUrls.value, [storyId]: resp.url }
    }
  } catch {
    // Ignore — thumbnail is optional
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
const email = computed(() => auth.user.value?.primary_email || 'No email on file')
const createdAt = computed(() => {
  const created = auth.user.value?.created_at

  if (!created) {
    return 'Unknown'
  }

  return new Date(created).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
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

async function handleLogout() {
  await auth.logout()
  await router.push({ name: 'login' })
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
    <div class="app-shell space-y-6">
      <section class="surface-card grid gap-5 px-6 py-7 sm:px-8 lg:grid-cols-[1.2fr_0.8fr] lg:px-10 lg:py-10">
        <div>
          <p class="page-kicker">Dashboard</p>
          <h1 class="page-title">Welcome, {{ displayName }}</h1>
          <p class="page-subtitle">
            This is the working home for your account. Manage profiles, prepare narration voices, and move toward story creation without losing your place.
          </p>
        </div>

        <div class="surface-card-muted p-5 sm:p-6">
          <p class="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--app-muted-soft)]">
            Account Snapshot
          </p>
          <dl class="mt-5 space-y-4 text-sm">
            <div>
              <dt class="text-[var(--app-muted)]">Email</dt>
              <dd class="mt-1 font-semibold text-[var(--app-ink)]">{{ email }}</dd>
            </div>
            <div>
              <dt class="text-[var(--app-muted)]">Status</dt>
              <dd class="mt-1 font-semibold capitalize text-[var(--app-ink)]">
                {{ auth.user.value?.status ?? 'unknown' }}
              </dd>
            </div>
            <div>
              <dt class="text-[var(--app-muted)]">Created</dt>
              <dd class="mt-1 font-semibold text-[var(--app-ink)]">{{ createdAt }}</dd>
            </div>
          </dl>

          <button class="primary-button mt-6 w-full sm:w-auto" type="button" @click="handleLogout">
            Log out
          </button>
        </div>
      </section>

      <section class="dashboard-grid md:grid-cols-2 xl:grid-cols-4">
        <RouterLink :to="{ name: 'story-create' }" class="dashboard-tile transition hover:-translate-y-0.5">
          <p class="page-kicker">Create</p>
          <h2 class="mt-3 text-2xl font-semibold text-[var(--app-ink)]">New story</h2>
          <p class="mt-3 text-sm leading-6 text-[var(--app-muted)]">
            Start a personalized story draft and let the background text worker build each page.
          </p>
        </RouterLink>

        <RouterLink :to="{ name: 'children' }" class="dashboard-tile transition hover:-translate-y-0.5">
          <p class="page-kicker">Profiles</p>
          <h2 class="mt-3 text-2xl font-semibold text-[var(--app-ink)]">Child profiles</h2>
          <p class="mt-3 text-sm leading-6 text-[var(--app-muted)]">
            Create and update the details that will personalize story prompts later.
          </p>
        </RouterLink>

        <RouterLink :to="{ name: 'voice-profiles' }" class="dashboard-tile transition hover:-translate-y-0.5">
          <p class="page-kicker">Narration</p>
          <h2 class="mt-3 text-2xl font-semibold text-[var(--app-ink)]">Voice profiles</h2>
          <p class="mt-3 text-sm leading-6 text-[var(--app-muted)]">
            Upload samples, trigger cloning, and prepare voices for page-by-page audio.
          </p>
        </RouterLink>

        <article class="dashboard-tile">
          <p class="page-kicker">Session</p>
          <h2 class="mt-3 text-2xl font-semibold text-[var(--app-ink)]">Cookie-backed auth</h2>
          <p class="mt-3 text-sm leading-6 text-[var(--app-muted)]">
            Refreshing the page restores the current user from the backend without storing tokens in local app state.
          </p>
        </article>

        <article class="dashboard-tile">
          <p class="page-kicker">Pipeline</p>
          <h2 class="mt-3 text-2xl font-semibold text-[var(--app-ink)]">Phase 10 live</h2>
          <p class="mt-3 text-sm leading-6 text-[var(--app-muted)]">
            Text + illustration generation active. Audio narration follows in phase 11.
          </p>
        </article>
      </section>

      <section class="surface-card px-6 py-6 sm:px-8">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p class="page-kicker">Library</p>
            <h2 class="mt-2 text-3xl font-semibold text-[var(--app-ink)]">Recent stories</h2>
          </div>
          <RouterLink :to="{ name: 'story-create' }" class="nav-link">Create another</RouterLink>
        </div>

        <div v-if="storiesStore.isLoading && storiesStore.stories.length === 0" class="mt-6 text-sm text-[var(--app-muted)]">
          Loading stories…
        </div>

        <div
          v-else-if="storiesStore.stories.length === 0"
          class="empty-panel mt-6 px-6 py-10 text-center"
        >
          <p class="text-base font-medium text-[var(--app-ink)]">No stories yet.</p>
          <p class="mx-auto mt-3 max-w-md text-sm leading-6 text-[var(--app-muted)]">
            Create the first story to see text generation progress and completed pages here.
          </p>
        </div>

        <div v-else class="mt-6 grid gap-4 md:grid-cols-2">
          <article
            v-for="story in storiesStore.stories"
            :key="story.id"
            class="surface-card-muted px-5 py-5"
          >
            <div class="flex items-start gap-3">
              <img
                v-if="thumbnailUrls[story.id]"
                :src="thumbnailUrls[story.id]"
                :alt="story.title || 'Story thumbnail'"
                class="h-16 w-16 flex-shrink-0 rounded-xl object-cover shadow-sm"
              />

              <RouterLink
                :to="{ name: 'story-detail', params: { storyId: story.id } }"
                class="block min-w-0 flex-1 transition hover:-translate-y-0.5"
              >
                <p class="page-kicker">Story</p>
                <h3 class="mt-2 text-2xl font-semibold text-[var(--app-ink)]">
                  {{ story.title || story.theme || 'Untitled Story' }}
                </h3>
                <p class="mt-3 text-sm leading-6 text-[var(--app-muted)]">
                  {{ story.target_page_count ?? 0 }} pages · {{ new Date(story.created_at).toLocaleDateString() }}
                </p>
              </RouterLink>

              <button
                type="button"
                class="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full border border-[var(--app-border)] bg-[var(--app-surface-strong)] text-[var(--app-muted)] transition hover:border-red-200 hover:bg-red-50 hover:text-[var(--app-danger)]"
                aria-label="Delete story"
                :disabled="storiesStore.isLoading"
                @click.stop="openDeleteModal(story)"
              >
                <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" aria-hidden="true">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M6 7.5h12m-9.75 0v-.75A2.25 2.25 0 0 1 10.5 4.5h3a2.25 2.25 0 0 1 2.25 2.25v.75m-8.25 0h9.75m-8.25 3v6.75a.75.75 0 0 0 .75.75h4.5a.75.75 0 0 0 .75-.75V10.5m-6 0h6" />
                </svg>
              </button>
              <span class="status-pill flex-shrink-0" :class="statusTone(story.status)">
                {{ story.status }}
              </span>
            </div>
          </article>
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

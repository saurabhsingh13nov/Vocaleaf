<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { useRouter } from 'vue-router'

import { useAuth } from '@/composables/useAuth'
import { useStoriesStore } from '@/stores/stories'

const router = useRouter()
const auth = useAuth()
const storiesStore = useStoriesStore()

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

async function handleDeleteStory(storyId: string) {
  const confirmed = window.confirm('Delete this failed story?')
  if (!confirmed) {
    return
  }

  await storiesStore.deleteStory(storyId)
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
          <h2 class="mt-3 text-2xl font-semibold text-[var(--app-ink)]">Phase 9 live</h2>
          <p class="mt-3 text-sm leading-6 text-[var(--app-muted)]">
            Text generation is now the active workflow. Illustrations and narration still follow in later phases.
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
            <div class="flex items-start justify-between gap-3">
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

              <span class="status-pill" :class="statusTone(story.status)">
                {{ story.status }}
              </span>
            </div>

            <div v-if="story.status === 'failed'" class="mt-5 flex justify-end">
              <button
                type="button"
                class="secondary-button border-red-200 text-[var(--app-danger)] hover:border-red-300 hover:bg-red-50"
                :disabled="storiesStore.isLoading"
                @click="handleDeleteStory(story.id)"
              >
                Delete
              </button>
            </div>
          </article>
        </div>
      </section>
    </div>
  </main>
</template>

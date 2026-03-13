<script setup lang="ts">
import { computed, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useChildrenStore } from '@/stores/children'
import { useStoriesStore } from '@/stores/stories'

const route = useRoute()
const router = useRouter()
const storiesStore = useStoriesStore()
const childrenStore = useChildrenStore()

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
      return 'Text ready'
    case 'failed':
      return 'Failed'
    default:
      return status
  }
}

function formatDate(value: string | null | undefined) {
  if (!value) {
    return 'Unknown'
  }

  return new Date(value).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

async function loadStory(nextStoryId: string) {
  await Promise.allSettled([
    childrenStore.fetchChildren(),
    storiesStore.fetchStory(nextStoryId),
  ])
}

async function handleDeleteStory() {
  if (!story.value) {
    return
  }

  const confirmed = window.confirm('Delete this failed story?')
  if (!confirmed) {
    return
  }

  await storiesStore.deleteStory(story.value.id)
  await router.push({ name: 'dashboard' })
}

watch(
  storyId,
  (nextStoryId, previousStoryId) => {
    if (previousStoryId) {
      storiesStore.stopGenerationPolling(previousStoryId)
    }

    if (nextStoryId) {
      loadStory(nextStoryId)
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  if (storyId.value) {
    storiesStore.stopGenerationPolling(storyId.value)
  }
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
            {{ childName }}’s story updates here as generation progresses.
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

          <div class="flex flex-wrap gap-2">
            <span class="status-pill" :class="statusTone(story.status)">
              {{ statusLabel(story.status) }}
            </span>
            <span v-if="story.art_style" class="status-pill bg-[var(--app-accent-soft)] text-[var(--app-accent-strong)]">
              {{ story.art_style }}
            </span>
          </div>
        </div>

        <div
          v-if="story.latest_error_message"
          class="mt-5 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          {{ story.latest_error_message }}
        </div>

        <div v-if="story.status === 'generating'" class="mt-8 space-y-5">
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

        <div v-else-if="story.pages.length > 0" class="mt-8 grid gap-4 md:grid-cols-2">
          <article v-for="page in story.pages" :key="page.id" class="surface-card-muted px-5 py-5">
            <div class="flex items-center justify-between gap-3">
              <p class="page-kicker">Page {{ page.page_number }}</p>
              <span class="status-pill bg-amber-100 text-amber-700">Text Ready</span>
            </div>

            <p class="story-page-text mt-4 text-[var(--app-ink)]">
              {{ page.text_content }}
            </p>

            <div class="story-illustration-placeholder mt-5">
              Illustration will appear here in the next phase.
            </div>

            <p class="mt-4 text-sm leading-6 text-[var(--app-muted)]">
              Audio narration is planned for phase 11.
            </p>
          </article>
        </div>

        <div v-else-if="story.status === 'failed'" class="mt-8 empty-panel px-6 py-10 text-center">
          <p class="text-lg font-semibold text-[var(--app-ink)]">Story generation failed</p>
          <p class="mx-auto mt-3 max-w-xl text-sm leading-6 text-[var(--app-muted)]">
            The story record is still saved. Review the error above and retry once the text worker is healthy again.
          </p>
          <button
            type="button"
            class="secondary-button mt-6 border-red-200 text-[var(--app-danger)] hover:border-red-300 hover:bg-red-50"
            :disabled="storiesStore.isLoading"
            @click="handleDeleteStory"
          >
            Delete failed story
          </button>
        </div>
      </section>
    </div>
  </main>
</template>

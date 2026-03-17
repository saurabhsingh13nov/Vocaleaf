<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { useAuth } from '@/composables/useAuth'
import { useChildrenStore } from '@/stores/children'
import { useStoriesStore } from '@/stores/stories'
import { useSubscriptionStore } from '@/stores/subscription'
import { useVoiceStore } from '@/stores/voice'

const auth = useAuth()
const router = useRouter()
const childrenStore = useChildrenStore()
const storiesStore = useStoriesStore()
const subscriptionStore = useSubscriptionStore()
const voiceStore = useVoiceStore()

const selectedChildId = ref('')
const prompt = ref('')
const theme = ref('')
const pageCount = ref(6)
const artStyle = ref('')
const readingLevel = ref('')
const language = ref('en')
const selectedVoiceProfileId = ref('')
const localError = ref<string | null>(null)

const themeOptions = ['Adventure', 'Bedtime', 'Friendship', 'Animals', 'Space', 'Fantasy', 'Nature', 'Ocean']
const artStyleOptions = ['Watercolor', 'Storybook Classic', 'Modern Illustration', 'Whimsical', 'Dreamy']
const readingLevelOptions = ['Preschool', 'Early Reader', 'Independent Reader']
const isElevated = computed(() => auth.user.value?.role === 'staff' || auth.user.value?.role === 'admin')
const roleLabel = computed(() => auth.user.value?.role ?? 'customer')
const pageCountOptions = computed(() => {
  if (isElevated.value) {
    return []
  }
  const max = subscriptionStore.maxPagesPerStory ?? 10
  return Array.from({ length: Math.max(max - 1, 1) }, (_, index) => index + 2)
})
const storyUsage = computed(() => subscriptionStore.metric('stories_created'))

const readyVoiceProfiles = computed(() =>
  voiceStore.profiles.filter((profile) => profile.status === 'ready'),
)

onMounted(async () => {
  localError.value = null

  await Promise.allSettled([
    childrenStore.fetchChildren(),
    subscriptionStore.fetchSummary(),
    voiceStore.fetchProfiles(),
  ])

  if (!selectedChildId.value && childrenStore.children[0]) {
    selectedChildId.value = childrenStore.children[0].id
  }
})

watch(pageCountOptions, (options) => {
  if (options.length && !options.includes(pageCount.value)) {
    pageCount.value = options[options.length - 1] ?? 6
  }
})

async function handleSubmit() {
  localError.value = null

  if (!selectedChildId.value) {
    localError.value = 'Select a child profile before creating a story.'
    return
  }

  if (!prompt.value.trim() && !theme.value.trim()) {
    localError.value = 'Add a story prompt or choose a theme before continuing.'
    return
  }

  if (pageCount.value < 2) {
    localError.value = 'Stories must have at least 2 pages.'
    return
  }

  const story = await storiesStore.createStory({
    child_id: selectedChildId.value,
    voice_profile_id: selectedVoiceProfileId.value || null,
    prompt: prompt.value.trim() || null,
    theme: theme.value.trim() || null,
    target_page_count: pageCount.value,
    reading_level: readingLevel.value || null,
    art_style: artStyle.value || null,
    language: language.value.trim() || 'en',
  })

  await router.push({ name: 'story-detail', params: { storyId: story.id } })
}
</script>

<template>
  <main class="min-h-screen px-4 py-6 sm:px-6 sm:py-8">
    <div class="app-shell space-y-6">
      <div class="page-header">
        <div>
          <p class="page-kicker">Create</p>
          <h1 class="page-title">New Story</h1>
          <p class="page-subtitle">
            Choose a child, shape the creative direction, and let the text worker build a page-by-page draft.
          </p>
        </div>

        <RouterLink :to="{ name: 'dashboard' }" class="nav-link">&larr; Dashboard</RouterLink>
      </div>

      <form class="surface-card px-6 py-6 sm:px-8" @submit.prevent="handleSubmit">
        <div
          v-if="subscriptionStore.summary"
          class="mb-6 rounded-[28px] border border-[var(--app-border)] bg-[var(--app-surface-muted)] px-5 py-4"
        >
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p class="page-kicker">Current plan</p>
              <p class="mt-1 text-lg font-semibold capitalize text-[var(--app-ink)]">
                {{ subscriptionStore.summary.plan.name }}
              </p>
              <p class="mt-2 text-sm font-medium uppercase tracking-[0.18em] text-[var(--app-accent-strong)]">
                Role: {{ roleLabel }}
              </p>
            </div>
            <RouterLink :to="{ name: 'subscription' }" class="nav-link">View full usage</RouterLink>
          </div>
          <p v-if="isElevated" class="mt-3 text-sm text-[var(--app-muted)]">
            This {{ roleLabel }} account is unrestricted for story and narration limits.
          </p>
          <p v-else class="mt-3 text-sm text-[var(--app-muted)]">
            {{ storyUsage?.remaining ?? 0 }} story credit<span v-if="storyUsage?.remaining !== 1">s</span> remaining this period.
            Stories on this plan can be up to {{ subscriptionStore.summary.plan.max_pages_per_story ?? 'unlimited' }} pages.
          </p>
        </div>

        <div class="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <section class="space-y-5">
            <label class="block">
              <span class="field-label">Child profile</span>
              <select v-model="selectedChildId" class="field-input" name="child_id" required>
                <option disabled value="">Select a child</option>
                <option v-for="child in childrenStore.children" :key="child.id" :value="child.id">
                  {{ child.age !== null ? `${child.name} · Age ${child.age}` : child.name }}
                </option>
              </select>
            </label>

            <label class="block">
              <span class="field-label">Story prompt</span>
              <textarea
                v-model="prompt"
                class="field-input min-h-40"
                name="prompt"
                maxlength="2000"
                placeholder="A calm moonlit adventure through the forest with a brave fox and a hidden lantern trail..."
              />
            </label>

            <div>
              <p class="field-label">Theme</p>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="option in themeOptions"
                  :key="option"
                  type="button"
                  class="theme-pill"
                  :class="{ 'theme-pill-active': theme === option }"
                  @click="theme = theme === option ? '' : option"
                >
                  {{ option }}
                </button>
              </div>
            </div>
          </section>

          <section class="space-y-5">
            <div>
              <p class="field-label">Art style</p>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="option in artStyleOptions"
                  :key="option"
                  type="button"
                  class="theme-pill"
                  :class="{ 'theme-pill-active': artStyle === option }"
                  @click="artStyle = artStyle === option ? '' : option"
                >
                  {{ option }}
                </button>
              </div>
            </div>

            <div>
              <p class="field-label">Page count</p>
              <div v-if="!isElevated" class="flex flex-wrap gap-2">
                <button
                  v-for="count in pageCountOptions"
                  :key="count"
                  type="button"
                  class="theme-pill"
                  :class="{ 'theme-pill-active': pageCount === count }"
                  @click="pageCount = count"
                >
                  {{ count }}
                </button>
              </div>
              <div v-else class="space-y-2">
                <input
                  v-model.number="pageCount"
                  class="field-input"
                  min="2"
                  name="target_page_count"
                  step="1"
                  type="number"
                />
                <p class="text-sm text-[var(--app-muted)]">
                  Elevated accounts can choose any page count of 2 or more.
                </p>
              </div>
            </div>

            <label class="block">
              <span class="field-label">Reading level</span>
              <select v-model="readingLevel" class="field-input" name="reading_level">
                <option value="">Choose a reading level</option>
                <option v-for="option in readingLevelOptions" :key="option" :value="option">
                  {{ option }}
                </option>
              </select>
            </label>

            <label class="block">
              <span class="field-label">Language</span>
              <input
                v-model="language"
                class="field-input"
                maxlength="10"
                name="language"
                placeholder="en"
              />
            </label>

            <label v-if="readyVoiceProfiles.length > 0" class="block">
              <span class="field-label">Narration voice</span>
              <select v-model="selectedVoiceProfileId" class="field-input" name="voice_profile_id">
                <option value="">No narration voice yet</option>
                <option v-for="profile in readyVoiceProfiles" :key="profile.id" :value="profile.id">
                  {{ profile.display_name }}
                </option>
              </select>
            </label>
          </section>
        </div>

        <div
          v-if="localError || storiesStore.error || childrenStore.error || voiceStore.error"
          class="mt-6 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
          role="alert"
        >
          {{ localError || storiesStore.error || childrenStore.error || voiceStore.error }}
        </div>

        <div class="mt-6 flex flex-wrap items-center gap-3">
          <button
            type="submit"
            class="primary-button"
            :disabled="storiesStore.isLoading || childrenStore.isLoading || !childrenStore.children.length || (!isElevated && storyUsage?.remaining === 0)"
          >
            Create Story
          </button>
          <p class="text-sm text-[var(--app-muted)]">
            The request saves immediately and generation continues in the background.
          </p>
        </div>
      </form>
    </div>
  </main>
</template>

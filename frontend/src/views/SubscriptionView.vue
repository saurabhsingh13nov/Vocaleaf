<script setup lang="ts">
import { computed, onMounted } from 'vue'

import { useAuth } from '@/composables/useAuth'
import { useSubscriptionStore } from '@/stores/subscription'
import type { UsageMetric } from '@/services/subscription'

const auth = useAuth()
const subscriptionStore = useSubscriptionStore()
const isElevated = computed(() => auth.user.value?.role === 'staff' || auth.user.value?.role === 'admin')
const roleLabel = computed(() => auth.user.value?.role ?? 'customer')

const usageEntries = computed(() => {
  const summary = subscriptionStore.summary
  if (!summary) {
    return []
  }

  const usageTypes: Array<[string, string]> = [
    ['stories_created', 'Stories created'],
    ['voice_clones_created', 'Voice clones'],
    ['audio_chars_synthesized', 'Narration characters'],
    ['images_generated', 'Images generated'],
  ]

  return usageTypes.map(([usageType, label]) => ({
    label,
    metric: summary.usage[usageType],
  })).filter((entry): entry is { label: string; metric: UsageMetric } => entry.metric !== undefined)
})

onMounted(() => {
  if (!subscriptionStore.summary) {
    subscriptionStore.fetchSummary().catch(() => undefined)
  }
})

function usageCopy(used: number, limit: number | null, unit: string) {
  if (limit === null) {
    return `${used} ${unit}${used === 1 ? '' : 's'} used this period`
  }

  return `${used} of ${limit} ${unit}${limit === 1 ? '' : 's'} used`
}
</script>

<template>
  <main class="min-h-screen px-4 py-6 sm:px-6 sm:py-8">
    <div class="app-shell space-y-6">
      <div class="page-header">
        <div>
          <p class="page-kicker">Plan</p>
          <h1 class="page-title">Subscription & Usage</h1>
          <p class="page-subtitle">
            Review the current plan, active period, and metered usage that powers story, voice, and narration limits.
          </p>
        </div>

        <RouterLink :to="{ name: 'dashboard' }" class="nav-link">&larr; Dashboard</RouterLink>
      </div>

      <div v-if="subscriptionStore.isLoading && !subscriptionStore.summary" class="py-12 text-center text-[var(--app-muted)]">
        Loading…
      </div>

      <div
        v-else-if="subscriptionStore.error && !subscriptionStore.summary"
        class="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        role="alert"
      >
        {{ subscriptionStore.error }}
      </div>

      <template v-else-if="subscriptionStore.summary">
        <section class="surface-card grid gap-6 px-6 py-6 sm:px-8 lg:grid-cols-[1fr_0.9fr]">
          <div>
            <p class="page-kicker">Current plan</p>
            <h2 class="mt-2 text-4xl font-semibold capitalize text-[var(--app-ink)]">
              {{ subscriptionStore.summary.plan.name }}
            </h2>
            <p class="mt-3 text-sm font-medium uppercase tracking-[0.18em] text-[var(--app-accent-strong)]">
              Role: {{ roleLabel }}
            </p>
            <p class="mt-3 text-sm leading-6 text-[var(--app-muted)]">
              Active through
              {{ subscriptionStore.summary.current_period_end ? new Date(subscriptionStore.summary.current_period_end).toLocaleDateString() : 'an open-ended period' }}.
            </p>
            <p v-if="isElevated" class="mt-3 text-sm leading-6 text-[var(--app-muted)]">
              This account is unrestricted for story and usage limits because it uses an elevated internal role.
            </p>
          </div>

          <div class="grid gap-3 sm:grid-cols-2">
            <div class="rounded-[28px] border border-[var(--app-border)] bg-white/80 px-4 py-4">
              <p class="text-xs uppercase tracking-[0.22em] text-[var(--app-muted)]">Stories / month</p>
              <p class="mt-2 text-3xl font-semibold text-[var(--app-ink)]">
                {{ subscriptionStore.summary.plan.monthly_story_limit ?? 'Unlimited' }}
              </p>
            </div>
            <div class="rounded-[28px] border border-[var(--app-border)] bg-white/80 px-4 py-4">
              <p class="text-xs uppercase tracking-[0.22em] text-[var(--app-muted)]">Max pages / story</p>
              <p class="mt-2 text-3xl font-semibold text-[var(--app-ink)]">
                {{ subscriptionStore.summary.plan.max_pages_per_story ?? 'Unlimited' }}
              </p>
            </div>
            <div class="rounded-[28px] border border-[var(--app-border)] bg-white/80 px-4 py-4">
              <p class="text-xs uppercase tracking-[0.22em] text-[var(--app-muted)]">Voice clones / month</p>
              <p class="mt-2 text-3xl font-semibold text-[var(--app-ink)]">
                {{ subscriptionStore.summary.plan.voice_clone_limit ?? 'Unlimited' }}
              </p>
            </div>
            <div class="rounded-[28px] border border-[var(--app-border)] bg-white/80 px-4 py-4">
              <p class="text-xs uppercase tracking-[0.22em] text-[var(--app-muted)]">Narration chars / month</p>
              <p class="mt-2 text-3xl font-semibold text-[var(--app-ink)]">
                {{ subscriptionStore.summary.plan.monthly_audio_chars_limit ?? 'Unlimited' }}
              </p>
            </div>
          </div>
        </section>

        <section class="grid gap-4 lg:grid-cols-2">
          <article
            v-for="entry in usageEntries"
            :key="entry.label"
            class="surface-card px-6 py-6 sm:px-7"
          >
            <p class="page-kicker">Usage</p>
            <h2 class="mt-2 text-2xl font-semibold text-[var(--app-ink)]">{{ entry.label }}</h2>
            <p class="mt-3 text-sm leading-6 text-[var(--app-muted)]">
              {{ usageCopy(entry.metric.used, entry.metric.limit, entry.metric.unit) }}
            </p>
            <p v-if="!isElevated && entry.metric.remaining !== null" class="mt-4 text-sm font-medium text-[var(--app-accent-strong)]">
              {{ entry.metric.remaining }} remaining this period
            </p>
            <p v-else-if="isElevated" class="mt-4 text-sm font-medium text-[var(--app-accent-strong)]">
              No limit applies for the {{ roleLabel }} role.
            </p>
          </article>
        </section>
      </template>
    </div>
  </main>
</template>

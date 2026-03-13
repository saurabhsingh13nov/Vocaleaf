<script setup lang="ts">
import type { VoiceSample } from '@/services/voice'

defineProps<{
  samples: VoiceSample[]
  isLoading?: boolean
}>()

defineEmits<{
  delete: [sampleId: string]
}>()

function formatDuration(durationSeconds: number | null) {
  if (!durationSeconds) {
    return 'Unknown duration'
  }

  return `${durationSeconds.toFixed(1)} sec`
}

function formatDate(value: string) {
  return new Date(value).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function sampleStatusTone(status: VoiceSample['status']) {
  if (status === 'accepted') {
    return 'bg-emerald-100 text-emerald-700'
  }

  if (status === 'rejected') {
    return 'bg-red-100 text-red-700'
  }

  if (status === 'processing') {
    return 'bg-amber-100 text-amber-700'
  }

  return 'bg-stone-200 text-stone-700'
}
</script>

<template>
  <div class="rounded-[1.5rem] border border-[var(--app-border)] bg-[rgba(255,253,249,0.76)] p-4">
    <div class="flex items-center justify-between gap-3">
      <div>
        <p class="page-kicker">Samples</p>
        <p class="mt-2 text-sm leading-6 text-[var(--app-muted)]">
          Raw uploads stay private and are not playable here.
        </p>
      </div>
      <p class="text-sm font-medium text-[var(--app-muted)]">{{ samples.length }} total</p>
    </div>

    <div v-if="samples.length === 0" class="empty-panel mt-4 px-4 py-5 text-sm text-[var(--app-muted)]">
      No samples uploaded yet.
    </div>

    <ul v-else class="mt-4 space-y-3">
      <li
        v-for="sample in samples"
        :key="sample.id"
        class="rounded-[1.25rem] border border-[var(--app-border)] bg-[var(--app-surface-strong)] px-4 py-4"
      >
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p class="text-sm font-semibold text-[var(--app-ink)]">{{ formatDuration(sample.duration_seconds) }}</p>
            <p class="mt-2 text-xs uppercase tracking-[0.18em] text-[var(--app-muted-soft)]">
              Added {{ formatDate(sample.created_at) }}
            </p>
          </div>

          <div class="flex items-center gap-2">
            <span class="status-pill" :class="sampleStatusTone(sample.status)">
              {{ sample.status }}
            </span>
            <button
              type="button"
              class="secondary-button !px-3 !py-2 border-red-200 text-[var(--app-danger)] hover:border-red-300 hover:bg-red-50"
              :disabled="isLoading"
              @click="$emit('delete', sample.id)"
            >
              Delete
            </button>
          </div>
        </div>
      </li>
    </ul>
  </div>
</template>

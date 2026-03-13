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
</script>

<template>
  <div class="rounded-2xl border border-stone-200 bg-stone-50 p-4">
    <div class="flex items-center justify-between gap-3">
      <div>
        <p class="text-xs font-semibold uppercase tracking-[0.3em] text-stone-500">Samples</p>
        <p class="mt-1 text-sm text-stone-600">Raw uploads stay private and are not playable here.</p>
      </div>
      <p class="text-sm font-medium text-stone-500">{{ samples.length }} total</p>
    </div>

    <div v-if="samples.length === 0" class="mt-4 rounded-xl border border-dashed border-stone-300 bg-white px-4 py-5 text-sm text-stone-500">
      No samples uploaded yet.
    </div>

    <ul v-else class="mt-4 space-y-3">
      <li
        v-for="sample in samples"
        :key="sample.id"
        class="rounded-xl bg-white px-4 py-3 shadow-sm ring-1 ring-stone-200"
      >
        <div class="flex flex-wrap items-center justify-between gap-2">
          <p class="text-sm font-semibold text-stone-900">{{ formatDuration(sample.duration_seconds) }}</p>
          <div class="flex items-center gap-2">
            <span class="rounded-full bg-stone-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-stone-600">
              {{ sample.status }}
            </span>
            <button
              type="button"
              class="rounded-full border border-red-200 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-red-600 transition hover:border-red-300 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="isLoading"
              @click="$emit('delete', sample.id)"
            >
              Delete
            </button>
          </div>
        </div>
        <p class="mt-2 text-xs text-stone-500">Added {{ formatDate(sample.created_at) }}</p>
      </li>
    </ul>
  </div>
</template>

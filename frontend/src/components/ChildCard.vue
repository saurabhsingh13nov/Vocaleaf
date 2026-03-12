<script setup lang="ts">
import type { Child } from '@/services/children'

defineProps<{
  child: Child
}>()

defineEmits<{
  edit: [child: Child]
  delete: [child: Child]
}>()
</script>

<template>
  <div class="rounded-2xl border border-stone-200 bg-white p-6 shadow-sm">
    <div class="flex items-start justify-between">
      <div>
        <h3 class="text-lg font-semibold text-stone-900">{{ child.name }}</h3>
        <p v-if="child.age !== null" class="mt-1 text-sm text-stone-500">
          Age {{ child.age }}
        </p>
      </div>

      <div class="flex gap-2">
        <button
          type="button"
          class="rounded-lg px-3 py-1.5 text-sm font-medium text-stone-600 transition hover:bg-stone-100"
          @click="$emit('edit', child)"
        >
          Edit
        </button>
        <button
          type="button"
          class="rounded-lg px-3 py-1.5 text-sm font-medium text-red-600 transition hover:bg-red-50"
          @click="$emit('delete', child)"
        >
          Delete
        </button>
      </div>
    </div>

    <p class="mt-4 text-xs text-stone-400">
      Added {{ new Date(child.created_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) }}
    </p>
  </div>
</template>

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
  <article class="surface-card px-6 py-5 sm:px-7">
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <p class="page-kicker">Child profile</p>
        <h3 class="mt-2 text-3xl font-semibold text-[var(--app-ink)]">{{ child.name }}</h3>
        <p v-if="child.age !== null" class="mt-3 text-sm text-[var(--app-muted)]">Age {{ child.age }}</p>
      </div>

      <div class="flex flex-wrap gap-3">
        <button type="button" class="secondary-button" @click="$emit('edit', child)">Edit</button>
        <button
          type="button"
          class="secondary-button border-red-200 text-[var(--app-danger)] hover:border-red-300 hover:bg-red-50"
          @click="$emit('delete', child)"
        >
          Delete
        </button>
      </div>
    </div>

    <p class="mt-5 text-xs uppercase tracking-[0.18em] text-[var(--app-muted-soft)]">
      Added {{ new Date(child.created_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) }}
    </p>
  </article>
</template>

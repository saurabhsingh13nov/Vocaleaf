<script setup lang="ts">
import { reactive } from 'vue'

import type { Child } from '@/services/children'

const props = defineProps<{
  child?: Child | null
}>()

defineEmits<{
  save: [data: { name: string; age: number | null }]
  cancel: []
}>()

const form = reactive({
  name: props.child?.name ?? '',
  age: (props.child?.age ?? null) as number | null,
})

const isEdit = !!props.child
</script>

<template>
  <div class="surface-card px-6 py-6 sm:px-8">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <p class="page-kicker">{{ isEdit ? 'Edit profile' : 'New profile' }}</p>
        <h2 class="mt-2 text-3xl font-semibold text-[var(--app-ink)]">
          {{ isEdit ? 'Edit Child' : 'Add Child' }}
        </h2>
      </div>
    </div>

    <form class="mt-6 space-y-5" @submit.prevent="$emit('save', { name: form.name, age: form.age })">
      <label>
        <span class="field-label">Name <span class="text-red-500">*</span></span>
        <input
          id="child-name"
          v-model="form.name"
          name="name"
          type="text"
          required
          maxlength="100"
          class="field-input"
          placeholder="Child's name"
        />
      </label>

      <label>
        <span class="field-label">Age</span>
        <input
          id="child-age"
          v-model.number="form.age"
          name="age"
          type="number"
          min="0"
          max="17"
          class="field-input"
          placeholder="Age (optional)"
        />
      </label>

      <div class="flex flex-col gap-3 pt-2 sm:flex-row">
        <button type="submit" :disabled="!form.name.trim()" class="primary-button">
          {{ isEdit ? 'Save Changes' : 'Add Child' }}
        </button>
        <button type="button" class="secondary-button" @click="$emit('cancel')">Cancel</button>
      </div>
    </form>
  </div>
</template>

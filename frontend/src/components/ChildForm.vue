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
  age: props.child?.age ?? null as number | null,
})

const isEdit = !!props.child
</script>

<template>
  <div class="rounded-2xl border border-stone-200 bg-white p-6 shadow-sm">
    <h3 class="text-lg font-semibold text-stone-900">
      {{ isEdit ? 'Edit Child' : 'Add Child' }}
    </h3>

    <form
      class="mt-4 space-y-4"
      @submit.prevent="$emit('save', { name: form.name, age: form.age })"
    >
      <div>
        <label for="child-name" class="block text-sm font-medium text-stone-700">
          Name <span class="text-red-500">*</span>
        </label>
        <input
          id="child-name"
          v-model="form.name"
          name="name"
          type="text"
          required
          maxlength="100"
          class="mt-1 block w-full rounded-lg border border-stone-300 px-3 py-2 text-sm shadow-sm focus:border-rose-500 focus:outline-none focus:ring-1 focus:ring-rose-500"
          placeholder="Child's name"
        />
      </div>

      <div>
        <label for="child-age" class="block text-sm font-medium text-stone-700">
          Age
        </label>
        <input
          id="child-age"
          v-model.number="form.age"
          name="age"
          type="number"
          min="0"
          max="17"
          class="mt-1 block w-full rounded-lg border border-stone-300 px-3 py-2 text-sm shadow-sm focus:border-rose-500 focus:outline-none focus:ring-1 focus:ring-rose-500"
          placeholder="Age (optional)"
        />
      </div>

      <div class="flex gap-3 pt-2">
        <button
          type="submit"
          :disabled="!form.name.trim()"
          class="rounded-lg bg-rose-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-rose-600 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {{ isEdit ? 'Save Changes' : 'Add Child' }}
        </button>
        <button
          type="button"
          class="rounded-lg px-4 py-2 text-sm font-medium text-stone-600 transition hover:bg-stone-100"
          @click="$emit('cancel')"
        >
          Cancel
        </button>
      </div>
    </form>
  </div>
</template>

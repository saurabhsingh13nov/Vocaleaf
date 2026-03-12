<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useChildrenStore } from '@/stores/children'
import type { Child } from '@/services/children'
import ChildCard from '@/components/ChildCard.vue'
import ChildForm from '@/components/ChildForm.vue'

const store = useChildrenStore()

const showForm = ref(false)
const editingChild = ref<Child | null>(null)

onMounted(() => {
  store.fetchChildren()
})

function openCreate() {
  editingChild.value = null
  showForm.value = true
}

function openEdit(child: Child) {
  editingChild.value = child
  showForm.value = true
}

async function handleSave(data: { name: string; age: number | null }) {
  if (editingChild.value) {
    await store.updateChild(editingChild.value.id, data)
  } else {
    await store.createChild(data)
  }
  showForm.value = false
  editingChild.value = null
}

async function handleDelete(child: Child) {
  await store.deleteChild(child.id)
}

function handleCancel() {
  showForm.value = false
  editingChild.value = null
}
</script>

<template>
  <main class="min-h-screen bg-[linear-gradient(180deg,#f6f0ff_0%,#fff8f1_42%,#fffdf8_100%)] px-6 py-10">
    <div class="mx-auto max-w-3xl space-y-6">
      <div class="flex items-center justify-between">
        <div>
          <p class="text-xs font-semibold uppercase tracking-[0.35em] text-rose-600">Profiles</p>
          <h1 class="mt-2 text-3xl font-semibold text-stone-950">Children</h1>
        </div>

        <RouterLink
          :to="{ name: 'dashboard' }"
          class="text-sm font-medium text-stone-500 transition hover:text-stone-700"
        >
          &larr; Dashboard
        </RouterLink>
      </div>

      <!-- Error -->
      <div
        v-if="store.error"
        class="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        role="alert"
      >
        {{ store.error }}
      </div>

      <!-- Loading -->
      <div v-if="store.isLoading && store.children.length === 0" class="py-12 text-center text-stone-400">
        Loading…
      </div>

      <!-- Form -->
      <ChildForm
        v-if="showForm"
        :child="editingChild"
        @save="handleSave"
        @cancel="handleCancel"
      />

      <!-- Empty state -->
      <div
        v-if="!store.isLoading && store.children.length === 0 && !showForm"
        class="rounded-2xl border border-dashed border-stone-300 bg-white px-6 py-12 text-center"
      >
        <p class="text-stone-500">No child profiles yet.</p>
        <button
          type="button"
          class="mt-4 rounded-lg bg-rose-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-rose-600"
          @click="openCreate"
        >
          Add your first child
        </button>
      </div>

      <!-- Child list -->
      <template v-if="store.children.length > 0">
        <button
          v-if="!showForm"
          type="button"
          class="rounded-lg bg-rose-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-rose-600"
          @click="openCreate"
        >
          Add Child
        </button>

        <div class="space-y-4">
          <ChildCard
            v-for="child in store.children"
            :key="child.id"
            :child="child"
            @edit="openEdit"
            @delete="handleDelete"
          />
        </div>
      </template>
    </div>
  </main>
</template>

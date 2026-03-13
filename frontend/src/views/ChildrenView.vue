<script setup lang="ts">
import { onMounted, ref } from 'vue'

import type { Child } from '@/services/children'
import { useChildrenStore } from '@/stores/children'
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
  <main class="min-h-screen px-4 py-6 sm:px-6 sm:py-8">
    <div class="app-shell space-y-6">
      <div class="page-header">
        <div>
          <p class="page-kicker">Profiles</p>
          <h1 class="page-title">Children</h1>
          <p class="page-subtitle">
            Keep profile details concise and editable so the story pipeline can later personalize themes, pacing, and narration.
          </p>
        </div>

        <div class="flex flex-wrap items-center gap-3">
          <button v-if="!showForm" type="button" class="primary-button" @click="openCreate">
            {{ store.children.length === 0 ? 'Add your first child' : 'Add Child' }}
          </button>
          <RouterLink :to="{ name: 'dashboard' }" class="nav-link">&larr; Dashboard</RouterLink>
        </div>
      </div>

      <div
        v-if="store.error"
        class="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        role="alert"
      >
        {{ store.error }}
      </div>

      <div v-if="store.isLoading && store.children.length === 0" class="py-12 text-center text-[var(--app-muted)]">
        Loading…
      </div>

      <ChildForm v-if="showForm" :child="editingChild" @save="handleSave" @cancel="handleCancel" />

      <div
        v-if="!store.isLoading && store.children.length === 0 && !showForm"
        class="empty-panel px-6 py-12 text-center"
      >
        <p class="text-base font-medium text-[var(--app-ink)]">No child profiles yet.</p>
        <p class="mx-auto mt-3 max-w-md text-sm leading-6 text-[var(--app-muted)]">
          Add a profile now so story prompts have age and family context available when generation arrives.
        </p>
        <button type="button" class="primary-button mt-6" @click="openCreate">Add your first child</button>
      </div>

      <template v-if="store.children.length > 0">
        <div class="grid gap-4">
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

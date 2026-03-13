<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'

const props = withDefaults(defineProps<{
  title: string
  message: string
  confirmLabel?: string
  pendingConfirmLabel?: string
  warningText?: string | null
  isPending: boolean
}>(), {
  confirmLabel: 'Delete',
  pendingConfirmLabel: 'Deleting...',
  warningText: null,
})

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()

function handleCancel() {
  if (!props.isPending) {
    emit('cancel')
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    handleCancel()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div class="modal-overlay" @click.self="handleCancel">
        <div
          class="modal-panel"
          role="dialog"
          aria-modal="true"
          aria-labelledby="confirm-modal-title"
        >
          <div class="mb-5 flex h-10 w-10 items-center justify-center rounded-full bg-red-100">
            <svg class="h-5 w-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
            </svg>
          </div>

          <h3 id="confirm-modal-title" class="text-lg font-semibold text-[var(--app-ink)]">
            {{ title }}
          </h3>

          <p class="mt-2 text-sm leading-6 text-[var(--app-muted)]">
            {{ message }}
          </p>

          <p
            v-if="warningText"
            class="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-xs font-medium text-amber-700"
          >
            {{ warningText }}
          </p>

          <div class="mt-6 flex items-center justify-end gap-3">
            <button
              type="button"
              class="secondary-button"
              data-testid="confirm-modal-cancel"
              :disabled="isPending"
              @click="handleCancel"
            >
              Cancel
            </button>
            <button
              type="button"
              class="rounded-2xl border border-red-200 bg-red-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-red-700 disabled:opacity-50"
              data-testid="confirm-modal-confirm"
              :disabled="isPending"
              @click="emit('confirm')"
            >
              {{ isPending ? pendingConfirmLabel : confirmLabel }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

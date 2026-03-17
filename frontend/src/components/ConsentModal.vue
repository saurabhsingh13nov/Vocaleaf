<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

interface ConsentLink {
  label: string
  href: string
}

const props = withDefaults(defineProps<{
  title: string
  message: string
  confirmationLabel: string
  confirmLabel?: string
  pendingConfirmLabel?: string
  dismissible?: boolean
  isPending: boolean
  links?: ConsentLink[]
}>(), {
  confirmLabel: 'Confirm',
  pendingConfirmLabel: 'Saving...',
  dismissible: true,
  links: () => [],
})

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()

const isConfirmed = ref(false)

watch(
  () => props.isPending,
  (pending) => {
    if (!pending) {
      isConfirmed.value = false
    }
  },
)

function handleCancel() {
  if (props.dismissible && !props.isPending) {
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
          aria-labelledby="consent-modal-title"
        >
          <div class="mb-5 flex h-10 w-10 items-center justify-center rounded-full bg-[var(--app-accent-soft)] text-[var(--app-accent-strong)]">
            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke-width="1.7" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-1.5 0h12a1.5 1.5 0 0 1 1.5 1.5v7.5A1.5 1.5 0 0 1 18 21h-12A1.5 1.5 0 0 1 4.5 19.5V12A1.5 1.5 0 0 1 6 10.5Z" />
            </svg>
          </div>

          <h3 id="consent-modal-title" class="text-lg font-semibold text-[var(--app-ink)]">
            {{ title }}
          </h3>

          <p class="mt-2 text-sm leading-6 text-[var(--app-muted)]">
            {{ message }}
          </p>

          <div v-if="links.length" class="mt-4 flex flex-wrap gap-3 text-sm">
            <a
              v-for="link in links"
              :key="link.href"
              :href="link.href"
              target="_blank"
              rel="noreferrer"
              class="nav-link"
            >
              {{ link.label }}
            </a>
          </div>

          <label class="field-checkbox mt-5 flex items-start gap-3 rounded-2xl border border-[var(--app-border)] px-4 py-4 text-sm leading-6 text-[var(--app-muted)]">
            <input
              v-model="isConfirmed"
              type="checkbox"
              class="mt-1 size-4 rounded border-[var(--app-border-strong)] text-[var(--app-accent)] focus:ring-[var(--app-accent)]"
            />
            <span>{{ confirmationLabel }}</span>
          </label>

          <div class="mt-6 flex items-center justify-end gap-3">
            <button
              v-if="dismissible"
              type="button"
              class="secondary-button"
              :disabled="isPending"
              @click="handleCancel"
            >
              Cancel
            </button>
            <button
              type="button"
              class="primary-button"
              :disabled="isPending || !isConfirmed"
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

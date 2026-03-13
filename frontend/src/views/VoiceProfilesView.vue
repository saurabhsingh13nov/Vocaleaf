<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

import VoiceRecorder from '@/components/VoiceRecorder.vue'
import VoiceSampleList from '@/components/VoiceSampleList.vue'
import type { VoiceProfile } from '@/services/voice'
import { useVoiceStore } from '@/stores/voice'

const store = useVoiceStore()

const displayName = ref('')
const consentConfirmed = ref(false)
const defaultForUser = ref(false)
const localError = ref<string | null>(null)

onMounted(() => {
  store.fetchProfiles()
})

onBeforeUnmount(() => {
  store.stopAllClonePolling()
})

async function handleCreateProfile() {
  localError.value = null

  if (!consentConfirmed.value) {
    localError.value = 'Consent is required before creating a voice profile.'
    return
  }

  await store.createProfile({
    display_name: displayName.value,
    consent_confirmed: consentConfirmed.value,
    default_for_user: defaultForUser.value,
  })

  displayName.value = ''
  consentConfirmed.value = false
  defaultForUser.value = false
}

async function handleUploadSample(
  profileId: string,
  payload: { file: Blob; mimeType: string; fileSizeBytes: number; durationSeconds: number },
) {
  await store.uploadSample(profileId, payload)
}

async function handleDeleteProfile(profileId: string) {
  const confirmed = window.confirm('Delete this voice profile and all of its samples?')
  if (!confirmed) {
    return
  }

  await store.deleteProfile(profileId)
}

async function handleDeleteSample(profileId: string, sampleId: string) {
  const confirmed = window.confirm('Delete this voice sample?')
  if (!confirmed) {
    return
  }

  await store.deleteSample(profileId, sampleId)
}

async function handleCloneProfile(profileId: string) {
  await store.cloneProfile(profileId)
}

function profileStatusTone(status: string) {
  switch (status) {
    case 'ready':
      return 'bg-emerald-100 text-emerald-700'
    case 'failed':
      return 'bg-red-100 text-red-700'
    case 'processing':
      return 'bg-amber-100 text-amber-700'
    default:
      return 'bg-stone-200 text-stone-700'
  }
}

function profileStatusLabel(status: string, sampleCount: number) {
  if (status === 'pending') {
    return sampleCount > 0 ? 'Awaiting clone' : 'Add samples'
  }

  if (status === 'processing') {
    return 'Cloning'
  }

  if (status === 'ready') {
    return 'Ready'
  }

  if (status === 'failed') {
    return 'Clone failed'
  }

  if (status === 'deleted') {
    return 'Deleted'
  }

  return status
}

function cloneableSampleCount(profile: VoiceProfile) {
  return profile.samples.filter((sample) => sample.status === 'uploaded' || sample.status === 'accepted').length
}

function canCloneProfile(profile: VoiceProfile) {
  return ['pending', 'failed'].includes(profile.status) && cloneableSampleCount(profile) > 0
}

function cloneButtonLabel(profile: VoiceProfile) {
  if (store.isCloningProfile(profile.id) || profile.status === 'processing') {
    return 'Cloning...'
  }

  if (profile.status === 'failed') {
    return 'Retry Clone'
  }

  return 'Clone Voice'
}
</script>

<template>
  <main class="min-h-screen px-4 py-6 sm:px-6 sm:py-8">
    <div class="app-shell space-y-6">
      <div class="page-header">
        <div>
          <p class="page-kicker">Narration</p>
          <h1 class="page-title">Voice Profiles</h1>
          <p class="page-subtitle">
            Build narration voices deliberately: create a profile, upload private samples, and trigger cloning only when the profile is ready.
          </p>
        </div>

        <RouterLink :to="{ name: 'dashboard' }" class="nav-link">&larr; Dashboard</RouterLink>
      </div>

      <section class="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <form class="surface-card px-6 py-6 sm:px-8" @submit.prevent="handleCreateProfile">
          <p class="page-kicker">Create</p>
          <h2 class="mt-2 text-3xl font-semibold text-[var(--app-ink)]">New narration voice</h2>
          <p class="mt-3 text-sm leading-6 text-[var(--app-muted)]">
            Create a private voice profile, then add recorded or uploaded audio samples for cloning.
          </p>

          <label class="mt-6 block" for="display_name">
            <span class="field-label">Profile name</span>
            <input
              id="display_name"
              v-model="displayName"
              name="display_name"
              type="text"
              required
              maxlength="100"
              class="field-input"
              placeholder="Bedtime Story Voice"
            />
          </label>

          <label class="field-checkbox mt-5 flex items-start gap-3 px-4 py-4 text-sm leading-6 text-[var(--app-muted)]">
            <input
              v-model="consentConfirmed"
              type="checkbox"
              class="mt-1 size-4 rounded border-[var(--app-border-strong)] text-[var(--app-accent)] focus:ring-[var(--app-accent)]"
            />
            <span>I confirm I have consent to clone and use this voice for narration.</span>
          </label>

          <label class="mt-4 flex items-center gap-3 text-sm text-[var(--app-muted)]">
            <input
              v-model="defaultForUser"
              type="checkbox"
              class="size-4 rounded border-[var(--app-border-strong)] text-[var(--app-accent)] focus:ring-[var(--app-accent)]"
            />
            <span>Set as my default narration voice when cloning is available.</span>
          </label>

          <div
            v-if="localError || store.error"
            class="mt-5 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
            role="alert"
          >
            {{ localError || store.error }}
          </div>

          <button type="submit" class="primary-button mt-6" :disabled="store.isLoading">
            Create voice profile
          </button>
        </form>

        <section class="surface-card-muted px-6 py-6 sm:px-8">
          <p class="page-kicker">Guidance</p>
          <h2 class="mt-2 text-3xl font-semibold text-[var(--app-ink)]">Sample checklist</h2>
          <ul class="mt-5 space-y-3 text-sm leading-6 text-[var(--app-muted)]">
            <li>Use a quiet room and keep the mic at a steady distance.</li>
            <li>Record your natural speaking voice instead of exaggerated character voices.</li>
            <li>Upload a few clean clips over time before triggering the clone.</li>
          </ul>

          <div class="mt-6 rounded-[1.25rem] border border-[var(--app-border)] bg-[rgba(255,253,249,0.82)] px-4 py-4">
            <p class="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--app-muted-soft)]">
              Phase 8 flow
            </p>
            <p class="mt-3 text-sm leading-6 text-[var(--app-muted)]">
              Upload samples first, then use <span class="font-semibold text-[var(--app-ink)]">Clone Voice</span> to start background processing. Status updates return to this screen automatically.
            </p>
          </div>
        </section>
      </section>

      <div v-if="store.isLoading && store.profiles.length === 0" class="py-12 text-center text-[var(--app-muted)]">
        Loading…
      </div>

      <div
        v-if="!store.isLoading && store.profiles.length === 0"
        class="empty-panel px-6 py-12 text-center"
      >
        <p class="text-base font-medium text-[var(--app-ink)]">No voice profiles yet.</p>
        <p class="mx-auto mt-3 max-w-md text-sm leading-6 text-[var(--app-muted)]">
          Create one profile now, then upload private samples to prepare a narration voice.
        </p>
      </div>

      <section v-else class="grid gap-4 xl:grid-cols-2">
        <article
          v-for="profile in store.profiles"
          :key="profile.id"
          class="surface-card px-6 py-6 sm:px-7"
        >
          <div class="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p class="page-kicker">Profile</p>
              <h2 class="mt-2 text-3xl font-semibold text-[var(--app-ink)]">{{ profile.display_name }}</h2>
              <p class="mt-3 text-sm text-[var(--app-muted)]">
                {{ profile.samples.length }} sample(s), {{ cloneableSampleCount(profile) }} ready for cloning
              </p>
            </div>

            <div class="flex flex-wrap items-center gap-2">
              <span class="status-pill" :class="profileStatusTone(profile.status)">
                {{ profileStatusLabel(profile.status, profile.samples.length) }}
              </span>
              <span
                v-if="profile.default_for_user"
                class="status-pill bg-[var(--app-accent-soft)] text-[var(--app-accent-strong)]"
              >
                default
              </span>
            </div>
          </div>

          <div class="mt-5 flex flex-wrap gap-3">
            <button
              v-if="profile.status !== 'ready'"
              type="button"
              class="primary-button"
              :disabled="!canCloneProfile(profile) || store.isCloningProfile(profile.id) || store.isLoading"
              @click="handleCloneProfile(profile.id)"
            >
              {{ cloneButtonLabel(profile) }}
            </button>
            <button
              type="button"
              class="secondary-button border-red-200 text-[var(--app-danger)] hover:border-red-300 hover:bg-red-50"
              :disabled="store.isLoading"
              @click="handleDeleteProfile(profile.id)"
            >
              Delete
            </button>
          </div>

          <div class="mt-6 space-y-4">
            <VoiceRecorder
              :is-uploading="store.isLoading"
              @submit="(payload) => handleUploadSample(profile.id, payload)"
            />
            <VoiceSampleList
              :samples="profile.samples"
              :is-loading="store.isLoading"
              @delete="(sampleId) => handleDeleteSample(profile.id, sampleId)"
            />
          </div>
        </article>
      </section>
    </div>
  </main>
</template>

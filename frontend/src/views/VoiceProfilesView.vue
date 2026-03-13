<script setup lang="ts">
import { onMounted, ref } from 'vue'

import VoiceRecorder from '@/components/VoiceRecorder.vue'
import VoiceSampleList from '@/components/VoiceSampleList.vue'
import { useVoiceStore } from '@/stores/voice'

const store = useVoiceStore()

const displayName = ref('')
const consentConfirmed = ref(false)
const defaultForUser = ref(false)
const localError = ref<string | null>(null)

onMounted(() => {
  store.fetchProfiles()
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

function profileStatusTone(status: string) {
  switch (status) {
    case 'ready':
      return 'bg-emerald-100 text-emerald-700'
    case 'failed':
      return 'bg-red-100 text-red-700'
    default:
      return 'bg-amber-100 text-amber-700'
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
</script>

<template>
  <main class="min-h-screen bg-[linear-gradient(180deg,#fff6eb_0%,#fffdf8_40%,#f8fbff_100%)] px-6 py-10">
    <div class="mx-auto max-w-6xl space-y-8">
      <div class="flex items-center justify-between">
        <div>
          <p class="text-xs font-semibold uppercase tracking-[0.35em] text-orange-600">Narration</p>
          <h1 class="mt-2 text-3xl font-semibold text-stone-950">Voice Profiles</h1>
        </div>

        <RouterLink
          :to="{ name: 'dashboard' }"
          class="text-sm font-medium text-stone-500 transition hover:text-stone-700"
        >
          &larr; Dashboard
        </RouterLink>
      </div>

      <section class="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <form
          class="rounded-[2rem] border border-orange-200 bg-white p-6 shadow-[0_20px_70px_-28px_rgba(234,88,12,0.28)]"
          @submit.prevent="handleCreateProfile"
        >
          <p class="text-xs font-semibold uppercase tracking-[0.35em] text-orange-600">Create</p>
          <h2 class="mt-3 text-2xl font-semibold text-stone-950">New narration voice</h2>
          <p class="mt-3 max-w-xl text-sm leading-6 text-stone-600">
            Create a private voice profile, then add recorded or uploaded audio samples for later cloning.
          </p>

          <label class="mt-6 block text-sm font-medium text-stone-700" for="display_name">
            Profile name
          </label>
          <input
            id="display_name"
            v-model="displayName"
            name="display_name"
            type="text"
            required
            maxlength="100"
            class="mt-2 block w-full rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3 text-stone-900 outline-none ring-0 transition placeholder:text-stone-400 focus:border-orange-300"
            placeholder="Bedtime Story Voice"
          />

          <label class="mt-5 flex items-start gap-3 rounded-2xl border border-stone-200 bg-stone-50 px-4 py-4 text-sm text-stone-700">
            <input
              v-model="consentConfirmed"
              type="checkbox"
              class="mt-1 size-4 rounded border-stone-300 text-orange-600 focus:ring-orange-500"
            />
            <span>I confirm I have consent to clone and use this voice for narration.</span>
          </label>

          <label class="mt-4 flex items-center gap-3 text-sm text-stone-700">
            <input
              v-model="defaultForUser"
              type="checkbox"
              class="size-4 rounded border-stone-300 text-orange-600 focus:ring-orange-500"
            />
            <span>Set as my default narration voice when cloning is available.</span>
          </label>

          <div
            v-if="localError || store.error"
            class="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
            role="alert"
          >
            {{ localError || store.error }}
          </div>

          <button
            type="submit"
            class="mt-6 rounded-2xl bg-orange-500 px-5 py-3 text-sm font-semibold text-white transition hover:bg-orange-600 disabled:cursor-not-allowed disabled:bg-orange-300"
            :disabled="store.isLoading"
          >
            Create voice profile
          </button>
        </form>

        <section class="rounded-[2rem] border border-stone-200 bg-stone-950 p-6 text-stone-50">
          <p class="text-xs font-semibold uppercase tracking-[0.35em] text-orange-300">Guidance</p>
          <h2 class="mt-3 text-2xl font-semibold">Sample checklist</h2>
          <ul class="mt-5 space-y-3 text-sm leading-6 text-stone-300">
            <li>Use a quiet room and keep the mic at a steady distance.</li>
            <li>Record natural speaking voice, not exaggerated character voices.</li>
            <li>Upload several clean clips over time; playback stays private.</li>
          </ul>
        </section>
      </section>

      <div v-if="store.isLoading && store.profiles.length === 0" class="py-12 text-center text-stone-400">
        Loading…
      </div>

      <div
        v-if="!store.isLoading && store.profiles.length === 0"
        class="rounded-[2rem] border border-dashed border-stone-300 bg-white px-6 py-12 text-center"
      >
        <p class="text-stone-500">No voice profiles yet.</p>
      </div>

      <section v-else class="grid gap-6 lg:grid-cols-2">
        <article
          v-for="profile in store.profiles"
          :key="profile.id"
          class="rounded-[2rem] border border-stone-200 bg-white p-6 shadow-[0_18px_60px_-32px_rgba(15,23,42,0.25)]"
        >
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p class="text-xs font-semibold uppercase tracking-[0.35em] text-orange-600">Profile</p>
              <h2 class="mt-3 text-2xl font-semibold text-stone-950">{{ profile.display_name }}</h2>
              <p class="mt-2 text-sm text-stone-500">{{ profile.samples.length }} sample(s)</p>
            </div>

            <div class="flex flex-wrap items-center gap-2">
              <span
                class="rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em]"
                :class="profileStatusTone(profile.status)"
              >
                {{ profileStatusLabel(profile.status, profile.samples.length) }}
              </span>
              <span
                v-if="profile.default_for_user"
                class="rounded-full bg-stone-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-stone-600"
              >
                default
              </span>
              <button
                type="button"
                class="rounded-full border border-red-200 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-red-600 transition hover:border-red-300 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
                :disabled="store.isLoading"
                @click="handleDeleteProfile(profile.id)"
              >
                Delete
              </button>
            </div>
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

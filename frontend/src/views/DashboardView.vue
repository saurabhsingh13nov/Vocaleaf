<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import { useAuth } from '@/composables/useAuth'

const router = useRouter()
const auth = useAuth()

const displayName = computed(() => auth.user.value?.full_name || 'Story Creator')
const email = computed(() => auth.user.value?.primary_email || 'No email on file')
const createdAt = computed(() => {
  const created = auth.user.value?.created_at

  if (!created) {
    return 'Unknown'
  }

  return new Date(created).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
})

async function handleLogout() {
  await auth.logout()
  await router.push({ name: 'login' })
}
</script>

<template>
  <main class="min-h-screen bg-[linear-gradient(180deg,#f6f0ff_0%,#fff8f1_42%,#fffdf8_100%)] px-6 py-10">
    <div class="mx-auto max-w-6xl space-y-8">
      <section class="overflow-hidden rounded-[2rem] border border-rose-200/70 bg-white shadow-[0_20px_80px_-28px_rgba(190,24,93,0.28)]">
        <div class="grid gap-8 px-8 py-10 lg:grid-cols-[1.15fr_0.85fr] lg:px-10">
          <div>
            <p class="text-xs font-semibold uppercase tracking-[0.35em] text-rose-600">Dashboard</p>
            <h1 class="mt-4 text-4xl font-semibold text-stone-950">
              Welcome, {{ displayName }}
            </h1>
            <p class="mt-4 max-w-2xl text-sm leading-7 text-stone-600">
              Your account session is now managed by the Vue app using the existing FastAPI auth
              API and cookie-based JWT flow. This page is intentionally simple and acts as the
              authenticated landing page for the next feature phases.
            </p>
          </div>

          <div class="rounded-[1.75rem] bg-stone-950 p-6 text-stone-50">
            <p class="text-xs font-semibold uppercase tracking-[0.35em] text-rose-300">
              Account Snapshot
            </p>
            <dl class="mt-6 space-y-4 text-sm">
              <div>
                <dt class="text-stone-400">Email</dt>
                <dd class="mt-1 font-medium text-white">{{ email }}</dd>
              </div>
              <div>
                <dt class="text-stone-400">Status</dt>
                <dd class="mt-1 font-medium capitalize text-white">
                  {{ auth.user.value?.status ?? 'unknown' }}
                </dd>
              </div>
              <div>
                <dt class="text-stone-400">Created</dt>
                <dd class="mt-1 font-medium text-white">{{ createdAt }}</dd>
              </div>
            </dl>

            <button
              class="mt-8 inline-flex rounded-2xl bg-rose-500 px-4 py-3 text-sm font-semibold text-white transition hover:bg-rose-600"
              type="button"
              @click="handleLogout"
            >
              Log out
            </button>
          </div>
        </div>
      </section>

      <section class="grid gap-6 lg:grid-cols-2 xl:grid-cols-4">
        <RouterLink
          :to="{ name: 'children' }"
          class="block rounded-[1.75rem] border border-amber-200 bg-amber-50 p-6 transition hover:shadow-md"
        >
          <p class="text-sm font-semibold uppercase tracking-[0.25em] text-amber-700">Manage</p>
          <h2 class="mt-4 text-xl font-semibold text-amber-950">Child profiles</h2>
          <p class="mt-3 text-sm leading-6 text-amber-900/75">
            Create and manage child profiles to personalize stories, themes, and narration.
          </p>
        </RouterLink>

        <RouterLink
          :to="{ name: 'voice-profiles' }"
          class="block rounded-[1.75rem] border border-violet-200 bg-violet-50 p-6 transition hover:shadow-md"
        >
          <p class="text-sm font-semibold uppercase tracking-[0.25em] text-violet-700">Narration</p>
          <h2 class="mt-4 text-xl font-semibold text-violet-950">Voice profiles</h2>
          <p class="mt-3 text-sm leading-6 text-violet-900/75">
            Record or upload voice samples that will later be used for cloned narration.
          </p>
        </RouterLink>

        <article class="rounded-[1.75rem] border border-sky-200 bg-sky-50 p-6">
          <p class="text-sm font-semibold uppercase tracking-[0.25em] text-sky-700">Ready</p>
          <h2 class="mt-4 text-xl font-semibold text-sky-950">Protected routing</h2>
          <p class="mt-3 text-sm leading-6 text-sky-900/75">
            Login and register routes stay public. Dashboard access now depends on the auth store.
          </p>
        </article>

        <article class="rounded-[1.75rem] border border-emerald-200 bg-emerald-50 p-6">
          <p class="text-sm font-semibold uppercase tracking-[0.25em] text-emerald-700">
            Session
          </p>
          <h2 class="mt-4 text-xl font-semibold text-emerald-950">Cookie-backed auth</h2>
          <p class="mt-3 text-sm leading-6 text-emerald-900/75">
            Refreshing the page preserves the session by restoring the current user from the backend.
          </p>
        </article>
      </section>
    </div>
  </main>
</template>

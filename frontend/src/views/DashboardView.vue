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
  <main class="min-h-screen px-4 py-6 sm:px-6 sm:py-8">
    <div class="app-shell space-y-6">
      <section class="surface-card grid gap-5 px-6 py-7 sm:px-8 lg:grid-cols-[1.2fr_0.8fr] lg:px-10 lg:py-10">
        <div>
          <p class="page-kicker">Dashboard</p>
          <h1 class="page-title">Welcome, {{ displayName }}</h1>
          <p class="page-subtitle">
            This is the working home for your account. Manage profiles, prepare narration voices, and move toward story creation without losing your place.
          </p>
        </div>

        <div class="surface-card-muted p-5 sm:p-6">
          <p class="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--app-muted-soft)]">
            Account Snapshot
          </p>
          <dl class="mt-5 space-y-4 text-sm">
            <div>
              <dt class="text-[var(--app-muted)]">Email</dt>
              <dd class="mt-1 font-semibold text-[var(--app-ink)]">{{ email }}</dd>
            </div>
            <div>
              <dt class="text-[var(--app-muted)]">Status</dt>
              <dd class="mt-1 font-semibold capitalize text-[var(--app-ink)]">
                {{ auth.user.value?.status ?? 'unknown' }}
              </dd>
            </div>
            <div>
              <dt class="text-[var(--app-muted)]">Created</dt>
              <dd class="mt-1 font-semibold text-[var(--app-ink)]">{{ createdAt }}</dd>
            </div>
          </dl>

          <button class="primary-button mt-6 w-full sm:w-auto" type="button" @click="handleLogout">
            Log out
          </button>
        </div>
      </section>

      <section class="dashboard-grid md:grid-cols-2 xl:grid-cols-4">
        <RouterLink :to="{ name: 'children' }" class="dashboard-tile transition hover:-translate-y-0.5">
          <p class="page-kicker">Profiles</p>
          <h2 class="mt-3 text-2xl font-semibold text-[var(--app-ink)]">Child profiles</h2>
          <p class="mt-3 text-sm leading-6 text-[var(--app-muted)]">
            Create and update the details that will personalize story prompts later.
          </p>
        </RouterLink>

        <RouterLink :to="{ name: 'voice-profiles' }" class="dashboard-tile transition hover:-translate-y-0.5">
          <p class="page-kicker">Narration</p>
          <h2 class="mt-3 text-2xl font-semibold text-[var(--app-ink)]">Voice profiles</h2>
          <p class="mt-3 text-sm leading-6 text-[var(--app-muted)]">
            Upload samples, trigger cloning, and prepare voices for page-by-page audio.
          </p>
        </RouterLink>

        <article class="dashboard-tile">
          <p class="page-kicker">Session</p>
          <h2 class="mt-3 text-2xl font-semibold text-[var(--app-ink)]">Cookie-backed auth</h2>
          <p class="mt-3 text-sm leading-6 text-[var(--app-muted)]">
            Refreshing the page restores the current user from the backend without storing tokens in local app state.
          </p>
        </article>

        <article class="dashboard-tile">
          <p class="page-kicker">Next</p>
          <h2 class="mt-3 text-2xl font-semibold text-[var(--app-ink)]">Story generation</h2>
          <p class="mt-3 text-sm leading-6 text-[var(--app-muted)]">
            Story creation and page generation are still ahead, but the account and voice foundations are now in place.
          </p>
        </article>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { useAuth } from '@/composables/useAuth'

const router = useRouter()
const auth = useAuth()

const form = reactive({
  email: '',
  full_name: '',
  password: '',
})

const errorMessage = ref('')

async function handleSubmit() {
  errorMessage.value = ''

  try {
    await auth.register({
      email: form.email,
      full_name: form.full_name,
      password: form.password,
    })
    await router.push({ name: 'dashboard' })
  } catch (error) {
    errorMessage.value = auth.getErrorMessage(error)
  }
}
</script>

<template>
  <main class="min-h-screen bg-[radial-gradient(circle_at_top_right,#dbeafe,transparent_28%),linear-gradient(180deg,#f8fafc_0%,#eff6ff_45%,#f8fafc_100%)] px-6 py-10">
    <div class="mx-auto flex min-h-[calc(100vh-5rem)] max-w-5xl items-center justify-center">
      <div class="grid w-full overflow-hidden rounded-[2rem] border border-sky-200/80 bg-white/90 shadow-[0_20px_80px_-24px_rgba(15,23,42,0.28)] backdrop-blur lg:grid-cols-[0.95fr_1.05fr]">
        <section class="px-6 py-10 sm:px-10">
          <div class="mx-auto max-w-md">
            <p class="text-sm font-medium uppercase tracking-[0.3em] text-sky-700">Vocaleaf</p>
            <h1 class="mt-4 text-3xl font-semibold text-slate-950">Create your account</h1>
            <p class="mt-2 text-sm text-slate-600">
              Start with account access. Child profiles and story creation come next.
            </p>

            <form class="mt-8 space-y-5" @submit.prevent="handleSubmit">
              <label class="block">
                <span class="mb-2 block text-sm font-medium text-slate-700">Full name</span>
                <input
                  v-model="form.full_name"
                  class="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-slate-900 outline-none transition focus:border-sky-500 focus:ring-4 focus:ring-sky-200/70"
                  type="text"
                  name="full_name"
                  autocomplete="name"
                  required
                />
              </label>

              <label class="block">
                <span class="mb-2 block text-sm font-medium text-slate-700">Email</span>
                <input
                  v-model="form.email"
                  class="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-slate-900 outline-none transition focus:border-sky-500 focus:ring-4 focus:ring-sky-200/70"
                  type="email"
                  name="email"
                  autocomplete="email"
                  required
                />
              </label>

              <label class="block">
                <span class="mb-2 block text-sm font-medium text-slate-700">Password</span>
                <input
                  v-model="form.password"
                  class="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-slate-900 outline-none transition focus:border-sky-500 focus:ring-4 focus:ring-sky-200/70"
                  type="password"
                  name="password"
                  autocomplete="new-password"
                  minlength="8"
                  required
                />
              </label>

              <p
                v-if="errorMessage"
                class="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
              >
                {{ errorMessage }}
              </p>

              <button
                class="w-full rounded-2xl bg-sky-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:bg-sky-300"
                type="submit"
                :disabled="auth.isLoading.value"
              >
                {{ auth.isLoading.value ? 'Creating account...' : 'Create account' }}
              </button>
            </form>

            <p class="mt-6 text-sm text-slate-600">
              Already have an account?
              <RouterLink class="font-semibold text-sky-700 hover:text-sky-800" to="/login">
                Sign in
              </RouterLink>
            </p>
          </div>
        </section>

        <section class="hidden bg-sky-950 px-10 py-12 text-sky-50 lg:block">
          <p class="text-xs font-semibold uppercase tracking-[0.35em] text-sky-300">Phase 3</p>
          <h2 class="mt-8 max-w-sm text-4xl font-semibold leading-tight">
            Frontend auth closes the loop with the FastAPI backend.
          </h2>
          <p class="mt-6 max-w-md text-sm leading-7 text-sky-100/80">
            Registration sets backend cookies immediately, so the app can route straight into an
            authenticated dashboard without storing tokens in the browser.
          </p>
        </section>
      </div>
    </div>
  </main>
</template>

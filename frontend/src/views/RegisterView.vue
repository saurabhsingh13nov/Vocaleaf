<script setup lang="ts">
import axios from 'axios'
import { onMounted, reactive, ref } from 'vue'
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
const googleLoaded = ref(false)
const pendingGoogleCredential = ref('')
const linkPassword = ref('')
const linkError = ref('')

async function handleLinkSubmit() {
  linkError.value = ''

  try {
    await auth.linkWithGoogle(pendingGoogleCredential.value, linkPassword.value)
    await router.push({ name: 'dashboard' })
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      linkError.value = 'Incorrect password. Please try again.'
    } else {
      linkError.value = auth.getErrorMessage(error)
    }
  }
}

function cancelLink() {
  pendingGoogleCredential.value = ''
  linkPassword.value = ''
  linkError.value = ''
}

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

async function handleGoogleCallback(response: { credential: string }) {
  errorMessage.value = ''

  try {
    await auth.loginWithGoogle(response.credential)
    await router.push({ name: 'dashboard' })
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 409) {
      pendingGoogleCredential.value = response.credential
    } else {
      errorMessage.value = auth.getErrorMessage(error)
    }
  }
}

onMounted(() => {
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID
  if (!clientId) return

  const script = document.createElement('script')
  script.src = 'https://accounts.google.com/gsi/client'
  script.async = true
  script.defer = true
  script.onload = () => {
    window.google?.accounts.id.initialize({
      client_id: clientId,
      callback: handleGoogleCallback,
    })
    window.google?.accounts.id.renderButton(
      document.getElementById('google-signin-btn-register')!,
      { theme: 'outline', size: 'large', width: '100%', text: 'signup_with' },
    )
    googleLoaded.value = true
  }
  document.head.appendChild(script)
})
</script>

<template>
  <main class="min-h-screen bg-[radial-gradient(circle_at_top_right,#dbeafe,transparent_28%),linear-gradient(180deg,#f8fafc_0%,#eff6ff_45%,#f8fafc_100%)] px-6 py-10">
    <div class="mx-auto flex min-h-[calc(100vh-5rem)] max-w-5xl items-center justify-center">
      <div class="grid w-full overflow-hidden rounded-[2rem] border border-sky-200/80 bg-white/90 shadow-[0_20px_80px_-24px_rgba(15,23,42,0.28)] backdrop-blur lg:grid-cols-[0.95fr_1.05fr]">
        <section class="px-6 py-10 sm:px-10">
          <div class="mx-auto max-w-md">
            <p class="text-sm font-medium uppercase tracking-[0.3em] text-sky-700">Vocaleaf</p>

            <!-- Link mode: shown when Google 409 triggers account linking -->
            <template v-if="pendingGoogleCredential">
              <h1 class="mt-4 text-3xl font-semibold text-slate-950">Link your accounts</h1>
              <p class="mt-2 text-sm text-slate-600">
                Your Google account uses the same email as an existing Vocaleaf account. Enter your
                password to link them.
              </p>

              <form class="mt-8 space-y-5" @submit.prevent="handleLinkSubmit">
                <label class="block">
                  <span class="mb-2 block text-sm font-medium text-slate-700">Password</span>
                  <input
                    v-model="linkPassword"
                    class="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-slate-900 outline-none transition focus:border-sky-500 focus:ring-4 focus:ring-sky-200/70"
                    type="password"
                    autocomplete="current-password"
                    required
                  />
                </label>

                <p
                  v-if="linkError"
                  class="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
                >
                  {{ linkError }}
                </p>

                <button
                  class="w-full rounded-2xl bg-sky-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:bg-sky-300"
                  type="submit"
                  :disabled="auth.isLoading.value"
                >
                  {{ auth.isLoading.value ? 'Linking...' : 'Link accounts' }}
                </button>

                <button
                  class="w-full rounded-2xl border border-slate-300 px-4 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
                  type="button"
                  @click="cancelLink"
                >
                  Cancel
                </button>
              </form>
            </template>

            <!-- Normal registration form -->
            <template v-else>
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

            <div class="my-6 flex items-center gap-4">
              <hr class="flex-1 border-slate-200" />
              <span class="text-xs font-medium uppercase tracking-wider text-slate-400">or</span>
              <hr class="flex-1 border-slate-200" />
            </div>

            <div id="google-signin-btn-register" class="flex justify-center"></div>

            <p class="mt-6 text-sm text-slate-600">
              Already have an account?
              <RouterLink class="font-semibold text-sky-700 hover:text-sky-800" to="/login">
                Sign in
              </RouterLink>
            </p>
            </template>
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

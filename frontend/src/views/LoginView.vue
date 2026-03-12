<script setup lang="ts">
import axios from 'axios'
import { onMounted, reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { useAuth } from '@/composables/useAuth'

const router = useRouter()
const auth = useAuth()

const form = reactive({
  email: '',
  password: '',
})

const errorMessage = ref('')
const googleLoaded = ref(false)

async function handleSubmit() {
  errorMessage.value = ''

  try {
    await auth.login({
      email: form.email,
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
      errorMessage.value =
        'This email is already registered with a password. Please sign in with your email and password.'
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
      document.getElementById('google-signin-btn-login')!,
      { theme: 'outline', size: 'large', width: '100%', text: 'signin_with' },
    )
    googleLoaded.value = true
  }
  document.head.appendChild(script)
})
</script>

<template>
  <main class="min-h-screen bg-[radial-gradient(circle_at_top,#fef3c7,transparent_28%),linear-gradient(180deg,#fffaf0_0%,#fff7ed_45%,#fffbeb_100%)] px-6 py-10">
    <div class="mx-auto flex min-h-[calc(100vh-5rem)] max-w-5xl items-center justify-center">
      <div class="grid w-full overflow-hidden rounded-[2rem] border border-amber-200/80 bg-white/85 shadow-[0_20px_80px_-24px_rgba(146,64,14,0.35)] backdrop-blur lg:grid-cols-[1.1fr_0.9fr]">
        <section class="hidden bg-amber-950 px-10 py-12 text-amber-50 lg:block">
          <p class="text-xs font-semibold uppercase tracking-[0.35em] text-amber-300">Vocaleaf</p>
          <h1 class="mt-8 max-w-sm text-4xl font-semibold leading-tight">
            Sign in to keep bedtime stories personal.
          </h1>
          <p class="mt-6 max-w-md text-sm leading-7 text-amber-100/80">
            Use the FastAPI auth backend already in the repo to manage your account, then the
            dashboard becomes the starting point for child profiles and story creation.
          </p>
        </section>

        <section class="px-6 py-10 sm:px-10">
          <div class="mx-auto max-w-md">
            <p class="text-sm font-medium uppercase tracking-[0.3em] text-amber-700 lg:hidden">
              Vocaleaf
            </p>
            <h2 class="mt-4 text-3xl font-semibold text-stone-900">Welcome back</h2>
            <p class="mt-2 text-sm text-stone-600">
              Sign in with your email and password.
            </p>

            <form class="mt-8 space-y-5" @submit.prevent="handleSubmit">
              <label class="block">
                <span class="mb-2 block text-sm font-medium text-stone-700">Email</span>
                <input
                  v-model="form.email"
                  class="w-full rounded-2xl border border-stone-300 bg-white px-4 py-3 text-stone-900 outline-none transition focus:border-amber-500 focus:ring-4 focus:ring-amber-200/60"
                  type="email"
                  name="email"
                  autocomplete="email"
                  required
                />
              </label>

              <label class="block">
                <span class="mb-2 block text-sm font-medium text-stone-700">Password</span>
                <input
                  v-model="form.password"
                  class="w-full rounded-2xl border border-stone-300 bg-white px-4 py-3 text-stone-900 outline-none transition focus:border-amber-500 focus:ring-4 focus:ring-amber-200/60"
                  type="password"
                  name="password"
                  autocomplete="current-password"
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
                class="w-full rounded-2xl bg-amber-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-amber-700 disabled:cursor-not-allowed disabled:bg-amber-300"
                type="submit"
                :disabled="auth.isLoading.value"
              >
                {{ auth.isLoading.value ? 'Signing in...' : 'Sign in' }}
              </button>
            </form>

            <div class="my-6 flex items-center gap-4">
              <hr class="flex-1 border-stone-200" />
              <span class="text-xs font-medium uppercase tracking-wider text-stone-400">or</span>
              <hr class="flex-1 border-stone-200" />
            </div>

            <div id="google-signin-btn-login" class="flex justify-center"></div>

            <p class="mt-6 text-sm text-stone-600">
              Need an account?
              <RouterLink class="font-semibold text-amber-700 hover:text-amber-800" to="/register">
                Create one
              </RouterLink>
            </p>
          </div>
        </section>
      </div>
    </div>
  </main>
</template>

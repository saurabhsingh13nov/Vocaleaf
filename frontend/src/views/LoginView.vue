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
      pendingGoogleCredential.value = response.credential
    } else {
      errorMessage.value = auth.getErrorMessage(error)
    }
  }
}

onMounted(() => {
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID
  if (!clientId) {
    return
  }

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
  }
  document.head.appendChild(script)
})
</script>

<template>
  <main class="min-h-screen px-4 py-6 sm:px-6 sm:py-8">
    <div class="app-shell flex min-h-[calc(100vh-2rem)] items-center">
      <div class="grid w-full gap-4 lg:grid-cols-[0.96fr_1.04fr]">
        <section class="surface-card-muted order-2 px-6 py-7 sm:px-8 lg:order-1 lg:px-10 lg:py-10">
          <p class="page-kicker">Vocaleaf</p>
          <h1 class="page-title max-w-sm">Stories that sound like home.</h1>
          <p class="page-subtitle max-w-md">
            Sign in to manage child profiles, save narration voices, and pick up where bedtime left off.
          </p>

          <div class="mt-8">
            <div class="dashboard-tile">
              <p class="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--app-muted-soft)]">
                Private by default
              </p>
              <p class="mt-3 text-sm leading-6 text-[var(--app-muted)]">
                Voice samples and generated story assets stay behind authenticated access.
              </p>
            </div>
          </div>
        </section>

        <section class="surface-card order-1 px-6 py-7 sm:px-8 lg:order-2 lg:px-10 lg:py-10">
          <p class="page-kicker">Sign in</p>

          <template v-if="pendingGoogleCredential">
            <h2 class="mt-3 text-4xl font-semibold text-[var(--app-ink)]">Link your accounts</h2>
            <p class="page-subtitle max-w-md">
              Your Google account uses the same email as an existing Vocaleaf account. Enter your password to link them.
            </p>

            <form class="mt-8 space-y-5" @submit.prevent="handleLinkSubmit">
              <label>
                <span class="field-label">Password</span>
                <input
                  v-model="linkPassword"
                  class="field-input"
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

              <div class="auth-actions sm:flex-row">
                <button class="primary-button w-full" type="submit" :disabled="auth.isLoading.value">
                  {{ auth.isLoading.value ? 'Linking...' : 'Link accounts' }}
                </button>
                <button class="secondary-button w-full" type="button" @click="cancelLink">Cancel</button>
              </div>
            </form>
          </template>

          <template v-else>
            <h2 class="mt-3 text-4xl font-semibold text-[var(--app-ink)]">Welcome back</h2>
            <p class="page-subtitle max-w-md">Sign in with your email and password.</p>

            <form class="mt-8 space-y-5" @submit.prevent="handleSubmit">
              <label>
                <span class="field-label">Email</span>
                <input
                  v-model="form.email"
                  class="field-input"
                  type="email"
                  name="email"
                  autocomplete="email"
                  required
                />
              </label>

              <label>
                <span class="field-label">Password</span>
                <input
                  v-model="form.password"
                  class="field-input"
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

              <div class="auth-actions">
                <button class="primary-button w-full" type="submit" :disabled="auth.isLoading.value">
                  {{ auth.isLoading.value ? 'Signing in...' : 'Sign in' }}
                </button>
              </div>
            </form>

            <div class="my-7 flex items-center gap-4">
              <div class="h-px flex-1 bg-[var(--app-border)]"></div>
              <span class="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--app-muted-soft)]">or</span>
              <div class="h-px flex-1 bg-[var(--app-border)]"></div>
            </div>

            <div id="google-signin-btn-login" class="flex justify-center"></div>

            <p class="mt-6 text-sm text-[var(--app-muted)]">
              Need an account?
              <RouterLink class="font-semibold text-[var(--app-accent)] transition hover:text-[var(--app-accent-strong)]" to="/register">
                Create one
              </RouterLink>
            </p>
          </template>
        </section>
      </div>
    </div>
  </main>
</template>

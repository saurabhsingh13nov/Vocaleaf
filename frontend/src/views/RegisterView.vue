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
      document.getElementById('google-signin-btn-register')!,
      { theme: 'outline', size: 'large', width: '100%', text: 'signup_with' },
    )
  }
  document.head.appendChild(script)
})
</script>

<template>
  <main class="min-h-screen px-4 py-6 sm:px-6 sm:py-8">
    <div class="app-shell flex min-h-[calc(100vh-2rem)] items-center">
      <div class="grid w-full gap-4 lg:grid-cols-[1.02fr_0.98fr]">
        <section class="surface-card order-1 px-6 py-7 sm:px-8 lg:px-10 lg:py-10">
          <p class="page-kicker">Create account</p>

          <template v-if="pendingGoogleCredential">
            <h1 class="mt-3 text-4xl font-semibold text-[var(--app-ink)]">Link your accounts</h1>
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

              <div class="flex flex-col gap-3 sm:flex-row">
                <button class="primary-button w-full" type="submit" :disabled="auth.isLoading.value">
                  {{ auth.isLoading.value ? 'Linking...' : 'Link accounts' }}
                </button>
                <button class="secondary-button w-full" type="button" @click="cancelLink">Cancel</button>
              </div>
            </form>
          </template>

          <template v-else>
            <h1 class="mt-3 text-4xl font-semibold text-[var(--app-ink)]">Create your account</h1>
            <p class="page-subtitle max-w-md">
              Start with account access. Child profiles, narration voices, and story creation come next.
            </p>

            <form class="mt-8 space-y-5" @submit.prevent="handleSubmit">
              <label>
                <span class="field-label">Full name</span>
                <input
                  v-model="form.full_name"
                  class="field-input"
                  type="text"
                  name="full_name"
                  autocomplete="name"
                  required
                />
              </label>

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

              <button class="primary-button w-full" type="submit" :disabled="auth.isLoading.value">
                {{ auth.isLoading.value ? 'Creating account...' : 'Create account' }}
              </button>
            </form>

            <div class="my-7 flex items-center gap-4">
              <div class="h-px flex-1 bg-[var(--app-border)]"></div>
              <span class="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--app-muted-soft)]">or</span>
              <div class="h-px flex-1 bg-[var(--app-border)]"></div>
            </div>

            <div id="google-signin-btn-register" class="flex justify-center"></div>

            <p class="mt-6 text-sm text-[var(--app-muted)]">
              Already have an account?
              <RouterLink class="font-semibold text-[var(--app-accent)] transition hover:text-[var(--app-accent-strong)]" to="/login">
                Sign in
              </RouterLink>
            </p>
          </template>
        </section>

        <section class="surface-card-muted order-2 px-6 py-7 sm:px-8 lg:px-10 lg:py-10">
          <p class="page-kicker">Why Vocaleaf</p>
          <h2 class="page-title max-w-sm">A calmer setup for families.</h2>
          <p class="page-subtitle max-w-md">
            Create one account, add a child profile, and build toward stories with familiar voices, private assets, and simple repeatable flows.
          </p>

          <div class="mt-8 space-y-3">
            <div class="dashboard-tile">
              <p class="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--app-muted-soft)]">One account</p>
              <p class="mt-3 text-sm leading-6 text-[var(--app-muted)]">
                Registration signs you in right away so the app can route directly into your workspace.
              </p>
            </div>
            <div class="dashboard-tile">
              <p class="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--app-muted-soft)]">Built for voice</p>
              <p class="mt-3 text-sm leading-6 text-[var(--app-muted)]">
                Consent, sample uploads, and cloning workflows stay explicit instead of hidden in the background.
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  </main>
</template>

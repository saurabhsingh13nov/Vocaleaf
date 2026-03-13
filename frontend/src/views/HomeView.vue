<script setup lang="ts">
import { onMounted, ref } from 'vue'

const apiStatus = ref<string>('checking...')
const isHealthy = ref(false)

onMounted(async () => {
  try {
    const response = await fetch('/api/health')
    const data = await response.json()
    apiStatus.value = data.status
    isHealthy.value = data.status === 'healthy'
  } catch {
    apiStatus.value = 'unreachable'
    isHealthy.value = false
  }
})
</script>

<template>
  <main class="min-h-screen px-4 py-6 sm:px-6 sm:py-8">
    <div class="app-shell flex min-h-[calc(100vh-2rem)] items-center justify-center">
      <section class="surface-card w-full max-w-3xl px-6 py-8 text-center sm:px-10">
        <p class="page-kicker">Vocaleaf</p>
        <h1 class="page-title">Personalized storybooks for your child</h1>
        <p class="page-subtitle mx-auto">
          The frontend and backend foundations are connected. This landing view is kept intentionally light while authenticated flows live behind the dashboard.
        </p>

        <div
          class="mx-auto mt-8 max-w-sm rounded-[1.25rem] border px-4 py-4"
          :class="isHealthy ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-red-200 bg-red-50 text-red-800'"
        >
          <p class="text-xs font-semibold uppercase tracking-[0.24em]">API status</p>
          <p class="mt-2 text-base font-semibold">{{ apiStatus }}</p>
        </div>
      </section>
    </div>
  </main>
</template>

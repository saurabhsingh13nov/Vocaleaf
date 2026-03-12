<!--
  App.vue is the root component. Every Vue app has one.
  <RouterView /> renders whichever view matches the current URL.
-->
<script setup lang="ts">
import { RouterView } from 'vue-router'

import { useAuth } from '@/composables/useAuth'

const auth = useAuth()
</script>

<template>
  <div v-if="!auth.isInitialized.value" class="flex min-h-screen items-center justify-center bg-stone-950 text-stone-50">
    <div class="rounded-full border border-stone-700 px-5 py-3 text-sm uppercase tracking-[0.35em] text-stone-300">
      Restoring session
    </div>
  </div>
  <RouterView v-else />
</template>

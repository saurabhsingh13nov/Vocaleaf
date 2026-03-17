<!--
  App.vue is the root component. Every Vue app has one.
  <RouterView /> renders whichever view matches the current URL.
-->
<script setup lang="ts">
import { RouterView } from 'vue-router'
import { watch } from 'vue'

import ConsentModal from '@/components/ConsentModal.vue'
import { useAuth } from '@/composables/useAuth'
import { useConsentStore } from '@/stores/consent'
import { useSubscriptionStore } from '@/stores/subscription'

const auth = useAuth()
const consentStore = useConsentStore()
const subscriptionStore = useSubscriptionStore()

const legalLinks = [
  { label: 'Terms of Service', href: '/legal/terms-2026-03-16.html' },
  { label: 'Privacy Policy', href: '/legal/privacy-2026-03-16.html' },
]

watch(
  () => [auth.isInitialized.value, auth.user.value?.id] as const,
  async ([isInitialized, userId]) => {
    if (!isInitialized) {
      return
    }

    if (!userId) {
      consentStore.reset()
      subscriptionStore.reset()
      return
    }

    await Promise.allSettled([
      consentStore.fetchStatus(),
      subscriptionStore.fetchSummary(),
    ])
  },
  { immediate: true },
)

async function acceptLegalConsents() {
  await consentStore.acceptLegalConsents()
}
</script>

<template>
  <div v-if="!auth.isInitialized.value" class="flex min-h-screen items-center justify-center bg-stone-950 text-stone-50">
    <div class="rounded-full border border-stone-700 px-5 py-3 text-sm uppercase tracking-[0.35em] text-stone-300">
      Restoring session
    </div>
  </div>
  <RouterView v-else />
  <ConsentModal
    v-if="auth.isAuthenticated.value && consentStore.requiresLegalConsent"
    title="Accept the latest legal updates"
    message="Before you continue, review and accept the current Terms of Service and Privacy Policy for Vocaleaf."
    confirmation-label="I have reviewed and accept the Terms of Service and Privacy Policy dated 2026-03-16."
    confirm-label="Accept and continue"
    pending-confirm-label="Saving..."
    :dismissible="false"
    :is-pending="consentStore.isSaving"
    :links="legalLinks"
    @confirm="acceptLegalConsents"
  />
</template>

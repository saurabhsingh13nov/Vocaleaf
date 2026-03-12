<!--
  VUE.JS LEARNING NOTES:

  <script setup lang="ts">
    This is the Composition API with <script setup> — the modern way to write Vue components.
    Code here runs once when the component mounts. No need for export default, data(), methods(), etc.

  ref() — creates reactive state. When the value changes, the template re-renders automatically.
  onMounted() — lifecycle hook that runs after the component is added to the DOM.

  In the template:
    {{ variable }} — renders reactive data
    :class="..." — dynamic class binding (shorthand for v-bind:class)
-->
<script setup lang="ts">
import { ref, onMounted } from 'vue'

// ref() creates a reactive variable. Think of it like useState() in React.
// The template automatically updates when this value changes.
const apiStatus = ref<string>('checking...')
const isHealthy = ref(false)

// onMounted runs once after the component appears in the DOM.
// This is where you make initial API calls.
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
  <div class="min-h-screen bg-gray-50 flex items-center justify-center">
    <div class="text-center space-y-6">
      <h1 class="text-4xl font-bold text-gray-900">Vocaleaf</h1>
      <p class="text-lg text-gray-600">Personalized storybooks for your child</p>

      <div
        class="mt-8 p-4 rounded-lg border"
        :class="isHealthy ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'"
      >
        <p
          class="text-sm font-medium"
          :class="isHealthy ? 'text-green-800' : 'text-red-800'"
        >
          API Status: {{ apiStatus }}
        </p>
      </div>
    </div>
  </div>
</template>

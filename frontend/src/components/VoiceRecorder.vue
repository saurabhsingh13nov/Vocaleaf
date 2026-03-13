<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'

import {
  getAudioDurationSeconds,
  isSupportedVoiceSampleMimeType,
  normalizeVoiceSampleMimeType,
} from '@/services/voice'

const props = defineProps<{
  isUploading?: boolean
}>()

const emit = defineEmits<{
  submit: [payload: { file: Blob; mimeType: string; fileSizeBytes: number; durationSeconds: number }]
}>()

const mode = ref<'record' | 'upload'>('record')
const isRecording = ref(false)
const error = ref<string | null>(null)
const pendingFile = ref<Blob | null>(null)
const pendingMimeType = ref('')
const pendingDurationSeconds = ref<number | null>(null)
const pendingLabel = ref<string | null>(null)

let activeRecorder: MediaRecorder | null = null
let activeStream: MediaStream | null = null
let recordedChunks: Blob[] = []

function clearPending() {
  pendingFile.value = null
  pendingMimeType.value = ''
  pendingDurationSeconds.value = null
  pendingLabel.value = null
}

function cleanupStream() {
  activeStream?.getTracks().forEach((track) => track.stop())
  activeStream = null
}

async function startRecording() {
  error.value = null

  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
    error.value = 'Recording is not supported in this browser.'
    return
  }

  recordedChunks = []
  clearPending()

  try {
    activeStream = await navigator.mediaDevices.getUserMedia({ audio: true })
    activeRecorder = new MediaRecorder(activeStream)
    activeRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        recordedChunks.push(event.data)
      }
    }
    activeRecorder.onstop = async () => {
      try {
        const mimeType = activeRecorder?.mimeType || 'audio/webm'
        const normalizedMimeType = normalizeVoiceSampleMimeType(mimeType)
        if (!isSupportedVoiceSampleMimeType(normalizedMimeType)) {
          throw new Error(`This recording format is not supported: ${mimeType}`)
        }
        const file = new Blob(recordedChunks, { type: mimeType })
        const durationSeconds = await getAudioDurationSeconds(file)
        pendingFile.value = file
        pendingMimeType.value = normalizedMimeType
        pendingDurationSeconds.value = durationSeconds
        pendingLabel.value = 'Recorded sample ready'
      } catch (err) {
        error.value = err instanceof Error ? err.message : 'Unable to prepare recorded sample.'
      } finally {
        cleanupStream()
        activeRecorder = null
        recordedChunks = []
      }
    }
    activeRecorder.start()
    isRecording.value = true
  } catch (err) {
    cleanupStream()
    error.value = err instanceof Error ? err.message : 'Unable to start recording.'
  }
}

function stopRecording() {
  if (!activeRecorder || !isRecording.value) {
    return
  }

  isRecording.value = false
  activeRecorder.stop()
}

async function handleFileChange(event: Event) {
  error.value = null
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]

  if (!file) {
    return
  }

  try {
    const normalizedMimeType = normalizeVoiceSampleMimeType(file.type || 'audio/webm')
    if (!isSupportedVoiceSampleMimeType(normalizedMimeType)) {
      throw new Error(`This audio format is not supported: ${file.type || 'unknown format'}`)
    }
    const durationSeconds = await getAudioDurationSeconds(file)
    pendingFile.value = file
    pendingMimeType.value = normalizedMimeType
    pendingDurationSeconds.value = durationSeconds
    pendingLabel.value = file.name
  } catch (err) {
    clearPending()
    error.value = err instanceof Error ? err.message : 'Unable to read the selected audio file.'
  }
}

function submitSample() {
  if (!pendingFile.value || !pendingDurationSeconds.value) {
    error.value = 'Choose or record an audio sample before uploading.'
    return
  }

  emit('submit', {
    file: pendingFile.value,
    mimeType: pendingMimeType.value,
    fileSizeBytes: pendingFile.value.size,
    durationSeconds: pendingDurationSeconds.value,
  })
  clearPending()
}

onBeforeUnmount(() => {
  cleanupStream()
  activeRecorder = null
})
</script>

<template>
  <div class="rounded-2xl border border-rose-200 bg-rose-50/60 p-4">
    <div class="flex flex-wrap gap-2">
      <button
        type="button"
        data-testid="voice-mode-record"
        class="rounded-full px-4 py-2 text-sm font-semibold transition"
        :class="mode === 'record' ? 'bg-stone-950 text-white' : 'bg-white text-stone-700 ring-1 ring-stone-200'"
        @click="mode = 'record'"
      >
        Record
      </button>
      <button
        type="button"
        data-testid="voice-mode-upload"
        class="rounded-full px-4 py-2 text-sm font-semibold transition"
        :class="mode === 'upload' ? 'bg-stone-950 text-white' : 'bg-white text-stone-700 ring-1 ring-stone-200'"
        @click="mode = 'upload'"
      >
        Upload file
      </button>
    </div>

    <div v-if="mode === 'record'" class="mt-4 space-y-3">
      <p class="text-sm text-stone-600">Record a short, clear sample directly in the browser.</p>
      <div class="flex flex-wrap items-center gap-3">
        <button
          v-if="!isRecording"
          type="button"
          data-testid="voice-start-recording"
          class="rounded-xl bg-rose-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-rose-600 disabled:cursor-not-allowed disabled:bg-rose-300"
          :disabled="props.isUploading"
          @click="startRecording"
        >
          Start recording
        </button>
        <button
          v-else
          type="button"
          data-testid="voice-stop-recording"
          class="rounded-xl bg-stone-950 px-4 py-2 text-sm font-semibold text-white transition hover:bg-stone-800"
          @click="stopRecording"
        >
          Stop recording
        </button>
        <span v-if="isRecording" class="text-sm font-medium text-rose-700">Recording in progress…</span>
      </div>
    </div>

    <div v-else class="mt-4 space-y-3">
      <p class="text-sm text-stone-600">Upload an existing audio clip in a supported format.</p>
      <input
        data-testid="voice-file-input"
        type="file"
        accept="audio/webm,audio/wav,audio/x-wav,audio/mpeg,audio/mp4,audio/x-m4a,audio/ogg"
        class="block w-full rounded-xl border border-dashed border-stone-300 bg-white px-4 py-3 text-sm text-stone-600"
        @change="handleFileChange"
      />
    </div>

    <div
      v-if="pendingFile && pendingDurationSeconds"
      class="mt-4 rounded-xl bg-white px-4 py-3 ring-1 ring-rose-200"
    >
      <p class="text-sm font-semibold text-stone-900">{{ pendingLabel || 'Sample ready' }}</p>
      <p class="mt-1 text-sm text-stone-600">{{ pendingDurationSeconds.toFixed(1) }} sec</p>
      <button
        type="button"
        data-testid="voice-submit-sample"
        class="mt-3 rounded-xl bg-stone-950 px-4 py-2 text-sm font-semibold text-white transition hover:bg-stone-800 disabled:cursor-not-allowed disabled:bg-stone-400"
        :disabled="props.isUploading"
        @click="submitSample"
      >
        Upload sample
      </button>
    </div>

    <div
      v-if="error"
      class="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
      role="alert"
    >
      {{ error }}
    </div>
  </div>
</template>

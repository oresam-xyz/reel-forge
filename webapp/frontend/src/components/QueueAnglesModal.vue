<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { queueJobs, suggestAngles as suggestHooks } from '../api/campaigns'

const props = defineProps<{ campaignId: number; vertical: string }>()
const emit = defineEmits<{ close: []; queued: [] }>()

const text = ref('')
const loading = ref(false)
const suggesting = ref(false)
const error = ref('')

async function fetchSuggestions() {
  suggesting.value = true
  error.value = ''
  try {
    const { angles } = await suggestHooks(props.campaignId)
    text.value = angles.join('\n')
  } catch {
    error.value = 'Could not generate suggestions — write your own hooks below.'
  } finally {
    suggesting.value = false
  }
}

onMounted(fetchSuggestions)

async function submit() {
  const hooks = text.value.split('\n').map((a) => a.trim()).filter(Boolean)
  if (!hooks.length) return
  loading.value = true
  try {
    await queueJobs(props.campaignId, hooks)
    emit('queued')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-6">
    <div class="bg-gray-900 border border-gray-800 rounded-2xl p-6 w-full max-w-lg space-y-4">
      <div class="flex items-center justify-between">
        <h2 class="font-semibold text-white">Queue Hooks</h2>
        <button class="text-gray-400 hover:text-white" @click="$emit('close')">✕</button>
      </div>

      <p class="text-sm text-gray-400">One hook per line. Each becomes a separate video job.</p>

      <!-- Generating state -->
      <div v-if="suggesting" class="flex items-center gap-2 text-sm text-indigo-400">
        <span class="animate-spin inline-block">⟳</span>
        Generating hook suggestions…
      </div>

      <p v-if="error" class="text-sm text-amber-400">{{ error }}</p>

      <textarea
        v-model="text"
        class="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-sm text-gray-200 resize-none focus:outline-none focus:border-gray-500"
        rows="8"
        placeholder="Enter one hook per line…"
      />

      <div class="flex gap-3">
        <button
          class="text-sm text-gray-400 hover:text-white flex items-center gap-1"
          :disabled="suggesting"
          @click="fetchSuggestions"
        >
          <span :class="suggesting ? 'animate-spin' : ''">⟳</span> Regenerate
        </button>
        <div class="flex-1" />
        <button class="bg-gray-800 hover:bg-gray-700 px-4 py-2.5 rounded-lg text-sm" @click="$emit('close')">Cancel</button>
        <button
          class="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 px-4 py-2.5 rounded-lg text-sm font-medium"
          :disabled="loading || suggesting"
          @click="submit"
        >
          {{ loading ? 'Queuing…' : 'Queue Jobs' }}
        </button>
      </div>
    </div>
  </div>
</template>

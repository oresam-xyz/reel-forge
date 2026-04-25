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
  <div class="fixed inset-0 z-50 flex items-center justify-center p-6" style="background: rgba(0,0,0,0.75); backdrop-filter: blur(4px)">
    <div class="w-full max-w-lg space-y-5 p-6 rounded-2xl"
      style="background: var(--bg-surface); border: 1px solid var(--border); box-shadow: 0 0 40px rgba(0,229,255,0.07)">

      <div class="flex items-center justify-between">
        <div>
          <div class="label mb-0.5">generate</div>
          <h2 class="text-lg font-bold tracking-tight" style="color: var(--text-primary)">Queue Hooks</h2>
        </div>
        <button class="mono text-lg leading-none transition-colors" style="color: var(--text-muted)"
          onmouseover="this.style.color='var(--cyan)'" onmouseout="this.style.color='var(--text-muted)'"
          @click="$emit('close')">✕</button>
      </div>

      <p class="text-sm" style="color: var(--text-muted)">One hook per line — each becomes a separate video job.</p>

      <!-- Generating state -->
      <div v-if="suggesting" class="flex items-center gap-2 text-sm" style="color: var(--cyan)">
        <span class="animate-spin inline-block mono">⟳</span>
        Generating hook suggestions…
      </div>

      <p v-if="error" class="text-sm" style="color: var(--amber)">{{ error }}</p>

      <textarea
        v-model="text"
        class="input-cyber resize-none"
        rows="8"
        placeholder="Enter one hook per line…"
      />

      <div class="flex gap-3 items-center">
        <button
          class="flex items-center gap-1.5 text-sm font-semibold transition-colors"
          style="color: var(--text-muted)"
          :class="{ 'opacity-40 cursor-not-allowed': suggesting }"
          :disabled="suggesting"
          onmouseover="this.style.color='var(--cyan)'" onmouseout="this.style.color='var(--text-muted)'"
          @click="fetchSuggestions"
        >
          <span :class="suggesting ? 'animate-spin' : ''" class="mono">⟳</span> Regenerate
        </button>
        <div class="flex-1" />
        <button class="btn-ghost" @click="$emit('close')">Cancel</button>
        <button
          class="btn-cyber"
          :class="{ 'opacity-40 cursor-not-allowed': loading || suggesting }"
          :disabled="loading || suggesting"
          @click="submit"
        >
          {{ loading ? 'Queuing…' : 'Queue Jobs' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  plan: Record<string, unknown>
  approving: boolean
  rejecting: boolean
}>()

const emit = defineEmits<{
  approve: [feedback: string]
  reject: [feedback: string]
}>()

const feedback = ref('')

const segments = (plan: Record<string, unknown>) =>
  (plan.segments as Array<Record<string, unknown>>) ?? []
</script>

<template>
  <div class="space-y-6">
    <!-- Hook -->
    <div class="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <p class="text-xs text-gray-500 uppercase tracking-wide mb-2">Hook</p>
      <p class="text-white text-lg font-medium leading-snug">{{ plan.hook }}</p>
    </div>

    <!-- Segments -->
    <div class="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
      <p class="text-xs text-gray-500 uppercase tracking-wide">Segments</p>
      <div
        v-for="(seg, i) in segments(plan)"
        :key="i"
        class="border-t border-gray-800 pt-3 first:border-0 first:pt-0"
      >
        <p class="text-xs text-gray-500 mb-1">Segment {{ i + 1 }} — {{ seg.duration_seconds }}s</p>
        <p class="text-gray-200 text-sm mb-1">{{ seg.narration }}</p>
        <p class="text-gray-500 text-xs italic">Visual: {{ seg.visual_brief }}</p>
      </div>
    </div>

    <!-- CTA + meta -->
    <div class="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <p class="text-xs text-gray-500 uppercase tracking-wide mb-2">CTA</p>
      <p class="text-white">{{ plan.cta }}</p>
      <p class="text-xs text-gray-500 mt-2">
        Est. duration: {{ plan.estimated_duration_seconds }}s · Tone: {{ plan.tone_guidance }}
      </p>
    </div>

    <!-- Feedback + actions -->
    <div class="space-y-3">
      <textarea
        v-model="feedback"
        class="w-full bg-gray-900 border border-gray-800 rounded-lg px-4 py-3 text-sm text-gray-200 placeholder-gray-600 resize-none focus:outline-none focus:border-gray-600"
        rows="3"
        placeholder="Changes to make before approving… (optional)"
      />
      <div class="flex gap-3">
        <button
          class="flex-1 bg-green-700 hover:bg-green-600 disabled:opacity-50 px-4 py-2.5 rounded-lg text-sm font-medium"
          :disabled="approving"
          @click="emit('approve', feedback)"
        >
          {{ approving ? 'Approving…' : '✓ Approve' }}
        </button>
        <button
          class="flex-1 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 px-4 py-2.5 rounded-lg text-sm font-medium text-red-400"
          :disabled="rejecting || !feedback.trim()"
          @click="emit('reject', feedback)"
        >
          {{ rejecting ? 'Rejecting…' : '✗ Reject with feedback' }}
        </button>
      </div>
    </div>
  </div>
</template>

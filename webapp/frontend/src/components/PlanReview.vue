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
  <div class="space-y-5">
    <!-- Hook -->
    <div class="card-cyber p-5">
      <div class="label mb-2">hook</div>
      <p class="text-lg font-bold leading-snug" style="color: var(--text-primary)">{{ plan.hook }}</p>
    </div>

    <!-- Segments -->
    <div class="card-cyber p-5 space-y-4">
      <div class="label">segments</div>
      <div
        v-for="(seg, i) in segments(plan)"
        :key="i"
        class="pt-3 space-y-1"
        :style="i > 0 ? 'border-top: 1px solid var(--border)' : ''"
      >
        <div class="label">Seg {{ i + 1 }} — {{ seg.duration_seconds }}s</div>
        <p class="text-sm" style="color: var(--text-primary)">{{ seg.narration }}</p>
        <p class="text-xs italic" style="color: var(--text-muted)">{{ seg.visual_brief }}</p>
      </div>
    </div>

    <!-- CTA + meta -->
    <div class="card-cyber p-5">
      <div class="label mb-2">cta</div>
      <p class="font-semibold" style="color: var(--cyan)">{{ plan.cta }}</p>
      <p class="text-xs mt-2" style="color: var(--text-muted)">
        Est. {{ plan.estimated_duration_seconds }}s · {{ plan.tone_guidance }}
      </p>
    </div>

    <!-- Feedback + actions -->
    <div class="space-y-3">
      <textarea
        v-model="feedback"
        class="input-cyber resize-none"
        rows="3"
        placeholder="Changes to make before approving… (optional)"
      />
      <div class="flex gap-3">
        <button
          class="flex-1 py-2.5 rounded-lg text-sm font-bold tracking-wide transition-all"
          style="background: rgba(57,255,20,0.1); color: var(--neon-green); border: 1px solid rgba(57,255,20,0.3)"
          :class="{ 'opacity-40 cursor-not-allowed': approving }"
          :disabled="approving"
          @click="emit('approve', feedback)"
        >
          {{ approving ? 'Approving…' : '✓ Approve' }}
        </button>
        <button
          class="btn-danger flex-1 py-2.5"
          :disabled="rejecting || !feedback.trim()"
          @click="emit('reject', feedback)"
        >
          {{ rejecting ? 'Rejecting…' : '✗ Reject' }}
        </button>
      </div>
    </div>
  </div>
</template>

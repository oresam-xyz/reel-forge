<script setup lang="ts">
import type { Job } from '../api/campaigns'
defineProps<{ job: Job }>()
defineEmits<{ view: [] }>()

const pillClass: Record<string, string> = {
  pending:        'pill pill-pending',
  running:        'pill pill-running',
  review_pending: 'pill pill-review',
  complete:       'pill pill-complete',
  failed:         'pill pill-failed',
}

function relativeTime(iso: string) {
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}
</script>

<template>
  <tr>
    <td class="px-4 py-3 max-w-xs truncate" style="color: var(--text-primary)">{{ job.angle }}</td>
    <td class="px-4 py-3">
      <span :class="pillClass[job.status]">{{ job.status.replace('_', ' ') }}</span>
    </td>
    <td class="px-4 py-3 mono text-xs capitalize" style="color: var(--text-muted)">{{ job.phase ?? '—' }}</td>
    <td class="px-4 py-3 mono text-xs">
      <span v-if="job.cost_usd != null && job.cost_usd > 0" style="color: #22d3ee; font-family: monospace">${{ job.cost_usd.toFixed(4) }}</span>
      <span v-else style="color: rgba(100,116,139,0.5)">—</span>
    </td>
    <td class="px-4 py-3 mono text-xs" style="color: rgba(100,116,139,0.6)">{{ relativeTime(job.created_at) }}</td>
    <td class="px-4 py-3 text-right">
      <button class="text-sm font-semibold transition-colors" style="color: var(--cyan)"
        onmouseover="this.style.textShadow='0 0 8px rgba(0,229,255,0.6)'"
        onmouseout="this.style.textShadow='none'"
        @click="$emit('view')">View →</button>
    </td>
  </tr>
</template>

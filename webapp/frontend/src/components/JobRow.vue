<script setup lang="ts">
import type { Job } from '../api/campaigns'
defineProps<{ job: Job }>()
defineEmits<{ view: [] }>()

const statusClass: Record<string, string> = {
  pending: 'bg-gray-800 text-gray-400',
  running: 'bg-blue-900 text-blue-300',
  review_pending: 'bg-amber-900 text-amber-300',
  complete: 'bg-green-900 text-green-300',
  failed: 'bg-red-900 text-red-400',
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
  <tr class="border-b border-gray-800 last:border-0 hover:bg-gray-800/40">
    <td class="px-4 py-3 text-gray-200 max-w-xs truncate">{{ job.angle }}</td>
    <td class="px-4 py-3">
      <span :class="['text-xs px-2 py-0.5 rounded-full font-medium', statusClass[job.status]]">
        {{ job.status.replace('_', ' ') }}
      </span>
    </td>
    <td class="px-4 py-3 text-gray-400 capitalize">{{ job.phase ?? '—' }}</td>
    <td class="px-4 py-3 text-gray-500 text-xs">{{ relativeTime(job.created_at) }}</td>
    <td class="px-4 py-3 text-right">
      <button class="text-indigo-400 hover:text-indigo-300 text-sm" @click="$emit('view')">View →</button>
    </td>
  </tr>
</template>

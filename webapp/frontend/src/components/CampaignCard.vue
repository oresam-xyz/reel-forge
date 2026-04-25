<script setup lang="ts">
import type { Campaign } from '../api/campaigns'
defineProps<{ campaign: Campaign }>()
</script>

<template>
  <div class="card-cyber cursor-pointer p-5">
    <div class="flex items-start justify-between mb-3">
      <h3 class="font-semibold truncate pr-2" style="color: var(--text-primary)">{{ campaign.name }}</h3>
      <span
        v-if="campaign.brief.vertical"
        class="mono flex-shrink-0 text-xs px-2 py-0.5 rounded"
        style="background: rgba(0,229,255,0.08); color: var(--cyan); border: 1px solid rgba(0,229,255,0.15)"
      >{{ campaign.brief.vertical }}</span>
    </div>
    <p class="text-sm line-clamp-2 mb-4" style="color: var(--text-muted)">{{ campaign.brief.product }}</p>
    <div class="flex flex-wrap gap-2">
      <span v-if="campaign.pending"       class="pill pill-pending">{{ campaign.pending }} pending</span>
      <span v-if="campaign.running"       class="pill pill-running">{{ campaign.running }} running</span>
      <span v-if="campaign.review_pending" class="pill pill-review">{{ campaign.review_pending }} review</span>
      <span v-if="campaign.complete"      class="pill pill-complete">{{ campaign.complete }} done</span>
      <span v-if="campaign.failed"        class="pill pill-failed">{{ campaign.failed }} failed</span>
    </div>
    <p class="mono text-xs mt-3" style="color: rgba(100,116,139,0.6)">{{ new Date(campaign.created_at).toLocaleDateString() }}</p>
  </div>
</template>

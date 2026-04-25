<script setup lang="ts">
import type { Campaign } from '../api/campaigns'
defineProps<{ campaign: Campaign }>()
</script>

<template>
  <div class="bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl p-5 cursor-pointer transition-colors">
    <div class="flex items-start justify-between mb-3">
      <h3 class="font-semibold text-white truncate pr-2">{{ campaign.name }}</h3>
      <span
        v-if="campaign.brief.vertical"
        class="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded-full flex-shrink-0"
      >{{ campaign.brief.vertical }}</span>
    </div>
    <p class="text-sm text-gray-400 line-clamp-2 mb-4">{{ campaign.brief.product }}</p>
    <div class="flex flex-wrap gap-2 text-xs">
      <span v-if="campaign.pending" class="bg-gray-800 text-gray-400 px-2 py-0.5 rounded-full">{{ campaign.pending }} pending</span>
      <span v-if="campaign.running" class="bg-blue-900 text-blue-300 px-2 py-0.5 rounded-full">{{ campaign.running }} running</span>
      <span v-if="campaign.review_pending" class="bg-amber-900 text-amber-300 px-2 py-0.5 rounded-full">{{ campaign.review_pending }} review</span>
      <span v-if="campaign.complete" class="bg-green-900 text-green-300 px-2 py-0.5 rounded-full">{{ campaign.complete }} done</span>
      <span v-if="campaign.failed" class="bg-red-900 text-red-400 px-2 py-0.5 rounded-full">{{ campaign.failed }} failed</span>
    </div>
    <p class="text-xs text-gray-600 mt-3">{{ new Date(campaign.created_at).toLocaleDateString() }}</p>
  </div>
</template>

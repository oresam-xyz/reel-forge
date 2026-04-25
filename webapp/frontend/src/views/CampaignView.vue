<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getCampaign, type CampaignDetail } from '../api/campaigns'
import JobRow from '../components/JobRow.vue'
import QueueAnglesModal from '../components/QueueAnglesModal.vue'

const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)
const campaign = ref<CampaignDetail | null>(null)
const showQueue = ref(false)
let pollInterval: ReturnType<typeof setInterval>

async function load() {
  campaign.value = await getCampaign(id)
}

function startPolling() {
  pollInterval = setInterval(load, 10_000)
}

onMounted(async () => {
  await load()
  startPolling()
})
onUnmounted(() => clearInterval(pollInterval))

async function handleQueued() {
  showQueue.value = false
  await load()
}
</script>

<template>
  <div class="min-h-screen bg-gray-950 text-white">
    <header class="border-b border-gray-800 px-6 py-4 flex items-center gap-3">
      <button class="text-gray-400 hover:text-white text-sm" @click="router.push('/')">← Campaigns</button>
      <span class="text-gray-600">/</span>
      <span class="font-semibold">{{ campaign?.name }}</span>
    </header>

    <main v-if="campaign" class="max-w-5xl mx-auto px-6 py-8">
      <!-- Brief card -->
      <details class="bg-gray-900 border border-gray-800 rounded-xl mb-6 group">
        <summary class="px-5 py-4 cursor-pointer text-sm font-medium text-gray-300 select-none">
          Brief — {{ campaign.brief.vertical || 'General' }}
        </summary>
        <div class="px-5 pb-4 grid grid-cols-2 gap-3 text-sm text-gray-400">
          <div><span class="text-gray-500">Product</span><p class="text-gray-200 mt-0.5">{{ campaign.brief.product }}</p></div>
          <div><span class="text-gray-500">Audience</span><p class="text-gray-200 mt-0.5">{{ campaign.brief.audience }}</p></div>
          <div><span class="text-gray-500">Pain point</span><p class="text-gray-200 mt-0.5">{{ campaign.brief.pain_point }}</p></div>
          <div><span class="text-gray-500">CTA</span><p class="text-gray-200 mt-0.5">{{ campaign.brief.cta }}</p></div>
        </div>
      </details>

      <!-- Jobs table -->
      <div class="flex items-center justify-between mb-4">
        <h3 class="font-semibold text-gray-200">Jobs</h3>
        <button
          class="bg-indigo-600 hover:bg-indigo-500 px-4 py-2 rounded-lg text-sm font-medium"
          @click="showQueue = true"
        >
          + Queue Hooks
        </button>
      </div>

      <div v-if="campaign.jobs.length === 0" class="text-gray-500 text-sm py-10 text-center">
        No jobs queued yet.
      </div>

      <div v-else class="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <table class="w-full text-sm">
          <thead class="border-b border-gray-800">
            <tr class="text-gray-500 text-xs uppercase tracking-wide">
              <th class="px-4 py-3 text-left">Hook</th>
              <th class="px-4 py-3 text-left">Status</th>
              <th class="px-4 py-3 text-left">Phase</th>
              <th class="px-4 py-3 text-left">Created</th>
              <th class="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            <JobRow
              v-for="job in campaign.jobs"
              :key="job.id"
              :job="job"
              @view="router.push(`/jobs/${job.id}`)"
            />
          </tbody>
        </table>
      </div>
    </main>

    <QueueAnglesModal
      v-if="showQueue && campaign"
      :campaign-id="id"
      :vertical="campaign.brief.vertical"
      @close="showQueue = false"
      @queued="handleQueued"
    />
  </div>
</template>

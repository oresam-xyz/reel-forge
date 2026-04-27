<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getCampaign, deleteCampaign, type CampaignDetail } from '../api/campaigns'
import JobRow from '../components/JobRow.vue'
import QueueAnglesModal from '../components/QueueAnglesModal.vue'

const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)
const campaign = ref<CampaignDetail | null>(null)
const showQueue = ref(false)
const deleting = ref(false)
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

async function handleDelete() {
  if (!confirm('Delete this campaign and all its jobs?')) return
  deleting.value = true
  try {
    await deleteCampaign(id)
    router.push('/campaigns')
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <div class="min-h-screen text-white">
    <header class="site-header px-6 py-4 flex items-center gap-3">
      <button class="label transition-colors hover:text-gray-300" @click="router.push('/campaigns')">← Campaigns</button>
      <span style="color: var(--border)">/</span>
      <span class="font-semibold" style="color: var(--text-primary)">{{ campaign?.name }}</span>
      <div class="ml-auto">
        <button
          class="mono text-xs transition-colors"
          :disabled="deleting"
          :style="deleting
            ? 'color: var(--red); opacity: 0.5; cursor: not-allowed'
            : 'color: var(--red); opacity: 0.7'"
          @mouseover="(e) => { if (!deleting) (e.target as HTMLElement).style.opacity = '1' }"
          @mouseout="(e) => { if (!deleting) (e.target as HTMLElement).style.opacity = '0.7' }"
          @click="handleDelete"
        >{{ deleting ? '[ deleting… ]' : '[ delete campaign ]' }}</button>
      </div>
    </header>

    <main v-if="campaign" class="max-w-5xl mx-auto px-6 py-8">
      <!-- Brief card -->
      <details class="card-cyber mb-6 group">
        <summary class="px-5 py-4 cursor-pointer select-none flex items-center gap-2"
          style="color: var(--text-muted)">
          <span class="mono text-xs" style="color: var(--cyan)">▶</span>
          <span class="label">Brief — {{ campaign.brief.vertical || 'General' }}</span>
        </summary>
        <div class="px-5 pb-5 grid grid-cols-2 gap-4 text-sm" style="border-top: 1px solid var(--border)">
          <div class="pt-4">
            <span class="label">Product</span>
            <p class="mt-1" style="color: var(--text-primary)">{{ campaign.brief.product }}</p>
          </div>
          <div class="pt-4">
            <span class="label">Audience</span>
            <p class="mt-1" style="color: var(--text-primary)">{{ campaign.brief.audience }}</p>
          </div>
          <div>
            <span class="label">Pain point</span>
            <p class="mt-1" style="color: var(--text-primary)">{{ campaign.brief.pain_point }}</p>
          </div>
          <div>
            <span class="label">CTA</span>
            <p class="mt-1" style="color: var(--cyan)">{{ campaign.brief.cta }}</p>
          </div>
        </div>
      </details>

      <!-- Jobs table -->
      <div class="flex items-center justify-between mb-4">
        <div>
          <div class="label mb-0.5">queue</div>
          <h3 class="font-bold text-lg" style="color: var(--text-primary)">Jobs</h3>
        </div>
        <button class="btn-cyber" @click="showQueue = true">+ Queue Hooks</button>
      </div>

      <div v-if="campaign.jobs.length === 0" class="text-center py-16">
        <div class="mono text-3xl mb-3" style="color: var(--border)">◻</div>
        <p class="text-sm" style="color: var(--text-muted)">No jobs queued yet.</p>
      </div>

      <div v-else class="card-cyber overflow-hidden">
        <table class="w-full table-cyber">
          <thead>
            <tr>
              <th class="text-left">Hook</th>
              <th class="text-left">Status</th>
              <th class="text-left">Phase</th>
              <th class="text-left">Cost</th>
              <th class="text-left">Created</th>
              <th></th>
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

      <div v-if="campaign.total_cost_usd != null && campaign.total_cost_usd > 0"
        class="mt-3 text-right">
        <span class="label">Total production cost:&nbsp;</span>
        <span class="mono text-xs" style="color: #22d3ee; font-family: monospace">${{ campaign.total_cost_usd.toFixed(4) }}</span>
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

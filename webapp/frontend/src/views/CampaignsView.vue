<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listCampaigns, createCampaign, type Campaign, type Brief } from '../api/campaigns'
import { useAuthStore } from '../stores/auth'
import { useRouter, RouterLink } from 'vue-router'
import CampaignCard from '../components/CampaignCard.vue'
import NewCampaignModal from '../components/NewCampaignModal.vue'

const auth = useAuthStore()
const router = useRouter()
const campaigns = ref<Campaign[]>([])
const showNew = ref(false)

async function load() {
  campaigns.value = await listCampaigns()
}

async function handleCreate(data: { name: string; brief: Brief; brand_name: string; auto_approve: boolean; visual_model: string; target_duration: number }) {
  await createCampaign(data)
  showNew.value = false
  await load()
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}

onMounted(load)
</script>

<template>
  <div class="min-h-screen text-white">
    <!-- Header -->
    <header class="site-header px-6 py-4 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <span class="mono text-xs" style="color: var(--cyan)">◈</span>
        <span class="font-bold text-lg tracking-tight" style="color: var(--text-primary)">Reel-Forge</span>
      </div>
      <div class="flex items-center gap-5">
        <span class="mono text-xs" style="color: var(--text-muted)">{{ auth.email }}</span>
        <RouterLink to="/settings" class="label hover:text-gray-300 transition-colors">[ settings ]</RouterLink>
        <button class="label hover:text-gray-300 transition-colors" @click="handleLogout">[ logout ]</button>
      </div>
    </header>

    <main class="max-w-6xl mx-auto px-6 py-8">
      <div class="flex items-center justify-between mb-7">
        <div>
          <div class="label mb-1">pipeline</div>
          <h2 class="text-2xl font-bold tracking-tight" style="color: var(--text-primary)">Campaigns</h2>
        </div>
        <button class="btn-cyber" @click="showNew = true">+ New Campaign</button>
      </div>

      <div v-if="campaigns.length === 0" class="text-center py-24">
        <div class="mono text-4xl mb-4" style="color: var(--border)">◻</div>
        <p style="color: var(--text-muted)">No campaigns yet. Create one to start generating ads.</p>
      </div>

      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <CampaignCard
          v-for="c in campaigns"
          :key="c.id"
          :campaign="c"
          @click="router.push(`/campaigns/${c.id}`)"
        />
      </div>
    </main>

    <NewCampaignModal v-if="showNew" @close="showNew = false" @submit="handleCreate" />
  </div>
</template>

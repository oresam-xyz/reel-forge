<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listCampaigns, createCampaign, type Campaign, type Brief } from '../api/campaigns'
import { useAuthStore } from '../stores/auth'
import { useRouter } from 'vue-router'
import CampaignCard from '../components/CampaignCard.vue'
import NewCampaignModal from '../components/NewCampaignModal.vue'

const auth = useAuthStore()
const router = useRouter()
const campaigns = ref<Campaign[]>([])
const showNew = ref(false)

async function load() {
  campaigns.value = await listCampaigns()
}

async function handleCreate(data: { name: string; brief: Brief; brand_name: string }) {
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
  <div class="min-h-screen bg-gray-950 text-white">
    <!-- Header -->
    <header class="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
      <span class="font-bold text-lg tracking-tight">Reel-Forge</span>
      <div class="flex items-center gap-4">
        <span class="text-gray-400 text-sm">{{ auth.email }}</span>
        <button class="text-sm text-gray-400 hover:text-white" @click="handleLogout">Logout</button>
      </div>
    </header>

    <main class="max-w-6xl mx-auto px-6 py-8">
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-xl font-semibold">Campaigns</h2>
        <button
          class="bg-indigo-600 hover:bg-indigo-500 px-4 py-2 rounded-lg text-sm font-medium"
          @click="showNew = true"
        >
          + New Campaign
        </button>
      </div>

      <div v-if="campaigns.length === 0" class="text-gray-500 text-center py-20">
        No campaigns yet. Create one to start generating ads.
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

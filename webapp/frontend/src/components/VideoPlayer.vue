<script setup lang="ts">
import { useRouter } from 'vue-router'

const props = defineProps<{ src: string; jobId: number; campaignId: number }>()
const router = useRouter()
</script>

<template>
  <div class="space-y-5">
    <div class="rounded-xl overflow-hidden mx-auto" style="max-width: 280px; border: 1px solid var(--border); box-shadow: 0 0 24px rgba(0,229,255,0.08)">
      <video
        :src="props.src"
        controls
        class="w-full bg-black block"
        style="aspect-ratio: 9/16"
      />
    </div>
    <div class="flex gap-3 justify-center">
      <a :href="props.src" download class="btn-ghost">↓ Download</a>
      <button class="btn-cyber" @click="router.push(`/campaigns/${props.campaignId}`)">
        Queue another hook →
      </button>
    </div>
  </div>
</template>

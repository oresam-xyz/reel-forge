<script setup lang="ts">
import { useRouter } from 'vue-router'

const props = defineProps<{ src: string; jobId: number; campaignId: number }>()
const router = useRouter()
</script>

<template>
  <div class="space-y-4">
    <video
      :src="props.src"
      controls
      class="w-full max-w-sm mx-auto rounded-xl bg-black"
      style="aspect-ratio: 9/16; max-height: 560px"
    />
    <div class="flex gap-3 justify-center">
      <a
        :href="props.src"
        download
        class="bg-gray-800 hover:bg-gray-700 px-4 py-2 rounded-lg text-sm font-medium"
      >
        ↓ Download
      </a>
      <button
        class="bg-indigo-600 hover:bg-indigo-500 px-4 py-2 rounded-lg text-sm font-medium"
        @click="router.push(`/campaigns/${props.campaignId}`)"
      >
        Queue another hook →
      </button>
    </div>
  </div>
</template>

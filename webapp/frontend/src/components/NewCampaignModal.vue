<script setup lang="ts">
import { reactive } from 'vue'
import type { Brief } from '../api/campaigns'

const emit = defineEmits<{
  close: []
  submit: [data: { name: string; brief: Brief; brand_name: string }]
}>()

const form = reactive({
  name: '',
  brand_name: 'oresam',
  brief: {
    product: 'Custom software builds — websites, AI agents, and automations by Samuel O\'Regan',
    audience: '',
    pain_point: '',
    cta: 'Visit oresam.xyz to get a quote',
    tone: 'direct',
    vertical: '',
  } as Brief,
})

function submit() {
  emit('submit', {
    name: form.name,
    brand_name: form.brand_name,
    brief: { ...form.brief },
  })
}
</script>

<template>
  <div class="fixed inset-0 bg-black/70 z-50 flex items-center justify-end">
    <div class="bg-gray-900 border-l border-gray-800 h-full w-full max-w-md overflow-y-auto p-6 space-y-5">
      <div class="flex items-center justify-between">
        <h2 class="font-semibold text-white">New Campaign</h2>
        <button class="text-gray-400 hover:text-white" @click="$emit('close')">✕</button>
      </div>

      <div class="space-y-4 text-sm">
        <label class="block">
          <span class="text-gray-400">Campaign name</span>
          <input v-model="form.name" class="mt-1 w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-200 text-sm focus:outline-none focus:border-gray-500" placeholder="Plumbers Cape Town Q2" />
        </label>

        <label class="block">
          <span class="text-gray-400">Vertical</span>
          <select v-model="form.brief.vertical" class="mt-1 w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-200 text-sm focus:outline-none focus:border-gray-500">
            <option value="">General</option>
            <option>plumbers</option>
            <option>attorneys</option>
            <option>builders</option>
            <option>bookkeepers</option>
            <option>other</option>
          </select>
        </label>

        <label class="block">
          <span class="text-gray-400">Product description</span>
          <textarea v-model="form.brief.product" class="mt-1 w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-200 text-sm focus:outline-none focus:border-gray-500 resize-none" rows="3" />
        </label>

        <label class="block">
          <span class="text-gray-400">Target audience</span>
          <textarea v-model="form.brief.audience" class="mt-1 w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-200 text-sm focus:outline-none focus:border-gray-500 resize-none" rows="2"
            placeholder="Cape Town plumbers with no website" />
        </label>

        <label class="block">
          <span class="text-gray-400">Pain point</span>
          <textarea v-model="form.brief.pain_point" class="mt-1 w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-200 text-sm focus:outline-none focus:border-gray-500 resize-none" rows="2"
            placeholder="Losing customers to competitors who appear online" />
        </label>

        <label class="block">
          <span class="text-gray-400">Call to action</span>
          <input v-model="form.brief.cta" class="mt-1 w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-200 text-sm focus:outline-none focus:border-gray-500" />
        </label>

        <label class="block">
          <span class="text-gray-400">Tone</span>
          <select v-model="form.brief.tone" class="mt-1 w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-200 text-sm focus:outline-none focus:border-gray-500">
            <option>direct</option>
            <option>conversational</option>
            <option>urgent</option>
            <option>friendly</option>
          </select>
        </label>

        <label class="block">
          <span class="text-gray-400">Brand</span>
          <input v-model="form.brand_name" class="mt-1 w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-200 text-sm focus:outline-none focus:border-gray-500" placeholder="oresam" />
        </label>
      </div>

      <div class="flex gap-3 pt-2">
        <button class="flex-1 bg-gray-800 hover:bg-gray-700 px-4 py-2.5 rounded-lg text-sm" @click="$emit('close')">Cancel</button>
        <button class="flex-1 bg-indigo-600 hover:bg-indigo-500 px-4 py-2.5 rounded-lg text-sm font-medium" @click="submit">Create</button>
      </div>
    </div>
  </div>
</template>


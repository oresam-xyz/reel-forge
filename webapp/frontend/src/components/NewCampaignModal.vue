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
  emit('submit', { name: form.name, brand_name: form.brand_name, brief: { ...form.brief } })
}
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-end" style="background: rgba(0,0,0,0.7); backdrop-filter: blur(4px)">
    <div class="h-full w-full max-w-md overflow-y-auto p-6 space-y-5 flex flex-col"
      style="background: var(--bg-surface); border-left: 1px solid var(--border)">

      <div class="flex items-center justify-between">
        <div>
          <div class="label mb-0.5">create</div>
          <h2 class="text-lg font-bold tracking-tight" style="color: var(--text-primary)">New Campaign</h2>
        </div>
        <button class="mono text-lg leading-none transition-colors" style="color: var(--text-muted)"
          onmouseover="this.style.color='var(--cyan)'" onmouseout="this.style.color='var(--text-muted)'"
          @click="$emit('close')">✕</button>
      </div>

      <div class="space-y-4 text-sm flex-1">
        <label class="block">
          <span class="label">Campaign name</span>
          <input v-model="form.name" class="input-cyber mt-1" placeholder="Plumbers Cape Town Q2" />
        </label>

        <label class="block">
          <span class="label">Vertical</span>
          <select v-model="form.brief.vertical" class="input-cyber mt-1">
            <option value="">General</option>
            <option>plumbers</option>
            <option>attorneys</option>
            <option>builders</option>
            <option>bookkeepers</option>
            <option>other</option>
          </select>
        </label>

        <label class="block">
          <span class="label">Product description</span>
          <textarea v-model="form.brief.product" class="input-cyber mt-1 resize-none" rows="3" />
        </label>

        <label class="block">
          <span class="label">Target audience</span>
          <textarea v-model="form.brief.audience" class="input-cyber mt-1 resize-none" rows="2"
            placeholder="Cape Town plumbers with no website" />
        </label>

        <label class="block">
          <span class="label">Pain point</span>
          <textarea v-model="form.brief.pain_point" class="input-cyber mt-1 resize-none" rows="2"
            placeholder="Losing customers to competitors who appear online" />
        </label>

        <label class="block">
          <span class="label">Call to action</span>
          <input v-model="form.brief.cta" class="input-cyber mt-1" />
        </label>

        <label class="block">
          <span class="label">Tone</span>
          <select v-model="form.brief.tone" class="input-cyber mt-1">
            <option>direct</option>
            <option>conversational</option>
            <option>urgent</option>
            <option>friendly</option>
          </select>
        </label>

        <label class="block">
          <span class="label">Brand</span>
          <input v-model="form.brand_name" class="input-cyber mt-1" placeholder="oresam" />
        </label>
      </div>

      <div class="flex gap-3 pt-2">
        <button class="btn-ghost flex-1" @click="$emit('close')">Cancel</button>
        <button class="btn-cyber flex-1" @click="submit">Create</button>
      </div>
    </div>
  </div>
</template>

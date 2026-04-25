<script setup lang="ts">
import { reactive, onMounted } from 'vue'
import type { Brief } from '../api/campaigns'
import { getMe } from '../api/user'
import { listBrands } from '../api/brands'

const emit = defineEmits<{
  close: []
  submit: [data: { name: string; brief: Brief; brand_name: string; auto_approve: boolean; visual_model: string; target_duration: number }]
}>()

const MODELS = [
  { value: 'cogvideox-5b',      label: 'CogVideoX 5B · $0.020/s' },
  { value: 'kling-1.6',         label: 'Kling 1.6 · $0.030/s' },
  { value: 'kling-2.0-master',  label: 'Kling 2.0 Master · $0.040/s' },
  { value: 'kling-2.1-master',  label: 'Kling 2.1 Master · $0.050/s' },
  { value: 'kling-2.6-pro',     label: 'Kling 2.6 Pro · $0.070/s' },
  { value: 'kling-3-pro',       label: 'Kling 3 Pro · $0.224/s' },
  { value: 'wan-t2v',           label: 'Wan T2V · $0.030/s' },
  { value: 'wan-2.2',           label: 'Wan 2.2 · $0.100/s' },
  { value: 'veo-3.1',           label: 'Veo 3.1 · $0.200/s' },
  { value: 'ltx-video',         label: 'LTX Video · $0.040/s' },
  { value: 'seedance-2',        label: 'Seedance 2 · $0.300/s' },
]

const form = reactive({
  name: '',
  brand_name: 'oresam',
  auto_approve: false,
  visual_model: 'kling-2.6-pro',
  target_duration: 30,
  brief: {
    product: "Custom software builds — websites, AI agents, and automations by Samuel O'Regan",
    audience: '',
    pain_point: '',
    cta: 'Visit oresam.xyz to get a quote',
    tone: 'direct',
    vertical: '',
  } as Brief,
})

const brands = reactive<string[]>([])

onMounted(async () => {
  try {
    const [me, brandList] = await Promise.all([getMe(), listBrands()])
    if (me.settings?.visual_model) form.visual_model = me.settings.visual_model
    if (me.settings?.target_duration) form.target_duration = me.settings.target_duration
    brands.push(...brandList)
  } catch {
    // non-fatal — defaults remain
  }
})

function submit() {
  emit('submit', {
    name: form.name,
    brand_name: form.brand_name,
    brief: { ...form.brief },
    auto_approve: form.auto_approve,
    visual_model: form.visual_model,
    target_duration: form.target_duration,
  })
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
          <select v-if="brands.length" v-model="form.brand_name" class="input-cyber mt-1">
            <option v-for="b in brands" :key="b" :value="b">{{ b }}</option>
          </select>
          <input v-else v-model="form.brand_name" class="input-cyber mt-1" placeholder="oresam" />
        </label>

        <label class="block">
          <span class="label">Visual model</span>
          <select v-model="form.visual_model" class="input-cyber mt-1">
            <option v-for="m in MODELS" :key="m.value" :value="m.value">{{ m.label }}</option>
          </select>
        </label>

        <label class="block">
          <span class="label">Target duration</span>
          <select v-model.number="form.target_duration" class="input-cyber mt-1">
            <option :value="15">15 seconds</option>
            <option :value="30">30 seconds</option>
            <option :value="60">60 seconds</option>
            <option :value="90">90 seconds</option>
          </select>
        </label>

        <!-- Auto-approve toggle -->
        <div class="flex items-start gap-3 rounded-lg px-3 py-3"
          style="background: rgba(0,0,0,0.3); border: 1px solid var(--border)">
          <button
            type="button"
            class="relative flex-shrink-0 w-10 h-5 rounded-full transition-colors duration-200 focus:outline-none mt-0.5"
            :style="form.auto_approve
              ? 'background: rgba(0,229,255,0.25); border: 1px solid var(--cyan); box-shadow: 0 0 8px rgba(0,229,255,0.3)'
              : 'background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.12)'"
            @click="form.auto_approve = !form.auto_approve"
            :aria-pressed="form.auto_approve"
          >
            <span
              class="absolute top-0.5 left-0.5 w-3.5 h-3.5 rounded-full transition-transform duration-200"
              :style="form.auto_approve
                ? 'transform: translateX(20px); background: var(--cyan)'
                : 'transform: translateX(0); background: var(--text-muted)'"
            />
          </button>
          <div class="min-w-0">
            <div class="text-sm font-semibold" style="color: var(--text-primary)">Auto-approve plan</div>
            <div class="text-xs mt-0.5" style="color: var(--text-muted)">(skip review, go straight to assets)</div>
          </div>
        </div>
      </div>

      <div class="flex gap-3 pt-2">
        <button class="btn-ghost flex-1" @click="$emit('close')">Cancel</button>
        <button class="btn-cyber flex-1" @click="submit">Create</button>
      </div>
    </div>
  </div>
</template>

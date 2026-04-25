<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getJob, approveJob, rejectJob, retryJob, videoUrl, getPhaseData } from '../api/jobs'
import type { Job } from '../api/campaigns'
import PhaseStepper from '../components/PhaseStepper.vue'
import PlanReview from '../components/PlanReview.vue'
import VideoPlayer from '../components/VideoPlayer.vue'

const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)
const job = ref<Job | null>(null)
const approving = ref(false)
const rejecting = ref(false)
const selectedPhase = ref<string | null>(null)
const phaseData = ref<any>(null)
const phaseLoading = ref(false)
let pollInterval: ReturnType<typeof setInterval>

async function load() {
  job.value = await getJob(id)
}

function startPolling() {
  pollInterval = setInterval(load, 5_000)
}

onMounted(async () => {
  await load()
  startPolling()
})
onUnmounted(() => clearInterval(pollInterval))

const phaseStates = computed(() => {
  const phases = ['research', 'planning', 'review', 'script', 'assets', 'render']
  const currentPhase = job.value?.phase
  const status = job.value?.status

  return phases.map((p) => {
    if (status === 'complete') return { name: p, state: 'complete' as const }
    if (p === currentPhase) {
      if (status === 'failed') return { name: p, state: 'failed' as const }
      if (status === 'review_pending') return { name: p, state: 'review' as const }
      return { name: p, state: 'running' as const }
    }
    const idx = phases.indexOf(p)
    const curIdx = currentPhase ? phases.indexOf(currentPhase) : -1
    const s: 'complete' | 'pending' = idx < curIdx ? 'complete' : 'pending'
    return { name: p, state: s }
  })
})

async function selectPhase(name: string) {
  if (selectedPhase.value === name) {
    selectedPhase.value = null
    phaseData.value = null
    return
  }
  selectedPhase.value = name
  phaseData.value = null
  phaseLoading.value = true
  try {
    phaseData.value = await getPhaseData(id, name)
  } catch {
    phaseData.value = { error: 'Could not load phase data' }
  } finally {
    phaseLoading.value = false
  }
}

watch(() => job.value?.phase, () => {
  if (selectedPhase.value) {
    selectedPhase.value = null
    phaseData.value = null
  }
})

async function handleApprove(feedback: string) {
  approving.value = true
  try {
    await approveJob(id, feedback)
    await load()
  } finally {
    approving.value = false
  }
}

async function handleReject(feedback: string) {
  rejecting.value = true
  try {
    await rejectJob(id, feedback)
    await load()
  } finally {
    rejecting.value = false
  }
}

async function handleRetry() {
  await retryJob(id)
  await load()
}

function fmtBytes(n: number) {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}
</script>

<template>
  <div class="min-h-screen text-white">
    <header class="site-header px-6 py-4 flex items-center gap-3">
      <button class="label transition-colors hover:text-gray-300" @click="router.go(-1)">← Back</button>
      <span style="color: var(--border)">/</span>
      <span class="font-semibold truncate max-w-xs" style="color: var(--text-primary)">{{ job?.angle }}</span>
    </header>

    <main v-if="job" class="max-w-5xl mx-auto px-6 py-8 flex gap-8">
      <!-- Left: stepper + metadata -->
      <div class="w-52 flex-shrink-0">
        <div class="label mb-3">pipeline</div>
        <PhaseStepper :phases="phaseStates" :selected="selectedPhase ?? undefined" @select="selectPhase" />
        <div class="mt-6 space-y-2">
          <div>
            <div class="label">status</div>
            <span :class="`pill pill-${job.status.replace('_','-')} mt-0.5 inline-flex`">{{ job.status.replace('_', ' ') }}</span>
          </div>
          <div>
            <div class="label">created</div>
            <p class="mono text-xs mt-0.5" style="color: var(--text-muted)">{{ new Date(job.created_at).toLocaleString() }}</p>
          </div>
          <div>
            <div class="label">updated</div>
            <p class="mono text-xs mt-0.5" style="color: var(--text-muted)">{{ new Date(job.updated_at).toLocaleString() }}</p>
          </div>
        </div>
      </div>

      <!-- Right: phase detail OR status panel -->
      <div class="flex-1 min-w-0">

        <!-- Phase detail -->
        <template v-if="selectedPhase">
          <div class="flex items-center justify-between mb-5">
            <div>
              <div class="label mb-0.5">phase output</div>
              <h2 class="text-xl font-bold capitalize tracking-tight" style="color: var(--cyan)">{{ selectedPhase }}</h2>
            </div>
            <button class="btn-ghost text-xs px-3 py-1.5" @click="selectedPhase = null; phaseData = null">✕ close</button>
          </div>

          <div v-if="phaseLoading" class="mono text-sm py-8 text-center" style="color: var(--text-muted)">Loading…</div>
          <div v-else-if="phaseData?.error" class="text-sm" style="color: var(--red)">{{ phaseData.error }}</div>

          <!-- Research -->
          <div v-else-if="selectedPhase === 'research' && phaseData" class="space-y-4 text-sm">
            <div v-if="phaseData.key_facts?.length" class="card-cyber p-5">
              <div class="label mb-3">key facts</div>
              <ul class="space-y-2">
                <li v-for="(f, i) in phaseData.key_facts" :key="i"
                  class="pl-3 text-sm" style="color: var(--text-primary); border-left: 2px solid var(--border)">{{ f }}</li>
              </ul>
            </div>
          </div>

          <!-- Planning / Review -->
          <div v-else-if="(selectedPhase === 'planning' || selectedPhase === 'review') && phaseData" class="space-y-4 text-sm">
            <div class="card-cyber p-5 space-y-4">
              <p class="text-lg font-bold" style="color: var(--text-primary)">{{ phaseData.hook }}</p>
              <div v-if="phaseData.segments?.length" class="space-y-4 pt-2">
                <div v-for="(seg, i) in phaseData.segments" :key="i"
                  class="pl-3 space-y-1" style="border-left: 2px solid var(--border)">
                  <div class="label">Seg {{ i + 1 }} — {{ seg.duration_seconds }}s</div>
                  <p style="color: var(--text-primary)">{{ seg.narration }}</p>
                  <p class="text-xs italic" style="color: var(--text-muted)">{{ seg.visual_brief }}</p>
                </div>
              </div>
              <p v-if="phaseData.cta" class="font-semibold" style="color: var(--cyan)">↳ {{ phaseData.cta }}</p>
              <p v-if="phaseData.tone_guidance" class="text-xs" style="color: var(--text-muted)">{{ phaseData.tone_guidance }}</p>
              <p class="mono text-xs" style="color: rgba(100,116,139,0.5)">Est. {{ phaseData.estimated_duration_seconds }}s</p>
            </div>
          </div>

          <!-- Script -->
          <div v-else-if="selectedPhase === 'script' && phaseData" class="space-y-3 text-sm">
            <p v-if="phaseData.title" class="font-bold" style="color: var(--text-primary)">{{ phaseData.title }}</p>
            <div v-if="phaseData.segments?.length" class="space-y-3">
              <div v-for="seg in phaseData.segments" :key="seg.segment_id" class="card-cyber p-4 space-y-2">
                <div class="label">Seg {{ seg.segment_id }} — {{ seg.duration_seconds }}s</div>
                <p style="color: var(--text-primary)">{{ seg.narration }}</p>
                <p class="text-xs italic" style="color: var(--text-muted)">{{ seg.visual_prompt }}</p>
              </div>
            </div>
            <p class="mono text-xs" style="color: var(--text-muted)">Total: {{ phaseData.total_duration?.toFixed(1) }}s</p>
          </div>

          <!-- Assets -->
          <div v-else-if="selectedPhase === 'assets' && phaseData" class="space-y-2 text-sm">
            <div class="label mb-3">generated files</div>
            <div v-if="phaseData.files?.length" class="space-y-2">
              <div v-for="f in phaseData.files" :key="f.name"
                class="flex items-center gap-3 rounded-lg px-3 py-2.5"
                style="background: rgba(0,0,0,0.3); border: 1px solid var(--border)">
                <span class="mono text-xs px-2 py-0.5 rounded"
                  :style="f.type === 'mp4' ? 'background: rgba(0,229,255,0.1); color: var(--cyan); border: 1px solid rgba(0,229,255,0.2)'
                         : f.type === 'wav' || f.type === 'mp3' ? 'background: rgba(224,64,251,0.1); color: var(--magenta); border: 1px solid rgba(224,64,251,0.2)'
                         : 'background: rgba(255,255,255,0.05); color: var(--text-muted); border: 1px solid var(--border)'"
                >{{ f.type }}</span>
                <span class="mono text-xs flex-1" style="color: var(--text-primary)">{{ f.name }}</span>
                <span class="mono text-xs" style="color: var(--text-muted)">{{ fmtBytes(f.size_bytes) }}</span>
              </div>
            </div>
            <p v-else style="color: var(--text-muted)">No asset files found.</p>
          </div>

          <!-- Render -->
          <div v-else-if="selectedPhase === 'render' && phaseData" class="space-y-4 text-sm">
            <p v-if="phaseData.output_size_bytes" class="mono text-xs" style="color: var(--text-muted)">
              output.mp4 — {{ fmtBytes(phaseData.output_size_bytes) }}
            </p>
            <div v-if="phaseData.captions?.words?.length" class="card-cyber p-5">
              <div class="label mb-3">captions — {{ phaseData.captions.words.length }} words</div>
              <p class="leading-relaxed text-sm" style="color: var(--text-primary)">
                <span v-for="(w, i) in phaseData.captions.words" :key="i" class="mr-1">{{ w.word }}</span>
              </p>
            </div>
          </div>

          <div v-else class="text-sm" style="color: var(--text-muted)">No data available for this phase.</div>
        </template>

        <!-- Normal status panel -->
        <template v-else>
          <!-- Pending -->
          <div v-if="job.status === 'pending'" class="py-20 text-center">
            <div class="mono text-5xl mb-4 animate-pulse" style="color: var(--border)">⏳</div>
            <p style="color: var(--text-muted)">Waiting in queue…</p>
          </div>

          <!-- Running -->
          <div v-else-if="job.status === 'running'" class="py-20 text-center">
            <div class="mono text-5xl mb-4 animate-spin inline-block" style="color: var(--cyan)">⟳</div>
            <p class="mt-3 text-xl font-bold capitalize tracking-wide" style="color: var(--text-primary)">{{ job.phase }}</p>
            <p class="text-sm mt-1" style="color: var(--text-muted)">In progress — refreshing every 5s</p>
          </div>

          <!-- Review pending -->
          <PlanReview
            v-else-if="job.status === 'review_pending' && job.plan_json"
            :plan="job.plan_json"
            :approving="approving"
            :rejecting="rejecting"
            @approve="handleApprove"
            @reject="handleReject"
          />

          <!-- Complete -->
          <VideoPlayer
            v-else-if="job.status === 'complete'"
            :src="videoUrl(id)"
            :job-id="id"
            :campaign-id="job.campaign_id"
          />

          <!-- Failed -->
          <div v-else-if="job.status === 'failed'" class="space-y-4">
            <div class="rounded-xl p-5" style="background: rgba(255,61,61,0.06); border: 1px solid rgba(255,61,61,0.2)">
              <p class="mono text-xs mb-3" style="color: var(--red)">✗ FAILED AT: {{ job.phase }}</p>
              <pre class="text-xs whitespace-pre-wrap overflow-auto max-h-60" style="color: rgba(255,100,100,0.8); font-family: 'Share Tech Mono', monospace">{{ job.error }}</pre>
            </div>
            <button class="btn-ghost" @click="handleRetry">↺ Retry</button>
          </div>
        </template>

      </div>
    </main>
  </div>
</template>

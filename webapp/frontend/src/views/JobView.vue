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

// Clear phase selection if job moves forward
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
  <div class="min-h-screen bg-gray-950 text-white">
    <header class="border-b border-gray-800 px-6 py-4 flex items-center gap-3">
      <button class="text-gray-400 hover:text-white text-sm" @click="router.go(-1)">← Back</button>
      <span class="text-gray-600">/</span>
      <span class="font-semibold truncate max-w-xs">{{ job?.angle }}</span>
    </header>

    <main v-if="job" class="max-w-5xl mx-auto px-6 py-8 flex gap-8">
      <!-- Left: stepper + metadata -->
      <div class="w-56 flex-shrink-0">
        <PhaseStepper :phases="phaseStates" :selected="selectedPhase ?? undefined" @select="selectPhase" />
        <div class="mt-6 text-xs text-gray-500 space-y-1">
          <p><span class="text-gray-400">Status</span>: {{ job.status }}</p>
          <p><span class="text-gray-400">Brand</span>: {{ job.project_id?.split('_')[2] ?? '—' }}</p>
          <p><span class="text-gray-400">Created</span>: {{ new Date(job.created_at).toLocaleString() }}</p>
          <p><span class="text-gray-400">Updated</span>: {{ new Date(job.updated_at).toLocaleString() }}</p>
        </div>
      </div>

      <!-- Right: phase detail (when a phase is selected) OR status panel -->
      <div class="flex-1 min-w-0">

        <!-- Phase detail overlay -->
        <template v-if="selectedPhase">
          <div class="mb-4 flex items-center justify-between">
            <h2 class="font-semibold capitalize text-white">{{ selectedPhase }}</h2>
            <button class="text-xs text-gray-500 hover:text-white" @click="selectedPhase = null; phaseData = null">✕ close</button>
          </div>

          <div v-if="phaseLoading" class="text-gray-500 text-sm py-8 text-center">Loading…</div>

          <div v-else-if="phaseData?.error" class="text-red-400 text-sm">{{ phaseData.error }}</div>

          <!-- Research -->
          <div v-else-if="selectedPhase === 'research' && phaseData" class="space-y-4 text-sm">
            <div v-if="phaseData.key_facts?.length">
              <p class="text-gray-400 mb-2 font-medium">Key facts</p>
              <ul class="space-y-1">
                <li v-for="(f, i) in phaseData.key_facts" :key="i" class="text-gray-200 pl-3 border-l border-gray-700">{{ f }}</li>
              </ul>
            </div>
            <div v-if="phaseData.sources?.length">
              <p class="text-gray-400 mb-2 font-medium">Sources</p>
              <ul class="space-y-1">
                <li v-for="(s, i) in phaseData.sources" :key="i" class="text-gray-400">{{ s.url || s }}</li>
              </ul>
            </div>
          </div>

          <!-- Planning / Review -->
          <div v-else-if="(selectedPhase === 'planning' || selectedPhase === 'review') && phaseData" class="space-y-4 text-sm">
            <div class="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
              <p class="text-white font-semibold text-base">{{ phaseData.hook }}</p>
              <div v-if="phaseData.segments?.length" class="space-y-3 pt-2">
                <div v-for="(seg, i) in phaseData.segments" :key="i" class="border-l-2 border-gray-700 pl-3 space-y-1">
                  <p class="text-gray-400 text-xs font-medium">Segment {{ i + 1 }} — {{ seg.duration_seconds }}s</p>
                  <p class="text-gray-200">{{ seg.narration }}</p>
                  <p class="text-gray-500 italic">{{ seg.visual_brief }}</p>
                </div>
              </div>
              <p v-if="phaseData.cta" class="text-indigo-300 pt-1">CTA: {{ phaseData.cta }}</p>
              <p v-if="phaseData.tone_guidance" class="text-gray-500 text-xs">Tone: {{ phaseData.tone_guidance }}</p>
              <p class="text-gray-600 text-xs">Est. {{ phaseData.estimated_duration_seconds }}s</p>
            </div>
          </div>

          <!-- Script -->
          <div v-else-if="selectedPhase === 'script' && phaseData" class="space-y-4 text-sm">
            <p v-if="phaseData.title" class="text-gray-400 font-medium">{{ phaseData.title }}</p>
            <div v-if="phaseData.segments?.length" class="space-y-3">
              <div v-for="seg in phaseData.segments" :key="seg.segment_id" class="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-2">
                <p class="text-gray-500 text-xs font-medium">Segment {{ seg.segment_id }} — {{ seg.duration_seconds }}s</p>
                <p class="text-gray-200">{{ seg.narration }}</p>
                <p class="text-gray-500 italic text-xs">{{ seg.visual_prompt }}</p>
              </div>
            </div>
            <p class="text-gray-600 text-xs">Total: {{ phaseData.total_duration?.toFixed(1) }}s</p>
          </div>

          <!-- Assets -->
          <div v-else-if="selectedPhase === 'assets' && phaseData" class="space-y-2 text-sm">
            <p class="text-gray-400 font-medium mb-3">Generated files</p>
            <div v-if="phaseData.files?.length" class="space-y-1">
              <div v-for="f in phaseData.files" :key="f.name" class="flex items-center gap-3 bg-gray-900 border border-gray-800 rounded-lg px-3 py-2">
                <span class="text-xs font-mono px-1.5 py-0.5 rounded text-xs"
                  :class="f.type === 'mp4' ? 'bg-blue-900 text-blue-300' : f.type === 'wav' || f.type === 'mp3' ? 'bg-purple-900 text-purple-300' : 'bg-gray-800 text-gray-400'"
                >{{ f.type }}</span>
                <span class="text-gray-200 flex-1 font-mono text-xs">{{ f.name }}</span>
                <span class="text-gray-500 text-xs">{{ fmtBytes(f.size_bytes) }}</span>
              </div>
            </div>
            <p v-else class="text-gray-500">No asset files found.</p>
          </div>

          <!-- Render -->
          <div v-else-if="selectedPhase === 'render' && phaseData" class="space-y-4 text-sm">
            <p v-if="phaseData.output_size_bytes" class="text-gray-400">Output: {{ fmtBytes(phaseData.output_size_bytes) }}</p>
            <div v-if="phaseData.captions?.words?.length">
              <p class="text-gray-400 font-medium mb-2">Captions ({{ phaseData.captions.words.length }} words)</p>
              <div class="bg-gray-900 border border-gray-800 rounded-xl p-4 max-h-64 overflow-y-auto">
                <p class="text-gray-200 leading-relaxed">
                  <span
                    v-for="(w, i) in phaseData.captions.words"
                    :key="i"
                    class="mr-1 text-gray-300"
                  >{{ w.word }}</span>
                </p>
              </div>
            </div>
          </div>

          <div v-else class="text-gray-500 text-sm">No data available for this phase.</div>
        </template>

        <!-- Normal status panel (no phase selected) -->
        <template v-else>
          <!-- Pending -->
          <div v-if="job.status === 'pending'" class="text-gray-500 py-16 text-center">
            <div class="animate-pulse text-4xl mb-3">⏳</div>
            <p>Waiting in queue…</p>
          </div>

          <!-- Running -->
          <div v-else-if="job.status === 'running'" class="text-gray-400 py-16 text-center">
            <div class="animate-spin text-4xl mb-3 inline-block">⟳</div>
            <p class="mt-2 font-medium text-white capitalize">{{ job.phase }}</p>
            <p class="text-sm mt-1">In progress — refreshing every 5s</p>
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
            <div class="bg-red-950 border border-red-800 rounded-xl p-4">
              <p class="text-red-400 text-sm font-medium mb-2">Pipeline failed at: {{ job.phase }}</p>
              <pre class="text-red-300 text-xs whitespace-pre-wrap overflow-auto max-h-60">{{ job.error }}</pre>
            </div>
            <button
              class="bg-gray-800 hover:bg-gray-700 px-4 py-2 rounded-lg text-sm font-medium"
              @click="handleRetry"
            >
              Retry
            </button>
          </div>
        </template>

      </div>
    </main>
  </div>
</template>

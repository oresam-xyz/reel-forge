<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getJob, approveJob, rejectJob, retryJob, resetPhase, patchScript, videoUrl, getPhaseData, splitJobVideo, projectFileUrl, assetFileUrl } from '../api/jobs'
import type { ScriptSegmentPatch, SplitPart } from '../api/jobs'
import type { Job } from '../api/campaigns'
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
// Live assets progress (auto-polled during assets phase)
const assetsProgress = ref<{ name: string; size_bytes: number; type: string }[]>([])
const scriptSegmentCount = ref(0)

// Phase reset
const resettingPhase = ref<string | null>(null)
// Asset media player
const selectedClip = ref<string | null>(null)
const selectedAudio = ref<string | null>(null)

function toggleClip(name: string, type: string) {
  if (type === 'mp4') {
    selectedAudio.value = null
    selectedClip.value = selectedClip.value === name ? null : name
  } else if (type === 'wav' || type === 'mp3') {
    selectedClip.value = null
    selectedAudio.value = selectedAudio.value === name ? null : name
  }
}

// Video split
const showSplitPanel = ref(false)
const splitMaxMb = ref(10)
const splitting = ref(false)
const splitParts = ref<SplitPart[] | null>(null)
const splitError = ref('')

async function handleSplit() {
  splitting.value = true
  splitError.value = ''
  splitParts.value = null
  try {
    const result = await splitJobVideo(id, splitMaxMb.value)
    splitParts.value = result.parts
  } catch (e: any) {
    splitError.value = e?.response?.data?.detail ?? 'Split failed'
  } finally {
    splitting.value = false
  }
}

// Script editor
const scriptEditMode = ref(false)
const scriptDraft = ref<ScriptSegmentPatch[]>([])
const savingScript = ref(false)
let pollInterval: ReturnType<typeof setInterval>

async function load() {
  job.value = await getJob(id)
  if (job.value?.status === 'running' && job.value?.phase === 'assets') {
    try {
      const data = await getPhaseData(id, 'assets')
      assetsProgress.value = data.files ?? []
    } catch { /* non-fatal */ }
    if (!scriptSegmentCount.value) {
      try {
        const script = await getPhaseData(id, 'script')
        scriptSegmentCount.value = script.segments?.length ?? 0
      } catch { /* non-fatal */ }
    }
  } else if (job.value?.phase !== 'assets') {
    assetsProgress.value = []
    scriptSegmentCount.value = 0
  }
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
  selectedClip.value = null
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

const RESETABLE_PHASES = ['planning', 'script', 'assets', 'render']

async function handleResetPhase(phase: string) {
  resettingPhase.value = phase
  try {
    await resetPhase(id, phase)
    selectedPhase.value = null
    phaseData.value = null
    await load()
  } finally {
    resettingPhase.value = null
  }
}

function enterScriptEdit() {
  const segments: any[] = phaseData.value?.segments ?? []
  scriptDraft.value = segments.map((s: any) => ({
    segment_id: s.segment_id,
    narration: s.narration ?? '',
    visual_prompt: s.visual_prompt ?? '',
    duration_seconds: s.duration_seconds ?? 5,
  }))
  scriptEditMode.value = true
}

function cancelScriptEdit() {
  scriptEditMode.value = false
  scriptDraft.value = []
}

async function saveScript() {
  savingScript.value = true
  try {
    await patchScript(id, scriptDraft.value)
    scriptEditMode.value = false
    scriptDraft.value = []
    selectedPhase.value = null
    phaseData.value = null
    await load()
  } finally {
    savingScript.value = false
  }
}

const creditAlert = computed(() => {
  const err = job.value?.error ?? ''
  const m = err.match(/^\[CREDIT_LIMIT:([^\]]+)\]\s*(.*)$/)
  if (!m) return null
  return { provider: m[1], detail: m[2] || 'Account credit limit reached.' }
})

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
        <!-- Custom phase stepper with reset buttons -->
        <ol class="space-y-0.5">
          <li
            v-for="phase in phaseStates"
            :key="phase.name"
            class="flex items-center gap-2 rounded-lg px-2 py-2 transition-colors"
            :class="{
              'cursor-pointer': phase.state === 'complete' || phase.state === 'failed',
              'cursor-default': phase.state === 'pending' || phase.state === 'running' || phase.state === 'review',
            }"
            :style="selectedPhase === phase.name
              ? 'background: rgba(0,229,255,0.07); border-left: 2px solid var(--cyan); padding-left: 10px;'
              : 'border-left: 2px solid transparent'"
            @click="(phase.state === 'complete' || phase.state === 'failed') && selectPhase(phase.name)"
          >
            <!-- Icon -->
            <span class="phase-icon flex-shrink-0"
              :class="{
                'phase-complete': phase.state === 'complete',
                'phase-running animate-pulse': phase.state === 'running',
                'phase-review': phase.state === 'review',
                'phase-failed': phase.state === 'failed',
                'phase-pending': phase.state === 'pending',
              }"
            >
              <span v-if="phase.state === 'complete'">✓</span>
              <span v-else-if="phase.state === 'running'">⟳</span>
              <span v-else-if="phase.state === 'review'">!</span>
              <span v-else-if="phase.state === 'failed'">✗</span>
              <span v-else>○</span>
            </span>
            <!-- Label -->
            <span class="text-sm capitalize font-semibold tracking-wide flex-1 min-w-0 truncate"
              :style="{
                color: phase.state === 'complete' ? 'var(--neon-green)'
                     : phase.state === 'running'  ? 'var(--cyan)'
                     : phase.state === 'review'   ? 'var(--amber)'
                     : phase.state === 'failed'   ? 'var(--red)'
                     : 'rgba(100,116,139,0.5)',
              }"
            >{{ phase.name }}</span>
            <!-- Reset button for completed resetable phases -->
            <button
              v-if="phase.state === 'complete' && RESETABLE_PHASES.includes(phase.name)"
              class="mono text-xs flex-shrink-0 transition-opacity"
              :disabled="resettingPhase !== null"
              :style="resettingPhase === phase.name
                ? 'color: var(--cyan); opacity: 0.5; cursor: not-allowed'
                : 'color: var(--text-muted); opacity: 0.6'"
              :title="`Reset ${phase.name} phase`"
              @click.stop="handleResetPhase(phase.name)"
              @mouseover="(e) => { if (!resettingPhase) (e.target as HTMLElement).style.opacity = '1' }"
              @mouseout="(e) => { if (!resettingPhase) (e.target as HTMLElement).style.opacity = '0.6' }"
            >{{ resettingPhase === phase.name ? '…' : '↺' }}</button>
            <!-- Chevron for non-resettable clickable phases -->
            <span v-else-if="(phase.state === 'complete' || phase.state === 'failed') && !RESETABLE_PHASES.includes(phase.name)"
              class="ml-auto text-xs" style="color: var(--text-muted)">›</span>
          </li>
        </ol>
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
          <div v-if="job.cost_usd != null && job.cost_usd > 0">
            <div class="label">cost</div>
            <p class="mono text-xs mt-0.5" style="color: #22d3ee; font-family: monospace">${{ job.cost_usd.toFixed(4) }}</p>
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
                  <div class="label">Seg {{ (i as number) + 1 }} — {{ Number(seg.duration_seconds) }}s</div>
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
            <!-- Read mode -->
            <template v-if="!scriptEditMode">
              <div class="flex items-center justify-between">
                <p v-if="phaseData.title" class="font-bold" style="color: var(--text-primary)">{{ phaseData.title }}</p>
                <button
                  v-if="phaseData.segments?.length && !['assets','render'].includes(job?.phase ?? '') && job?.status !== 'complete'"
                  class="mono text-xs transition-colors ml-auto"
                  style="color: var(--cyan); opacity: 0.8"
                  @mouseover="(e) => (e.target as HTMLElement).style.opacity = '1'"
                  @mouseout="(e) => (e.target as HTMLElement).style.opacity = '0.8'"
                  @click="enterScriptEdit"
                >[ edit script ]</button>
              </div>
              <div v-if="phaseData.segments?.length" class="space-y-3">
                <div v-for="seg in phaseData.segments" :key="seg.segment_id" class="card-cyber p-4 space-y-2">
                  <div class="label">Seg {{ seg.segment_id }} — {{ seg.duration_seconds }}s</div>
                  <p style="color: var(--text-primary)">{{ seg.narration }}</p>
                  <p class="text-xs italic" style="color: var(--text-muted)">{{ seg.visual_prompt }}</p>
                </div>
              </div>
              <p class="mono text-xs" style="color: var(--text-muted)">Total: {{ phaseData.total_duration?.toFixed(1) }}s</p>
            </template>

            <!-- Edit mode -->
            <template v-else>
              <div class="flex items-center justify-between mb-1">
                <div class="label" style="color: var(--cyan)">editing script</div>
                <div class="mono text-xs" style="color: var(--text-muted)">changes reset assets + render</div>
              </div>
              <div class="space-y-4">
                <div v-for="(seg, i) in scriptDraft" :key="seg.segment_id"
                  class="card-cyber p-4 space-y-3">
                  <div class="flex items-center justify-between">
                    <div class="label">Seg {{ seg.segment_id }}</div>
                    <div class="flex items-center gap-2">
                      <span class="label">duration (s)</span>
                      <input
                        v-model.number="scriptDraft[i].duration_seconds"
                        type="number"
                        min="1"
                        max="30"
                        step="0.5"
                        class="input-cyber text-xs py-1 px-2"
                        style="width: 4.5rem"
                      />
                    </div>
                  </div>
                  <div>
                    <div class="label mb-1">narration</div>
                    <textarea
                      v-model="scriptDraft[i].narration"
                      class="input-cyber resize-none text-sm"
                      rows="3"
                      placeholder="Narration text…"
                    />
                  </div>
                  <div>
                    <div class="label mb-1">visual prompt</div>
                    <textarea
                      v-model="scriptDraft[i].visual_prompt"
                      class="input-cyber resize-none text-xs"
                      style="color: var(--text-muted)"
                      rows="2"
                      placeholder="Visual description…"
                    />
                  </div>
                </div>
              </div>
              <div class="flex gap-3 pt-2">
                <button
                  class="btn-ghost flex-1"
                  :disabled="savingScript"
                  @click="cancelScriptEdit"
                >[ cancel ]</button>
                <button
                  class="btn-cyber flex-1"
                  :disabled="savingScript"
                  @click="saveScript"
                >{{ savingScript ? '[ saving… ]' : '[ save &amp; regenerate ]' }}</button>
              </div>
            </template>
          </div>

          <!-- Assets -->
          <div v-else-if="selectedPhase === 'assets' && phaseData" class="space-y-3 text-sm">
            <!-- Inline video player -->
            <div v-if="selectedClip" class="rounded-xl overflow-hidden"
              style="border: 1px solid var(--border); box-shadow: 0 0 20px rgba(0,229,255,0.06)">
              <div class="flex items-center justify-between px-3 py-2"
                style="background: rgba(0,0,0,0.4); border-bottom: 1px solid var(--border)">
                <span class="mono text-xs" style="color: var(--cyan)">{{ selectedClip }}</span>
                <button type="button" class="mono text-xs transition-colors" style="color: var(--text-muted)"
                  @mouseover="(e) => (e.target as HTMLElement).style.color = 'var(--cyan)'"
                  @mouseout="(e) => (e.target as HTMLElement).style.color = 'var(--text-muted)'"
                  @click="selectedClip = null">✕ close</button>
              </div>
              <video :src="assetFileUrl(id, selectedClip)" :key="selectedClip" controls autoplay
                class="bg-black block" style="aspect-ratio: 9/16; max-width: 220px; max-height: 400px; margin: 0 auto" />
            </div>

            <!-- Inline audio player -->
            <div v-if="selectedAudio" class="rounded-xl overflow-hidden"
              style="border: 1px solid rgba(224,64,251,0.35); box-shadow: 0 0 20px rgba(224,64,251,0.06)">
              <div class="flex items-center justify-between px-3 py-2"
                style="background: rgba(0,0,0,0.4); border-bottom: 1px solid rgba(224,64,251,0.2)">
                <span class="mono text-xs" style="color: var(--magenta)">{{ selectedAudio }}</span>
                <button type="button" class="mono text-xs transition-colors" style="color: var(--text-muted)"
                  @mouseover="(e) => (e.target as HTMLElement).style.color = 'var(--magenta)'"
                  @mouseout="(e) => (e.target as HTMLElement).style.color = 'var(--text-muted)'"
                  @click="selectedAudio = null">✕ close</button>
              </div>
              <div class="px-4 py-3">
                <audio :src="assetFileUrl(id, selectedAudio)" :key="selectedAudio" controls autoplay class="w-full" style="accent-color: var(--magenta)" />
              </div>
            </div>

            <!-- File list -->
            <div v-if="phaseData.files?.length" class="space-y-1.5">
              <button
                v-for="f in phaseData.files"
                :key="f.name"
                type="button"
                class="w-full flex items-center gap-3 rounded-lg px-3 py-2.5 transition-colors text-left"
                :style="selectedClip === f.name
                  ? 'background: rgba(0,229,255,0.07); border: 1px solid var(--cyan); cursor: pointer'
                  : selectedAudio === f.name
                    ? 'background: rgba(224,64,251,0.07); border: 1px solid rgba(224,64,251,0.5); cursor: pointer'
                    : (f.type === 'mp4' || f.type === 'wav' || f.type === 'mp3')
                      ? 'background: rgba(0,0,0,0.3); border: 1px solid var(--border); cursor: pointer'
                      : 'background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.04); cursor: default'"
                @click="toggleClip(f.name, f.type)"
              >
                <span class="mono text-xs px-2 py-0.5 rounded flex-shrink-0"
                  :style="f.type === 'mp4'
                    ? 'background: rgba(0,229,255,0.1); color: var(--cyan); border: 1px solid rgba(0,229,255,0.2)'
                    : f.type === 'wav' || f.type === 'mp3'
                      ? 'background: rgba(224,64,251,0.1); color: var(--magenta); border: 1px solid rgba(224,64,251,0.2)'
                      : 'background: rgba(255,255,255,0.05); color: var(--text-muted); border: 1px solid var(--border)'"
                >{{ f.type }}</span>
                <span class="mono text-xs flex-1" style="color: var(--text-primary)">{{ f.name }}</span>
                <span class="mono text-xs" style="color: var(--text-muted)">{{ fmtBytes(f.size_bytes) }}</span>
                <span v-if="f.type === 'mp4' || f.type === 'wav' || f.type === 'mp3'"
                  class="mono text-xs flex-shrink-0"
                  :style="f.type === 'wav' || f.type === 'mp3' ? 'color: var(--magenta)' : 'color: var(--text-muted)'">
                  {{ (selectedClip === f.name || selectedAudio === f.name) ? '▲' : '▶' }}
                </span>
              </button>
            </div>
            <p v-else style="color: var(--text-muted)">No asset files found.</p>
          </div>

          <!-- Render -->
          <div v-else-if="selectedPhase === 'render' && phaseData" class="space-y-4 text-sm">
            <VideoPlayer :src="videoUrl(id)" :job-id="id" :campaign-id="job.campaign_id" />
            <p v-if="phaseData.output_size_bytes" class="mono text-xs text-center" style="color: var(--text-muted)">
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
          <div v-else-if="job.status === 'running'">
            <!-- Assets phase: show clip-by-clip progress -->
            <template v-if="job.phase === 'assets' && assetsProgress.length">
              <div class="mb-5 flex items-center gap-3">
                <div class="mono text-xl animate-spin inline-block flex-shrink-0" style="color: var(--cyan)">⟳</div>
                <div>
                  <p class="text-lg font-bold tracking-wide" style="color: var(--text-primary)">Generating Assets</p>
                  <p class="text-xs mt-0.5" style="color: var(--text-muted)">
                    {{ assetsProgress.filter(f => f.name.startsWith('clip_')).length }}
                    <template v-if="scriptSegmentCount"> / {{ scriptSegmentCount }}</template>
                    clips done — refreshing every 5s
                  </p>
                </div>
              </div>

              <!-- Progress bar -->
              <div v-if="scriptSegmentCount" class="mb-4 h-1.5 rounded-full overflow-hidden" style="background: rgba(255,255,255,0.07)">
                <div
                  class="h-full rounded-full transition-all duration-500"
                  style="background: var(--cyan)"
                  :style="{ width: (assetsProgress.filter(f => f.name.startsWith('clip_')).length / scriptSegmentCount * 100) + '%' }"
                />
              </div>

              <!-- Inline video player for live progress view -->
              <div v-if="selectedClip" class="mb-3 rounded-xl overflow-hidden"
                style="border: 1px solid var(--border); box-shadow: 0 0 20px rgba(0,229,255,0.06)">
                <div class="flex items-center justify-between px-3 py-2"
                  style="background: rgba(0,0,0,0.4); border-bottom: 1px solid var(--border)">
                  <span class="mono text-xs" style="color: var(--cyan)">{{ selectedClip }}</span>
                  <button type="button" class="mono text-xs transition-colors" style="color: var(--text-muted)"
                    @mouseover="(e) => (e.target as HTMLElement).style.color = 'var(--cyan)'"
                    @mouseout="(e) => (e.target as HTMLElement).style.color = 'var(--text-muted)'"
                    @click="selectedClip = null">✕ close</button>
                </div>
                <video :src="assetFileUrl(id, selectedClip)" :key="selectedClip" controls autoplay
                  class="bg-black block" style="aspect-ratio: 9/16; max-width: 220px; max-height: 400px; margin: 0 auto" />
              </div>

              <!-- Inline audio player for live progress view -->
              <div v-if="selectedAudio" class="mb-3 rounded-xl overflow-hidden"
                style="border: 1px solid rgba(224,64,251,0.35); box-shadow: 0 0 20px rgba(224,64,251,0.06)">
                <div class="flex items-center justify-between px-3 py-2"
                  style="background: rgba(0,0,0,0.4); border-bottom: 1px solid rgba(224,64,251,0.2)">
                  <span class="mono text-xs" style="color: var(--magenta)">{{ selectedAudio }}</span>
                  <button type="button" class="mono text-xs transition-colors" style="color: var(--text-muted)"
                    @mouseover="(e) => (e.target as HTMLElement).style.color = 'var(--magenta)'"
                    @mouseout="(e) => (e.target as HTMLElement).style.color = 'var(--text-muted)'"
                    @click="selectedAudio = null">✕ close</button>
                </div>
                <div class="px-4 py-3">
                  <audio :src="assetFileUrl(id, selectedAudio)" :key="selectedAudio" controls autoplay class="w-full" style="accent-color: var(--magenta)" />
                </div>
              </div>

              <div class="space-y-2">
                <button
                  v-for="f in assetsProgress"
                  :key="f.name"
                  type="button"
                  class="w-full flex items-center gap-3 rounded-lg px-3 py-2.5 transition-all text-left"
                  :style="selectedClip === f.name
                    ? 'background: rgba(0,229,255,0.07); border: 1px solid var(--cyan); cursor: pointer'
                    : selectedAudio === f.name
                      ? 'background: rgba(224,64,251,0.07); border: 1px solid rgba(224,64,251,0.5); cursor: pointer'
                      : 'background: rgba(0,0,0,0.3); border: 1px solid var(--border); cursor: pointer'"
                  @click="toggleClip(f.name, f.type)"
                >
                  <span class="mono text-xs px-2 py-0.5 rounded flex-shrink-0"
                    :style="f.type === 'mp4'
                      ? 'background: rgba(0,229,255,0.1); color: var(--cyan); border: 1px solid rgba(0,229,255,0.2)'
                      : 'background: rgba(224,64,251,0.1); color: var(--magenta); border: 1px solid rgba(224,64,251,0.2)'"
                  >{{ f.type }}</span>
                  <span class="mono text-xs flex-1" style="color: var(--text-primary)">{{ f.name }}</span>
                  <span class="mono text-xs" style="color: var(--text-muted)">{{ fmtBytes(f.size_bytes) }}</span>
                  <span class="text-xs"
                    :style="f.type === 'wav' || f.type === 'mp3' ? 'color: var(--magenta)' : 'color: var(--neon-green)'">
                    {{ (selectedClip === f.name || selectedAudio === f.name) ? '▲' : '▶' }}
                  </span>
                </button>

                <!-- Pending clips -->
                <template v-if="scriptSegmentCount">
                  <div
                    v-for="i in scriptSegmentCount - assetsProgress.filter(f => f.name.startsWith('clip_')).length"
                    :key="'pending-' + i"
                    class="flex items-center gap-3 rounded-lg px-3 py-2.5"
                    style="background: rgba(0,0,0,0.15); border: 1px solid rgba(255,255,255,0.04)">
                    <span class="mono text-xs px-2 py-0.5 rounded flex-shrink-0"
                      style="background: rgba(255,255,255,0.03); color: rgba(100,116,139,0.4); border: 1px solid rgba(255,255,255,0.06)">mp4</span>
                    <span class="mono text-xs flex-1 animate-pulse" style="color: rgba(100,116,139,0.4)">
                      clip_{{ String(assetsProgress.filter(f => f.name.startsWith('clip_')).length + i).padStart(2, '0') }}.mp4
                    </span>
                    <span class="mono text-xs animate-pulse" style="color: rgba(100,116,139,0.3)">generating…</span>
                  </div>
                </template>
              </div>
            </template>

            <!-- All other phases: standard spinner -->
            <template v-else>
              <div class="py-20 text-center">
                <div class="mono text-5xl mb-4 animate-spin inline-block" style="color: var(--cyan)">⟳</div>
                <p class="mt-3 text-xl font-bold capitalize tracking-wide" style="color: var(--text-primary)">{{ job.phase }}</p>
                <p class="text-sm mt-1" style="color: var(--text-muted)">In progress — refreshing every 5s</p>
              </div>
            </template>
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
          <template v-else-if="job.status === 'complete'">
            <VideoPlayer
              :src="videoUrl(id)"
              :job-id="id"
              :campaign-id="job.campaign_id"
            />
            <div v-if="job.cost_usd != null && job.cost_usd > 0" class="mt-4">
              <div class="label mb-0.5">production cost</div>
              <p class="mono text-sm" style="color: #22d3ee; font-family: monospace">${{ job.cost_usd.toFixed(4) }}</p>
            </div>

            <!-- Split for WhatsApp -->
            <div class="mt-5">
              <button
                class="mono text-xs transition-colors"
                style="color: var(--cyan); opacity: 0.8"
                @mouseover="(e) => (e.target as HTMLElement).style.opacity = '1'"
                @mouseout="(e) => (e.target as HTMLElement).style.opacity = '0.8'"
                @click="showSplitPanel = !showSplitPanel; splitParts = null; splitError = ''"
              >{{ showSplitPanel ? '[ ✕ close split ]' : '[ split for WhatsApp ]' }}</button>

              <div v-if="showSplitPanel" class="mt-3 space-y-3 rounded-xl p-4"
                style="background: rgba(0,0,0,0.3); border: 1px solid var(--border)">
                <div class="flex items-center gap-3">
                  <div class="label">max size</div>
                  <div class="flex items-center gap-2">
                    <input
                      v-model.number="splitMaxMb"
                      type="number"
                      min="1"
                      max="100"
                      step="1"
                      class="input-cyber text-xs py-1 px-2"
                      style="width: 5rem"
                    />
                    <span class="mono text-xs" style="color: var(--text-muted)">MB</span>
                  </div>
                  <button class="btn-cyber text-xs px-3 py-1.5 ml-auto" :disabled="splitting" @click="handleSplit">
                    {{ splitting ? '[ splitting… ]' : '[ split ]' }}
                  </button>
                </div>

                <p v-if="splitError" class="mono text-xs" style="color: var(--red)">{{ splitError }}</p>

                <div v-if="splitParts !== null" class="space-y-2">
                  <template v-if="splitParts.length === 1 && splitParts[0].filename === 'output.mp4'">
                    <p class="mono text-xs" style="color: var(--neon-green)">
                      ✓ Video is already under {{ splitMaxMb }} MB — no split needed.
                    </p>
                  </template>
                  <template v-else>
                    <div v-for="part in splitParts" :key="part.filename"
                      class="flex items-center gap-3 rounded-lg px-3 py-2"
                      style="background: rgba(0,0,0,0.3); border: 1px solid var(--border)">
                      <span class="mono text-xs flex-1" style="color: var(--text-primary)">{{ part.filename }}</span>
                      <span class="mono text-xs" style="color: var(--text-muted)">{{ part.size_mb }} MB</span>
                      <a
                        :href="projectFileUrl(id, part.filename)"
                        class="mono text-xs transition-colors"
                        style="color: var(--cyan)"
                        download
                      >↓ download</a>
                    </div>
                  </template>
                </div>
              </div>
            </div>
          </template>

          <!-- Failed -->
          <div v-else-if="job.status === 'failed'" class="space-y-4">
            <!-- Credit limit alert -->
            <div v-if="creditAlert" class="rounded-xl p-5 space-y-3"
              style="background: rgba(245,158,11,0.07); border: 1px solid rgba(245,158,11,0.35)">
              <div class="flex items-center gap-2">
                <span class="text-base">⚠</span>
                <p class="font-bold text-sm tracking-wide" style="color: #f59e0b">
                  {{ creditAlert.provider }} — Credit Limit Reached
                </p>
              </div>
              <p class="text-sm" style="color: rgba(245,158,11,0.85)">{{ creditAlert.detail }}</p>
              <p class="text-xs" style="color: rgba(245,158,11,0.55)">
                Top up your {{ creditAlert.provider }} account, then retry this job.
              </p>
            </div>

            <!-- Generic error -->
            <div v-else class="rounded-xl p-5" style="background: rgba(255,61,61,0.06); border: 1px solid rgba(255,61,61,0.2)">
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

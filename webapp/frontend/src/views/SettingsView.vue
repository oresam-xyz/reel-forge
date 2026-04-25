<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { listBrands, getBrand, patchBrand, type BrandIdentity } from '../api/brands'

const router = useRouter()
const userStore = useUserStore()

const activeTab = ref<'profile' | 'brands'>('profile')

// Profile
const nameInput = ref('')
const selectedModel = ref('kling-2.6-pro')
const selectedDuration = ref(30)
const savingProfile = ref(false)
const profileSaved = ref(false)

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

// Brands
const brandNames = ref<string[]>([])
const selectedBrand = ref<string | null>(null)
const brandData = ref<BrandIdentity | null>(null)
const brandLoading = ref(false)
const brandSaving = ref(false)
const brandSaved = ref(false)
const brandError = ref('')

// Local editable brand state
const brandForm = reactive({
  reading_pace: 'fast',
  voice_id: '',
  voice_speed: 1.0,
  image_prompt_prefix: '',
  pronunciations: {} as Record<string, string>,
})
const newPronKey = ref('')
const newPronValue = ref('')

onMounted(async () => {
  await userStore.fetch()
  const me = userStore.me
  if (me) {
    nameInput.value = me.name ?? ''
    selectedModel.value = me.settings?.visual_model ?? 'kling-2.6-pro'
    selectedDuration.value = me.settings?.target_duration ?? 30
  }
  brandNames.value = await listBrands()
})

async function saveSettings() {
  savingProfile.value = true
  profileSaved.value = false
  try {
    await userStore.saveName(nameInput.value)
    await userStore.saveSettings({ visual_model: selectedModel.value, target_duration: selectedDuration.value })
    profileSaved.value = true
    setTimeout(() => { profileSaved.value = false }, 2000)
  } finally {
    savingProfile.value = false
  }
}

async function selectBrand(name: string) {
  selectedBrand.value = name
  brandData.value = null
  brandLoading.value = true
  brandError.value = ''
  try {
    const data = await getBrand(name)
    brandData.value = data
    brandForm.reading_pace = data.tone?.reading_pace ?? 'fast'
    brandForm.voice_id = data.voice_profile?.voice_id ?? ''
    brandForm.voice_speed = data.voice_profile?.speed ?? 1.0
    brandForm.image_prompt_prefix = data.visual_style?.image_prompt_prefix ?? ''
    brandForm.pronunciations = { ...(data.pronunciations ?? {}) }
  } catch {
    brandError.value = 'Could not load brand'
  } finally {
    brandLoading.value = false
  }
}

function addPronunciation() {
  if (!newPronKey.value.trim()) return
  brandForm.pronunciations[newPronKey.value.trim()] = newPronValue.value
  newPronKey.value = ''
  newPronValue.value = ''
}

function removePronunciation(key: string) {
  delete brandForm.pronunciations[key]
}

async function saveBrand() {
  if (!selectedBrand.value) return
  brandSaving.value = true
  brandSaved.value = false
  brandError.value = ''
  try {
    await patchBrand(selectedBrand.value, {
      tone: { reading_pace: brandForm.reading_pace },
      voice_profile: { voice_id: brandForm.voice_id, speed: brandForm.voice_speed },
      visual_style: { image_prompt_prefix: brandForm.image_prompt_prefix },
      pronunciations: { ...brandForm.pronunciations },
    })
    brandSaved.value = true
    setTimeout(() => { brandSaved.value = false }, 2000)
  } catch (e: any) {
    brandError.value = e?.response?.data?.detail ?? 'Save failed'
  } finally {
    brandSaving.value = false
  }
}
</script>

<template>
  <div class="min-h-screen text-white">
    <header class="site-header px-6 py-4 flex items-center gap-3">
      <button class="label transition-colors hover:text-gray-300" @click="router.push('/')">← Back</button>
      <span style="color: var(--border)">/</span>
      <span class="font-semibold" style="color: var(--text-primary)">Settings</span>
    </header>

    <main class="max-w-2xl mx-auto px-6 py-8">
      <!-- Tabs -->
      <div class="flex gap-4 mb-8" style="border-bottom: 1px solid var(--border)">
        <button
          v-for="tab in (['profile', 'brands'] as const)"
          :key="tab"
          class="pb-3 text-sm font-semibold capitalize transition-colors"
          :style="activeTab === tab
            ? 'color: var(--cyan); border-bottom: 2px solid var(--cyan); margin-bottom: -1px'
            : 'color: var(--text-muted); border-bottom: 2px solid transparent; margin-bottom: -1px'"
          @click="activeTab = tab"
        >{{ tab }}</button>
      </div>

      <!-- Profile tab -->
      <div v-if="activeTab === 'profile'" class="space-y-6">
        <div class="card-cyber p-6 space-y-5">
          <div>
            <div class="label mb-0.5">profile</div>
            <h2 class="text-lg font-bold tracking-tight" style="color: var(--text-primary)">Account</h2>
          </div>

          <label class="block">
            <span class="label">Display name</span>
            <input v-model="nameInput" class="input-cyber mt-1" placeholder="Your name" />
          </label>

          <div>
            <div class="label mb-1">email</div>
            <p class="mono text-sm" style="color: var(--text-muted)">{{ userStore.me?.email }}</p>
          </div>

          <div>
            <div class="label mb-1">member since</div>
            <p class="mono text-sm" style="color: var(--text-muted)">
              {{ userStore.me ? new Date(userStore.me.created_at).toLocaleDateString() : '' }}
            </p>
          </div>
        </div>

        <div class="card-cyber p-6 space-y-5">
          <div>
            <div class="label mb-0.5">defaults</div>
            <h2 class="text-lg font-bold tracking-tight" style="color: var(--text-primary)">Pipeline Defaults</h2>
            <p class="text-xs mt-1" style="color: var(--text-muted)">Pre-fills new campaign form. Overridable per-campaign.</p>
          </div>

          <label class="block">
            <span class="label">Default visual model</span>
            <select v-model="selectedModel" class="input-cyber mt-1">
              <option v-for="m in MODELS" :key="m.value" :value="m.value">{{ m.label }}</option>
            </select>
          </label>

          <label class="block">
            <span class="label">Default target duration</span>
            <select v-model.number="selectedDuration" class="input-cyber mt-1">
              <option :value="15">15 seconds</option>
              <option :value="30">30 seconds</option>
              <option :value="60">60 seconds</option>
              <option :value="90">90 seconds</option>
            </select>
          </label>

          <div class="flex items-center gap-4 pt-1">
            <button class="btn-cyber" :disabled="savingProfile" @click="saveSettings">
              {{ savingProfile ? '[ saving… ]' : '[ Save Settings ]' }}
            </button>
            <span v-if="profileSaved" class="mono text-xs" style="color: var(--neon-green)">✓ saved</span>
          </div>
        </div>
      </div>

      <!-- Brands tab -->
      <div v-else-if="activeTab === 'brands'" class="space-y-4">
        <div class="card-cyber p-6">
          <div class="label mb-3">brands</div>
          <div v-if="brandNames.length === 0" style="color: var(--text-muted)" class="text-sm">No brands found.</div>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="name in brandNames"
              :key="name"
              class="px-3 py-1.5 rounded-lg text-sm font-semibold transition-colors"
              :style="selectedBrand === name
                ? 'background: rgba(0,229,255,0.15); color: var(--cyan); border: 1px solid var(--cyan)'
                : 'background: rgba(255,255,255,0.04); color: var(--text-muted); border: 1px solid var(--border)'"
              @click="selectBrand(name)"
            >{{ name }}</button>
          </div>
        </div>

        <div v-if="selectedBrand" class="card-cyber p-6 space-y-5">
          <div>
            <div class="label mb-0.5">editing</div>
            <h2 class="text-lg font-bold tracking-tight" style="color: var(--cyan)">{{ selectedBrand }}</h2>
          </div>

          <div v-if="brandLoading" class="mono text-sm py-4 text-center" style="color: var(--text-muted)">Loading…</div>

          <template v-else-if="brandData">
            <label class="block">
              <span class="label">Reading pace</span>
              <select v-model="brandForm.reading_pace" class="input-cyber mt-1">
                <option>slow</option>
                <option>medium</option>
                <option>fast</option>
              </select>
            </label>

            <label class="block">
              <span class="label">Voice ID (ElevenLabs)</span>
              <input v-model="brandForm.voice_id" class="input-cyber mt-1 mono text-xs" placeholder="21m00Tcm4TlvDq8ikWAM" />
            </label>

            <label class="block">
              <span class="label">Voice speed (0.5 – 2.0)</span>
              <input
                v-model.number="brandForm.voice_speed"
                type="number"
                min="0.5"
                max="2.0"
                step="0.1"
                class="input-cyber mt-1"
                style="max-width: 8rem"
              />
            </label>

            <label class="block">
              <span class="label">Image prompt prefix</span>
              <textarea v-model="brandForm.image_prompt_prefix" class="input-cyber mt-1 resize-none text-xs" rows="3" />
            </label>

            <!-- Pronunciations -->
            <div>
              <div class="label mb-3">pronunciations</div>
              <div class="space-y-2">
                <div
                  v-for="(val, key) in brandForm.pronunciations"
                  :key="key"
                  class="flex items-center gap-2"
                >
                  <span class="mono text-xs flex-shrink-0 px-2 py-1 rounded"
                    style="background: rgba(0,0,0,0.4); color: var(--text-muted); border: 1px solid var(--border); min-width: 8rem">{{ key }}</span>
                  <span class="mono text-xs" style="color: var(--text-muted)">→</span>
                  <input
                    :value="val"
                    @input="brandForm.pronunciations[key as string] = ($event.target as HTMLInputElement).value"
                    class="input-cyber text-xs py-1 flex-1"
                    placeholder="spoken form"
                  />
                  <button
                    class="mono text-xs flex-shrink-0 transition-colors"
                    style="color: var(--red); opacity: 0.7"
                    @mouseover="(e) => (e.target as HTMLElement).style.opacity = '1'"
                    @mouseout="(e) => (e.target as HTMLElement).style.opacity = '0.7'"
                    @click="removePronunciation(key as string)"
                  >✕</button>
                </div>

                <!-- Add new entry -->
                <div class="flex items-center gap-2 pt-1">
                  <input v-model="newPronKey" class="input-cyber text-xs py-1 flex-1" placeholder="word / phrase" />
                  <span class="mono text-xs" style="color: var(--text-muted)">→</span>
                  <input v-model="newPronValue" class="input-cyber text-xs py-1 flex-1" placeholder="spoken form" />
                  <button
                    class="mono text-xs flex-shrink-0 transition-colors px-2 py-1 rounded"
                    style="color: var(--cyan); border: 1px solid var(--cyan); background: rgba(0,229,255,0.06)"
                    @click="addPronunciation"
                  >+ add</button>
                </div>
              </div>
            </div>

            <p v-if="brandError" class="mono text-xs" style="color: var(--red)">{{ brandError }}</p>

            <div class="flex items-center gap-4 pt-1">
              <button class="btn-cyber" :disabled="brandSaving" @click="saveBrand">
                {{ brandSaving ? '[ saving… ]' : '[ Save Brand ]' }}
              </button>
              <span v-if="brandSaved" class="mono text-xs" style="color: var(--neon-green)">✓ saved</span>
            </div>
          </template>
        </div>
      </div>
    </main>
  </div>
</template>

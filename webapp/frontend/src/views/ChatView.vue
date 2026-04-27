<script setup lang="ts">
import { ref, nextTick, onMounted, computed } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { sendMessage, getChatHistory, type ChatMessage } from '../api/chat'
import { listBrands } from '../api/brands'

const auth = useAuthStore()
const router = useRouter()

const messages = ref<ChatMessage[]>([])
const input = ref('')
const loading = ref(false)
const bottomEl = ref<HTMLElement | null>(null)
const pendingAction = ref<{ type: string; path: string } | null>(null)
const awaitingApproval = ref(false)

// Brand selection
const brands = ref<string[]>([])
const activeBrand = ref('__inbox__')
const showBrandPicker = ref(false)

const WELCOME = `Hey! I'm your Reel Forge assistant. I can help you set up a brand identity or create a new video campaign — just tell me what you'd like to do.

- **"Create a new brand"** — I'll walk you through building your content creator persona
- **"New video campaign"** — I'll help you set up a campaign using an existing brand
- **"What brands do I have?"** — I'll check what's already set up`

onMounted(async () => {
  try {
    brands.value = await listBrands()
  } catch {
    brands.value = []
  }

  if (brands.value.length === 1) {
    await selectBrand(brands.value[0])
  } else if (brands.value.length > 1) {
    showBrandPicker.value = true
    messages.value = [{ role: 'assistant', content: WELCOME }]
  } else {
    messages.value = [{ role: 'assistant', content: WELCOME }]
  }
})

async function selectBrand(name: string) {
  showBrandPicker.value = false
  activeBrand.value = name
  try {
    const { messages: history } = await getChatHistory(name)
    if (history && history.length > 0) {
      messages.value = history
    } else {
      messages.value = [{ role: 'assistant', content: WELCOME }]
    }
  } catch {
    messages.value = [{ role: 'assistant', content: WELCOME }]
  }
  await scrollToBottom()
}

async function submit(text?: string) {
  const txt = (text ?? input.value).trim()
  if (!txt || loading.value) return

  messages.value.push({ role: 'user', content: txt })
  if (!text) input.value = ''
  loading.value = true
  awaitingApproval.value = false
  await scrollToBottom()

  try {
    // Send only user+assistant turns (no system or tool messages stored locally)
    const res = await sendMessage(messages.value, activeBrand.value)
    messages.value.push({ role: 'assistant', content: res.reply })
    awaitingApproval.value = res.awaiting_approval ?? false
    if (res.action) pendingAction.value = res.action

    // Always refresh brand list — cheap call, keeps picker in sync after create_brand
    try {
      const updated = await listBrands()
      const newBrand = updated.find(b => !brands.value.includes(b))
      brands.value = updated
      if (newBrand) {
        activeBrand.value = newBrand
      }
    } catch { /* ignore */ }
  } catch {
    messages.value.push({
      role: 'assistant',
      content: 'Something went wrong — please try again.',
    })
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

function approve() {
  submit('Yes, go ahead.')
}

function handleNavigate() {
  if (pendingAction.value) {
    router.push(pendingAction.value.path)
    pendingAction.value = null
  }
}

async function scrollToBottom() {
  await nextTick()
  bottomEl.value?.scrollIntoView({ behavior: 'smooth', block: 'end' })
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    submit()
  }
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}

function renderMarkdown(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>')
}

// Show approve button after the last assistant message when it needs approval
const lastIsAssistant = computed(
  () => messages.value.length > 0 && messages.value[messages.value.length - 1].role === 'assistant'
)
</script>

<template>
  <div class="min-h-screen flex flex-col text-white" @click="showBrandPicker = false">
    <!-- Header -->
    <header class="site-header px-6 py-4 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-4">
        <span class="mono text-xs" style="color: var(--cyan)">◈</span>
        <span class="font-bold text-lg tracking-tight" style="color: var(--text-primary)">Reel-Forge</span>
        <RouterLink to="/campaigns" class="label hover:text-gray-300 transition-colors ml-2">[ campaigns ]</RouterLink>
        <span class="label" style="color: var(--cyan)">[ chat ]</span>
      </div>
      <div class="flex items-center gap-5">
        <!-- Brand selector pill -->
        <div v-if="brands.length > 0" class="relative" @click.stop>
          <button
            class="mono text-xs px-2 py-1 rounded"
            style="border: 1px solid var(--border); color: var(--text-muted)"
            @click="showBrandPicker = !showBrandPicker"
          >
            {{ activeBrand === '__inbox__' ? '— no brand —' : activeBrand }} ▾
          </button>
          <div
            v-if="showBrandPicker"
            class="absolute right-0 mt-1 z-50 rounded-lg overflow-hidden"
            style="background: var(--bg-card); border: 1px solid var(--border); min-width: 140px"
          >
            <button
              v-for="b in brands"
              :key="b"
              class="block w-full text-left px-4 py-2 text-xs hover:bg-white/5 transition-colors"
              style="color: var(--text-primary)"
              @click="selectBrand(b)"
            >
              {{ b }}
            </button>
          </div>
        </div>
        <span class="mono text-xs" style="color: var(--text-muted)">{{ auth.email }}</span>
        <RouterLink to="/settings" class="label hover:text-gray-300 transition-colors">[ settings ]</RouterLink>
        <button class="label hover:text-gray-300 transition-colors" @click="handleLogout">[ logout ]</button>
      </div>
    </header>

    <!-- Chat body -->
    <main class="flex-1 max-w-3xl w-full mx-auto px-4 py-6 flex flex-col gap-4 overflow-hidden">

      <!-- Messages -->
      <div class="flex-1 overflow-y-auto flex flex-col pr-1" style="scrollbar-width: thin">
        <div class="flex-1" />
        <div class="flex flex-col gap-4 pb-2">

          <div
            v-for="(msg, i) in messages"
            :key="i"
            class="flex"
            :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
          >
            <!-- Assistant bubble -->
            <div
              v-if="msg.role === 'assistant'"
              class="max-w-[85%] rounded-xl px-4 py-3 text-sm leading-relaxed"
              style="background: var(--bg-card); border: 1px solid var(--border); color: var(--text-primary)"
              v-html="renderMarkdown(msg.content)"
            />

            <!-- User bubble -->
            <div
              v-else
              class="max-w-[75%] rounded-xl px-4 py-3 text-sm leading-relaxed"
              style="background: rgba(0,229,255,0.08); border: 1px solid rgba(0,229,255,0.25); color: var(--text-primary)"
            >
              {{ msg.content }}
            </div>
          </div>

          <!-- Typing indicator -->
          <div v-if="loading" class="flex justify-start">
            <div class="rounded-xl px-4 py-3" style="background: var(--bg-card); border: 1px solid var(--border)">
              <span class="typing-dots" style="color: var(--cyan)">
                <span>·</span><span>·</span><span>·</span>
              </span>
            </div>
          </div>

          <!-- Approve button (shown after last assistant message when awaiting approval) -->
          <div v-if="awaitingApproval && lastIsAssistant && !loading" class="flex justify-start pl-1">
            <button
              class="text-xs px-4 py-2 rounded-lg transition-colors"
              style="background: rgba(0,229,255,0.1); border: 1px solid rgba(0,229,255,0.35); color: var(--cyan)"
              @click="approve"
            >
              Approve →
            </button>
          </div>

          <!-- Scroll sentinel -->
          <div ref="bottomEl" />
        </div>
      </div>

      <!-- Action card -->
      <div
        v-if="pendingAction"
        class="card-cyber px-4 py-3 flex items-center justify-between shrink-0"
        style="border-color: rgba(0,229,255,0.3)"
      >
        <div class="text-sm" style="color: var(--text-muted)">
          <span style="color: var(--cyan)">◈</span>
          {{ pendingAction.path.startsWith('/campaigns') ? 'Campaign ready' : 'Ready' }}
          <span class="mono ml-1" style="color: var(--text-muted)">{{ pendingAction.path }}</span>
        </div>
        <button class="btn-cyber text-xs py-1 px-3" @click="handleNavigate">
          View →
        </button>
      </div>

      <!-- Input -->
      <div class="shrink-0 flex gap-3 items-end">
        <textarea
          v-model="input"
          @keydown="onKeydown"
          :disabled="loading"
          rows="2"
          placeholder="Ask me anything or say 'create a new brand'…"
          class="flex-1 resize-none rounded-xl px-4 py-3 text-sm outline-none"
          style="
            background: var(--bg-card);
            border: 1px solid var(--border);
            color: var(--text-primary);
            font-family: inherit;
            transition: border-color 0.2s;
          "
          @focus="(e: FocusEvent) => (e.target as HTMLElement).style.borderColor = 'rgba(0,229,255,0.4)'"
          @blur="(e: FocusEvent) => (e.target as HTMLElement).style.borderColor = 'var(--border)'"
        />
        <button
          class="btn-cyber px-4 py-3 shrink-0"
          :disabled="loading || !input.trim()"
          @click="submit()"
          style="align-self: stretch"
        >
          Send
        </button>
      </div>

      <p class="text-center text-xs" style="color: var(--text-muted)">Enter to send · Shift+Enter for new line</p>
    </main>
  </div>
</template>

<style scoped>
.typing-dots span {
  animation: blink 1.2s infinite;
  font-size: 1.4rem;
  line-height: 1;
}
.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes blink {
  0%, 80%, 100% { opacity: 0.2; }
  40% { opacity: 1; }
}

textarea::placeholder { color: var(--text-muted); }
textarea:disabled { opacity: 0.5; }
button:disabled { opacity: 0.4; cursor: not-allowed; }
</style>

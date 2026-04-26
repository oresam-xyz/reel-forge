<script setup lang="ts">
const apiBase = import.meta.env.VITE_API_URL || ''
</script>

<template>
  <div class="min-h-screen flex items-center justify-center px-4" style="background-color:#07070f; background-image: radial-gradient(rgba(0,229,255,0.04) 1px, transparent 1px); background-size: 24px 24px;">
    <div class="card-cyber w-full max-w-sm p-10 text-center" style="box-shadow: 0 0 40px rgba(0,229,255,0.08);">
      <!-- Wordmark -->
      <div class="mono text-xs tracking-widest text-gray-500 mb-1">◈ SYSTEM</div>
      <h1 class="text-3xl font-bold tracking-tight mb-1 glow-cyan">Reel-Forge</h1>
      <p class="text-gray-500 text-sm mb-8 tracking-wide">Ad pipeline · oresam.xyz</p>

      <!-- Divider -->
      <div class="flex items-center gap-3 mb-6">
        <div class="flex-1 h-px" style="background: var(--border)"></div>
        <span class="label">auth</span>
        <div class="flex-1 h-px" style="background: var(--border)"></div>
      </div>

      <a
        :href="`${apiBase}/auth/google`"
        class="flex items-center justify-center gap-3 w-full px-6 py-3 rounded-lg font-semibold text-sm transition-all"
        style="background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); color: #e2e8f0;"
        onmouseover="this.style.background='rgba(255,255,255,0.09)'; this.style.borderColor='rgba(255,255,255,0.2)'"
        onmouseout="this.style.background='rgba(255,255,255,0.05)'; this.style.borderColor='rgba(255,255,255,0.1)'"
      >
        <svg class="w-5 h-5 flex-shrink-0" viewBox="0 0 24 24">
          <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
          <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
          <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"/>
          <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
        </svg>
        Continue with Google
      </a>
    </div>
  </div>
</template>

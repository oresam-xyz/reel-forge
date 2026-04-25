<script setup lang="ts">
defineProps<{
  phases: Array<{ name: string; state: 'pending' | 'running' | 'review' | 'complete' | 'failed' }>
  selected?: string
}>()
defineEmits<{ select: [name: string] }>()
</script>

<template>
  <ol class="space-y-0.5">
    <li
      v-for="phase in phases"
      :key="phase.name"
      class="flex items-center gap-3 rounded-lg px-2 py-2 transition-colors"
      :class="{
        'cursor-pointer': phase.state === 'complete' || phase.state === 'failed',
        'cursor-default': phase.state === 'pending' || phase.state === 'running' || phase.state === 'review',
      }"
      :style="selected === phase.name ? 'background: rgba(0,229,255,0.07); border-left: 2px solid var(--cyan); padding-left: 10px;' : 'border-left: 2px solid transparent'"
      @click="(phase.state === 'complete' || phase.state === 'failed') && $emit('select', phase.name)"
    >
      <!-- Icon -->
      <span class="phase-icon"
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
      <span class="text-sm capitalize font-semibold tracking-wide"
        :style="{
          color: phase.state === 'complete' ? 'var(--neon-green)'
               : phase.state === 'running'  ? 'var(--cyan)'
               : phase.state === 'review'   ? 'var(--amber)'
               : phase.state === 'failed'   ? 'var(--red)'
               : 'rgba(100,116,139,0.5)',
        }"
      >{{ phase.name }}</span>
      <!-- chevron for clickable -->
      <span v-if="phase.state === 'complete' || phase.state === 'failed'"
        class="ml-auto text-xs" style="color: var(--text-muted)">›</span>
    </li>
  </ol>
</template>

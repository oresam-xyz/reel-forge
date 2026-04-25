<script setup lang="ts">
defineProps<{
  phases: Array<{ name: string; state: 'pending' | 'running' | 'review' | 'complete' | 'failed' }>
  selected?: string
}>()
defineEmits<{ select: [name: string] }>()
</script>

<template>
  <ol class="space-y-1">
    <li
      v-for="phase in phases"
      :key="phase.name"
      class="flex items-center gap-3 rounded-lg px-2 py-1.5 transition-colors"
      :class="{
        'cursor-pointer hover:bg-gray-800': phase.state === 'complete' || phase.state === 'failed',
        'bg-gray-800': selected === phase.name,
        'cursor-default': phase.state === 'pending' || phase.state === 'running' || phase.state === 'review',
      }"
      @click="(phase.state === 'complete' || phase.state === 'failed') && $emit('select', phase.name)"
    >
      <!-- Icon -->
      <span class="w-6 h-6 flex-shrink-0 flex items-center justify-center rounded-full text-xs font-bold"
        :class="{
          'bg-green-900 text-green-300': phase.state === 'complete',
          'bg-blue-900 text-blue-300 animate-pulse': phase.state === 'running',
          'bg-amber-900 text-amber-300': phase.state === 'review',
          'bg-red-900 text-red-400': phase.state === 'failed',
          'bg-gray-800 text-gray-600': phase.state === 'pending',
        }"
      >
        <span v-if="phase.state === 'complete'">✓</span>
        <span v-else-if="phase.state === 'running'">⟳</span>
        <span v-else-if="phase.state === 'review'">!</span>
        <span v-else-if="phase.state === 'failed'">✗</span>
        <span v-else>○</span>
      </span>
      <!-- Label -->
      <span class="text-sm capitalize"
        :class="{
          'text-green-300': phase.state === 'complete' && selected !== phase.name,
          'text-white font-medium': phase.state === 'complete' && selected === phase.name,
          'text-blue-300 font-medium': phase.state === 'running',
          'text-amber-300 font-medium': phase.state === 'review',
          'text-red-400': phase.state === 'failed',
          'text-gray-600': phase.state === 'pending',
        }"
      >{{ phase.name }}</span>
      <!-- chevron hint for clickable phases -->
      <span v-if="phase.state === 'complete' || phase.state === 'failed'" class="ml-auto text-gray-600 text-xs">›</span>
    </li>
  </ol>
</template>

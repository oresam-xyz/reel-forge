<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

onMounted(() => {
  const params = new URLSearchParams(window.location.search)
  const token = params.get('token')
  if (token) {
    auth.setToken(token)
    router.replace('/')
  } else {
    router.replace('/login')
  }
})
</script>

<template>
  <div class="flex h-screen items-center justify-center text-gray-400">Signing in…</div>
</template>

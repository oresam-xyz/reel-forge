import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAuthStore = defineStore(
  'auth',
  () => {
    const token = ref<string | null>(localStorage.getItem('rf_token'))
    const email = ref<string | null>(null)

    function setToken(t: string) {
      token.value = t
      localStorage.setItem('rf_token', t)
      // Decode email from JWT payload (no verification needed — API does that)
      try {
        const payload = JSON.parse(atob(t.split('.')[1]))
        email.value = payload.email ?? null
      } catch {}
    }

    function logout() {
      token.value = null
      email.value = null
      localStorage.removeItem('rf_token')
    }

    return { token, email, setToken, logout }
  },
)

import { ref } from 'vue'
import { defineStore } from 'pinia'
import { getMe, patchMe, type Me, type UserSettings } from '../api/user'

export const useUserStore = defineStore('user', () => {
  const me = ref<Me | null>(null)

  async function fetch() {
    me.value = await getMe()
  }

  async function saveSettings(settings: UserSettings) {
    me.value = await patchMe({ settings })
  }

  async function saveName(name: string) {
    me.value = await patchMe({ name })
  }

  return { me, fetch, saveSettings, saveName }
})

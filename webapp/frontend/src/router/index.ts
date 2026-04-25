import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import CampaignsView from '../views/CampaignsView.vue'
import CampaignView from '../views/CampaignView.vue'
import JobView from '../views/JobView.vue'
import AuthCallback from '../views/AuthCallback.vue'
import SettingsView from '../views/SettingsView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginView },
    { path: '/auth/callback', component: AuthCallback },
    { path: '/', component: CampaignsView, meta: { requiresAuth: true } },
    { path: '/campaigns/:id', component: CampaignView, meta: { requiresAuth: true } },
    { path: '/jobs/:id', component: JobView, meta: { requiresAuth: true } },
    { path: '/settings', component: SettingsView, meta: { requiresAuth: true } },
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem('rf_token')
  if (to.meta.requiresAuth && !token) return '/login'
})

export default router

import { createRouter, createWebHistory } from 'vue-router'

import ChildrenView from '@/views/ChildrenView.vue'
import DashboardView from '@/views/DashboardView.vue'
import LoginView from '@/views/LoginView.vue'
import RegisterView from '@/views/RegisterView.vue'
import { useAuthStore } from '@/stores/auth'
import { pinia } from '@/stores/pinia'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'root',
      redirect: (to) => {
        const authStore = useAuthStore(pinia)
        return authStore.isAuthenticated ? { name: 'dashboard' } : { name: 'login' }
      },
    },
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: {
        guestOnly: true,
      },
    },
    {
      path: '/register',
      name: 'register',
      component: RegisterView,
      meta: {
        guestOnly: true,
      },
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: DashboardView,
      meta: {
        requiresAuth: true,
      },
    },
    {
      path: '/children',
      name: 'children',
      component: ChildrenView,
      meta: {
        requiresAuth: true,
      },
    },
  ],
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore(pinia)

  if (!authStore.isInitialized) {
    try {
      await authStore.fetchUser()
    } catch {
      authStore.clearUser()
    }
  }

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return { name: 'login' }
  }

  if (to.meta.guestOnly && authStore.isAuthenticated) {
    return { name: 'dashboard' }
  }
})

export default router

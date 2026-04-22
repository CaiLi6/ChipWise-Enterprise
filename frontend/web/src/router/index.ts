import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'Login', component: () => import('@/views/LoginView.vue') },
    { path: '/register', name: 'Register', component: () => import('@/views/RegisterView.vue') },
    {
      path: '/',
      component: () => import('@/components/AppLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        { path: '', redirect: '/query' },
        { path: 'query', name: 'Query', component: () => import('@/views/QueryView.vue') },
        { path: 'compare', name: 'Compare', component: () => import('@/views/CompareView.vue') },
        { path: 'documents', name: 'Documents', component: () => import('@/views/DocumentsView.vue') },
        { path: 'traces', name: 'Traces', component: () => import('@/views/TracesView.vue') },
        { path: 'evaluations', name: 'Evaluations', component: () => import('@/views/EvaluationsView.vue') },
      ],
    },
  ],
})

router.beforeEach((to, _from, next) => {
  const auth = useAuthStore()
  if (to.matched.some((r) => r.meta.requiresAuth) && !auth.isLoggedIn) {
    next({ path: '/login', query: { redirect: to.fullPath } })
  } else if (to.path === '/login' && auth.isLoggedIn) {
    next('/')
  } else {
    next()
  }
})

export default router

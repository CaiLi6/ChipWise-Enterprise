import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'Login', component: () => import('@/views/LoginView.vue') },
    { path: '/query', name: 'Query', component: () => import('@/views/QueryView.vue') },
    { path: '/compare', name: 'Compare', component: () => import('@/views/CompareView.vue') },
    { path: '/documents', name: 'Documents', component: () => import('@/views/DocumentsView.vue') },
    { path: '/', redirect: '/query' },
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem('chipwise_token')
  if (!token && to.name !== 'Login' && import.meta.env.PROD) {
    return { name: 'Login' }
  }
})

export default router

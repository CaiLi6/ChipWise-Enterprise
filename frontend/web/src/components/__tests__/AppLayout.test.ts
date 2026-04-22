import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import AppLayout from '../AppLayout.vue'
import ElementPlus from 'element-plus'
import { createRouter, createMemoryHistory } from 'vue-router'

function createMockRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/query', component: { template: '<div>Query</div>' } },
      { path: '/compare', component: { template: '<div>Compare</div>' } },
      { path: '/documents', component: { template: '<div>Documents</div>' } },
      { path: '/login', component: { template: '<div>Login</div>' } },
    ],
  })
}

describe('AppLayout', () => {
  it('renders sidebar menu items', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createMockRouter()
    await router.push('/query')
    await router.isReady()

    const wrapper = mount(AppLayout, {
      global: {
        plugins: [pinia, router, ElementPlus],
      },
    })

    const menuItems = wrapper.findAll('.el-menu-item')
    // 5 sections: Query, Compare, Documents, Traces, Evaluations
    expect(menuItems.length).toBe(5)
  })

  it('shows ChipWise brand text', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createMockRouter()
    await router.push('/query')
    await router.isReady()

    const wrapper = mount(AppLayout, {
      global: {
        plugins: [pinia, router, ElementPlus],
      },
    })

    expect(wrapper.text()).toContain('ChipWise')
  })
})

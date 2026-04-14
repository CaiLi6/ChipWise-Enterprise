import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MessageBubble from '../MessageBubble.vue'

describe('MessageBubble', () => {
  it('renders user role with correct class', () => {
    const wrapper = mount(MessageBubble, {
      props: { role: 'user', content: 'Hello' },
      global: { stubs: { CitationCard: true, ElTag: true } },
    })
    expect(wrapper.find('.bubble-row.user').exists()).toBe(true)
    expect(wrapper.text()).toContain('Hello')
  })

  it('renders assistant role with correct class', () => {
    const wrapper = mount(MessageBubble, {
      props: { role: 'assistant', content: 'Response' },
      global: { stubs: { CitationCard: true, ElTag: true } },
    })
    expect(wrapper.find('.bubble-row.assistant').exists()).toBe(true)
    expect(wrapper.text()).toContain('Response')
  })

  it('renders system role with danger styling', () => {
    const wrapper = mount(MessageBubble, {
      props: { role: 'system', content: 'Error message' },
      global: { stubs: { CitationCard: true, ElTag: true } },
    })
    expect(wrapper.find('.bubble-row.system').exists()).toBe(true)
  })

  it('shows blinking cursor when loading', () => {
    const wrapper = mount(MessageBubble, {
      props: { role: 'assistant', content: 'Loading...', loading: true },
      global: { stubs: { CitationCard: true, ElTag: true } },
    })
    expect(wrapper.find('.cursor').exists()).toBe(true)
  })

  it('hides cursor when not loading', () => {
    const wrapper = mount(MessageBubble, {
      props: { role: 'assistant', content: 'Done' },
      global: { stubs: { CitationCard: true, ElTag: true } },
    })
    expect(wrapper.find('.cursor').exists()).toBe(false)
  })
})

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import CitationCard from '../CitationCard.vue'
import ElementPlus from 'element-plus'

const mockCitation = {
  chunk_id: 'c1',
  doc_id: 'doc-123',
  content: 'STM32F407 has a maximum clock frequency of 168 MHz with Cortex-M4 core.',
  score: 0.92,
}

describe('CitationCard', () => {
  const globalConfig = { plugins: [ElementPlus] }

  it('renders doc_id', () => {
    const wrapper = mount(CitationCard, {
      props: { citation: mockCitation },
      global: globalConfig,
    })
    expect(wrapper.text()).toContain('doc-123')
  })

  it('renders score formatted to 2 decimal places', () => {
    const wrapper = mount(CitationCard, {
      props: { citation: mockCitation },
      global: globalConfig,
    })
    expect(wrapper.text()).toContain('0.92')
  })

  it('truncates long content to 150 chars', () => {
    const longContent = 'A'.repeat(200)
    const wrapper = mount(CitationCard, {
      props: { citation: { ...mockCitation, content: longContent } },
      global: globalConfig,
    })
    expect(wrapper.text()).toContain('…')
  })
})

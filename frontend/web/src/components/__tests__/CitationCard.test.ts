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

  it('renders doc_id as the chip label', () => {
    const wrapper = mount(CitationCard, {
      props: { citation: mockCitation },
      global: globalConfig,
    })
    expect(wrapper.text()).toContain('doc-123')
  })

  it('renders the chip element with score-tier class', () => {
    const wrapper = mount(CitationCard, {
      props: { citation: mockCitation },
      global: globalConfig,
    })
    const chip = wrapper.find('.chip')
    expect(chip.exists()).toBe(true)
    // 0.92 falls in the "high" tier (>= 0.7)
    expect(chip.classes()).toContain('high')
  })

  it('shows the page number when provided', () => {
    const wrapper = mount(CitationCard, {
      props: { citation: { ...mockCitation, page_number: 42 } },
      global: globalConfig,
    })
    expect(wrapper.text()).toContain('p.42')
  })
})

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import LoadingError from '../LoadingError.vue'

describe('LoadingError', () => {
  it('shows loading skeleton when loading=true', () => {
    const wrapper = mount(LoadingError, {
      props: { loading: true },
      global: { stubs: { ElSkeleton: true, ElResult: true, ElEmpty: true, ElButton: true } },
    })
    expect(wrapper.findComponent({ name: 'ElSkeleton' }).exists()).toBe(true)
  })

  it('shows error result when error is set', () => {
    const wrapper = mount(LoadingError, {
      props: { error: 'Something went wrong' },
      global: { stubs: { ElSkeleton: true, ElResult: true, ElEmpty: true, ElButton: true } },
    })
    expect(wrapper.findComponent({ name: 'ElResult' }).exists()).toBe(true)
  })

  it('shows empty state when empty=true', () => {
    const wrapper = mount(LoadingError, {
      props: { empty: true, emptyText: '暂无数据' },
      global: { stubs: { ElSkeleton: true, ElResult: true, ElEmpty: true, ElButton: true } },
    })
    expect(wrapper.findComponent({ name: 'ElEmpty' }).exists()).toBe(true)
  })

  it('renders default slot when no special state', () => {
    const wrapper = mount(LoadingError, {
      slots: { default: '<div class="content">Data here</div>' },
      global: { stubs: { ElSkeleton: true, ElResult: true, ElEmpty: true, ElButton: true } },
    })
    expect(wrapper.find('.content').exists()).toBe(true)
    expect(wrapper.text()).toContain('Data here')
  })
})

import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import AvailabilityTimeline from '@/components/AvailabilityTimeline.vue'

const ranges = [
  { start: '08:00', end: '10:00' },
  { start: '11:00', end: '18:00' }
]

describe('AvailabilityTimeline', () => {
  it('只渲染绿色可用区间，并标记当前时间', () => {
    const wrapper = mount(AvailabilityTimeline, {
      props: {
        ranges,
        openTime: '08:00',
        closeTime: '18:00',
        currentTime: '16:10',
        selectedStart: '11:00',
        selectedEnd: '12:00'
      }
    })

    expect(wrapper.findAll('.timeline-range')).toHaveLength(2)
    expect(wrapper.find('.timeline-now').exists()).toBe(true)
    expect(wrapper.find('.timeline-selected').exists()).toBe(true)
    expect(wrapper.text()).toContain('16:10')
    expect(wrapper.text()).toContain('08')
    expect(wrapper.text()).toContain('18')
  })

  it('全部不可用时没有绿色区间', () => {
    const wrapper = mount(AvailabilityTimeline, {
      props: {
        ranges: [],
        openTime: '08:00',
        closeTime: '18:00'
      }
    })

    expect(wrapper.findAll('.timeline-range')).toHaveLength(0)
    expect(wrapper.find('.timeline-now').exists()).toBe(false)
  })
})
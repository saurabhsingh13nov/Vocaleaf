import { ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { Child } from '@/services/children'
import ChildrenView from '@/views/ChildrenView.vue'
import { useChildrenStore } from '@/stores/children'

vi.mock('vue-router', async () => {
  const actual = await vi.importActual<typeof import('vue-router')>('vue-router')
  return {
    ...actual,
    useRouter: () => ({ push: vi.fn() }),
    RouterLink: {
      template: '<a><slot /></a>',
      props: ['to'],
    },
  }
})

vi.mock('@/services/children', () => ({
  getChildren: vi.fn().mockResolvedValue([]),
  createChild: vi.fn(),
  updateChild: vi.fn(),
  deleteChild: vi.fn(),
}))

const sampleChild: Child = {
  id: 'aaa-bbb-ccc',
  user_id: 'user-123',
  name: 'Luna',
  age: 5,
  favorite_themes: null,
  favorite_characters: null,
  bedtime_preferences: null,
  created_at: '2026-03-12T10:00:00Z',
  updated_at: '2026-03-12T10:00:00Z',
}

describe('ChildrenView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  it('renders empty state when no children exist', async () => {
    const wrapper = mount(ChildrenView)
    await flushPromises()

    expect(wrapper.text()).toContain('No child profiles yet')
    expect(wrapper.text()).toContain('Add your first child')
  })

  it('renders child cards when children exist', async () => {
    const { getChildren } = await import('@/services/children')
    vi.mocked(getChildren).mockResolvedValue([sampleChild])

    const wrapper = mount(ChildrenView)
    await flushPromises()

    expect(wrapper.text()).toContain('Luna')
    expect(wrapper.text()).toContain('Age 5')
  })

  it('opens create form and submits', async () => {
    const { getChildren, createChild } = await import('@/services/children')
    vi.mocked(getChildren).mockResolvedValue([])
    vi.mocked(createChild).mockResolvedValue({
      ...sampleChild,
      name: 'Max',
      age: 3,
    })

    const wrapper = mount(ChildrenView)
    await flushPromises()

    // Click "Add your first child"
    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Add Child')

    // Fill and submit
    await wrapper.find('input[name="name"]').setValue('Max')
    await wrapper.find('input[name="age"]').setValue('3')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(createChild).toHaveBeenCalledWith({ name: 'Max', age: 3 })
  })

  it('deletes a child when delete is clicked', async () => {
    const { getChildren, deleteChild } = await import('@/services/children')
    vi.mocked(getChildren).mockResolvedValue([sampleChild])
    vi.mocked(deleteChild).mockResolvedValue(undefined)

    const wrapper = mount(ChildrenView)
    await flushPromises()

    // Find and click delete button
    const deleteBtn = wrapper.findAll('button').find((b) => b.text() === 'Delete')
    expect(deleteBtn).toBeTruthy()

    await deleteBtn!.trigger('click')
    await flushPromises()

    expect(deleteChild).toHaveBeenCalledWith('aaa-bbb-ccc')
  })
})

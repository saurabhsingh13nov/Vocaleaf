import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ConfirmModal from '@/components/ConfirmModal.vue'

describe('ConfirmModal', () => {
  function mountModal(isPending = false) {
    return mount(ConfirmModal, {
      props: {
        title: 'Delete story',
        message: 'This action removes the story permanently.',
        confirmLabel: 'Delete story',
        pendingConfirmLabel: 'Deleting...',
        warningText: 'Generation is still in progress.',
        isPending,
      },
      global: {
        stubs: {
          Teleport: true,
        },
      },
    })
  }

  it('renders its copy and warning text', () => {
    const wrapper = mountModal()

    expect(wrapper.text()).toContain('Delete story')
    expect(wrapper.text()).toContain('This action removes the story permanently.')
    expect(wrapper.text()).toContain('Generation is still in progress.')
  })

  it('emits cancel and confirm actions', async () => {
    const wrapper = mountModal()

    await wrapper.get('[data-testid="confirm-modal-cancel"]').trigger('click')
    await wrapper.get('[data-testid="confirm-modal-confirm"]').trigger('click')

    expect(wrapper.emitted('cancel')).toHaveLength(1)
    expect(wrapper.emitted('confirm')).toHaveLength(1)
  })

  it('disables actions and ignores escape while pending', async () => {
    const wrapper = mountModal(true)

    expect(wrapper.get('[data-testid="confirm-modal-cancel"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="confirm-modal-confirm"]').attributes('disabled')).toBeDefined()

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))

    expect(wrapper.emitted('cancel')).toBeUndefined()
    expect(wrapper.text()).toContain('Deleting...')
  })
})

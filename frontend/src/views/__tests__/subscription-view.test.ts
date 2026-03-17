import { computed, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { User } from '@/services/auth'
import { getSubscriptionSummary } from '@/services/subscription'
import SubscriptionView from '@/views/SubscriptionView.vue'
import { useAuth } from '@/composables/useAuth'

const useAuthMock = vi.mocked(useAuth)

vi.mock('@/composables/useAuth', () => ({
  useAuth: vi.fn(),
}))

vi.mock('vue-router', async () => {
  const actual = await vi.importActual<typeof import('vue-router')>('vue-router')
  return {
    ...actual,
    RouterLink: {
      template: '<a><slot /></a>',
      props: ['to'],
    },
  }
})

vi.mock('@/services/subscription', () => ({
  getSubscriptionSummary: vi.fn(),
}))

const mockedGetSubscriptionSummary = vi.mocked(getSubscriptionSummary)

const sampleUser: User = {
  id: 'user-1',
  primary_email: 'parent@example.com',
  full_name: 'Parent Reader',
  avatar_url: null,
  status: 'active',
  role: 'admin',
  email_verified_at: null,
  created_at: '2026-03-11T20:00:00Z',
}

function makeAuthState(userOverride: Partial<User> = {}) {
  const user = ref<User | null>({ ...sampleUser, ...userOverride })

  return {
    clearUser: vi.fn(),
    fetchUser: vi.fn(),
    getErrorMessage: vi.fn(() => 'Friendly error message'),
    isAuthenticated: computed(() => user.value !== null),
    isInitialized: ref(true),
    isLoading: ref(false),
    link: vi.fn(),
    linkWithGoogle: vi.fn(),
    login: vi.fn(),
    loginWithGoogle: vi.fn(),
    logout: vi.fn(),
    register: vi.fn(),
    user,
  } as unknown as ReturnType<typeof useAuth>
}

describe('SubscriptionView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    useAuthMock.mockReturnValue(makeAuthState())
    mockedGetSubscriptionSummary.mockResolvedValue({
      id: 'subscription-1',
      status: 'active',
      current_period_start: '2026-03-01T00:00:00Z',
      current_period_end: '2026-03-31T00:00:00Z',
      plan: {
        id: 'plan-1',
        code: 'free',
        name: 'free',
        monthly_story_limit: null,
        max_pages_per_story: null,
        image_quality_mode: 'standard',
        voice_clone_limit: null,
        monthly_audio_chars_limit: null,
        price_cents: 0,
      },
      usage: {
        stories_created: { used: 5, limit: null, remaining: null, unit: 'story' },
        voice_clones_created: { used: 2, limit: null, remaining: null, unit: 'voice_clone' },
        audio_chars_synthesized: { used: 42000, limit: null, remaining: null, unit: 'character' },
        images_generated: { used: 14, limit: null, remaining: null, unit: 'page_image' },
      },
    })
  })

  it('shows the current role and unrestricted messaging for elevated accounts', async () => {
    const wrapper = mount(SubscriptionView, {
      global: {
        stubs: {
          RouterLink: true,
        },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Role: admin')
    expect(wrapper.text()).toContain('This account is unrestricted for story and usage limits because it uses an elevated internal role.')
    expect(wrapper.text()).toContain('No limit applies for the admin role.')
    expect(wrapper.text()).not.toContain('remaining this period')
  })
})

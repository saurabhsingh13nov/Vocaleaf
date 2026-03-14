import { computed, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { User } from '@/services/auth'
import DashboardView from '@/views/DashboardView.vue'
import LoginView from '@/views/LoginView.vue'
import RegisterView from '@/views/RegisterView.vue'
import { useAuth } from '@/composables/useAuth'

const pushMock = vi.fn()
const useAuthMock = vi.mocked(useAuth)

vi.mock('@/composables/useAuth', () => ({
  useAuth: vi.fn(),
}))

vi.mock('@/services/stories', () => ({
  createStory: vi.fn(),
  getStory: vi.fn(),
  getStories: vi.fn().mockResolvedValue([]),
}))

vi.mock('vue-router', async () => {
  const actual = await vi.importActual<typeof import('vue-router')>('vue-router')

  return {
    ...actual,
    useRouter: () => ({
      push: pushMock,
    }),
  }
})

const sampleUser: User = {
  id: 'cc4e3be9-0e56-4d1b-9128-655ddcf06092',
  primary_email: 'parent@example.com',
  full_name: 'Parent Reader',
  avatar_url: null,
  status: 'active',
  email_verified_at: null,
  created_at: '2026-03-11T20:00:00Z',
}

function makeAuthState(overrides?: Partial<ReturnType<typeof useAuth>>): ReturnType<typeof useAuth> {
  const user = overrides?.user ?? ref<User | null>(null)

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
    ...overrides,
  } as unknown as ReturnType<typeof useAuth>
}

describe('auth views', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  it('submits login credentials and navigates to dashboard', async () => {
    const authState = makeAuthState({
      login: vi.fn().mockResolvedValue(sampleUser),
    })
    useAuthMock.mockReturnValue(authState)

    const wrapper = mount(LoginView, {
      global: {
        stubs: {
          RouterLink: true,
        },
      },
    })

    await wrapper.get('input[name="email"]').setValue(sampleUser.primary_email ?? '')
    await wrapper.get('input[name="password"]').setValue('securepass123')
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(authState.login).toHaveBeenCalledWith({
      email: sampleUser.primary_email,
      password: 'securepass123',
    })
    expect(pushMock).toHaveBeenCalledWith({ name: 'dashboard' })
  })

  it('shows a login error when submission fails', async () => {
    const error = new Error('bad login')
    const authState = makeAuthState({
      getErrorMessage: vi.fn(() => 'Invalid email or password'),
      login: vi.fn().mockRejectedValue(error),
    })
    useAuthMock.mockReturnValue(authState)

    const wrapper = mount(LoginView, {
      global: {
        stubs: {
          RouterLink: true,
        },
      },
    })

    await wrapper.get('input[name="email"]').setValue('wrong@example.com')
    await wrapper.get('input[name="password"]').setValue('wrongpassword')
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(authState.getErrorMessage).toHaveBeenCalledWith(error)
    expect(wrapper.text()).toContain('Invalid email or password')
    expect(pushMock).not.toHaveBeenCalled()
  })

  it('submits registration details and navigates to dashboard', async () => {
    const authState = makeAuthState({
      register: vi.fn().mockResolvedValue(sampleUser),
    })
    useAuthMock.mockReturnValue(authState)

    const wrapper = mount(RegisterView, {
      global: {
        stubs: {
          RouterLink: true,
        },
      },
    })

    await wrapper.get('input[name="full_name"]').setValue(sampleUser.full_name ?? '')
    await wrapper.get('input[name="email"]').setValue(sampleUser.primary_email ?? '')
    await wrapper.get('input[name="password"]').setValue('securepass123')
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(authState.register).toHaveBeenCalledWith({
      email: sampleUser.primary_email,
      full_name: sampleUser.full_name,
      password: 'securepass123',
    })
    expect(pushMock).toHaveBeenCalledWith({ name: 'dashboard' })
  })

  it('shows a register error when submission fails', async () => {
    const error = new Error('duplicate email')
    const authState = makeAuthState({
      getErrorMessage: vi.fn(() => 'Email already registered'),
      register: vi.fn().mockRejectedValue(error),
    })
    useAuthMock.mockReturnValue(authState)

    const wrapper = mount(RegisterView, {
      global: {
        stubs: {
          RouterLink: true,
        },
      },
    })

    await wrapper.get('input[name="full_name"]').setValue('Another Parent')
    await wrapper.get('input[name="email"]').setValue('parent@example.com')
    await wrapper.get('input[name="password"]').setValue('securepass123')
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(authState.getErrorMessage).toHaveBeenCalledWith(error)
    expect(wrapper.text()).toContain('Email already registered')
    expect(pushMock).not.toHaveBeenCalled()
  })

  describe('Google account linking (409 flow)', () => {
    let googleCallback: ((r: { credential: string }) => void) | undefined
    let appendSpy: ReturnType<typeof vi.spyOn>

    function setupGoogleMock() {
      googleCallback = undefined
      ;(window as any).google = {
        accounts: {
          id: {
            initialize: vi.fn(({ callback }: { callback: typeof googleCallback }) => {
              googleCallback = callback
            }),
            renderButton: vi.fn(),
          },
        },
      }
      appendSpy = vi.spyOn(document.head, 'appendChild').mockImplementation((el: Node) => {
        if (el instanceof HTMLScriptElement) el.onload?.(new Event('load'))
        return el
      })
      vi.stubEnv('VITE_GOOGLE_CLIENT_ID', 'fake-client-id')
    }

    afterEach(() => {
      appendSpy?.mockRestore()
      vi.unstubAllEnvs()
      delete (window as any).google
    })

    function make409Error() {
      return Object.assign(new Error('Conflict'), { isAxiosError: true, response: { status: 409 } })
    }

    function make401Error() {
      return Object.assign(new Error('Unauthorized'), { isAxiosError: true, response: { status: 401 } })
    }

    // ── LoginView ──────────────────────────────────────────────────────────

    it('LoginView: shows link-mode form when Google returns 409', async () => {
      setupGoogleMock()
      const authState = makeAuthState({ loginWithGoogle: vi.fn().mockRejectedValue(make409Error()) })
      useAuthMock.mockReturnValue(authState)

      const wrapper = mount(LoginView, { global: { stubs: { RouterLink: true } } })
      await flushPromises()
      await googleCallback!({ credential: 'fake-token' })
      await flushPromises()

      expect(wrapper.text()).toContain('Link your accounts')
      expect(wrapper.text()).not.toContain('Welcome back')
    })

    it('LoginView: correct password links accounts and navigates to dashboard', async () => {
      setupGoogleMock()
      const authState = makeAuthState({
        loginWithGoogle: vi.fn().mockRejectedValue(make409Error()),
        linkWithGoogle: vi.fn().mockResolvedValue(sampleUser),
      })
      useAuthMock.mockReturnValue(authState)

      const wrapper = mount(LoginView, { global: { stubs: { RouterLink: true } } })
      await flushPromises()
      await googleCallback!({ credential: 'fake-token' })
      await flushPromises()

      await wrapper.get('input[type="password"]').setValue('correctpassword')
      await wrapper.get('form').trigger('submit.prevent')
      await flushPromises()

      expect(authState.linkWithGoogle).toHaveBeenCalledWith('fake-token', 'correctpassword')
      expect(pushMock).toHaveBeenCalledWith({ name: 'dashboard' })
    })

    it('LoginView: wrong password shows inline error', async () => {
      setupGoogleMock()
      const authState = makeAuthState({
        loginWithGoogle: vi.fn().mockRejectedValue(make409Error()),
        linkWithGoogle: vi.fn().mockRejectedValue(make401Error()),
      })
      useAuthMock.mockReturnValue(authState)

      const wrapper = mount(LoginView, { global: { stubs: { RouterLink: true } } })
      await flushPromises()
      await googleCallback!({ credential: 'fake-token' })
      await flushPromises()

      await wrapper.get('input[type="password"]').setValue('wrongpassword')
      await wrapper.get('form').trigger('submit.prevent')
      await flushPromises()

      expect(wrapper.text()).toContain('Incorrect password')
      expect(pushMock).not.toHaveBeenCalled()
    })

    it('LoginView: cancel returns to normal login form', async () => {
      setupGoogleMock()
      const authState = makeAuthState({ loginWithGoogle: vi.fn().mockRejectedValue(make409Error()) })
      useAuthMock.mockReturnValue(authState)

      const wrapper = mount(LoginView, { global: { stubs: { RouterLink: true } } })
      await flushPromises()
      await googleCallback!({ credential: 'fake-token' })
      await flushPromises()

      expect(wrapper.text()).toContain('Link your accounts')
      await wrapper.get('button[type="button"]').trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('Welcome back')
      expect(wrapper.text()).not.toContain('Link your accounts')
    })

    // ── RegisterView ───────────────────────────────────────────────────────

    it('RegisterView: shows link-mode form when Google returns 409', async () => {
      setupGoogleMock()
      const authState = makeAuthState({ loginWithGoogle: vi.fn().mockRejectedValue(make409Error()) })
      useAuthMock.mockReturnValue(authState)

      const wrapper = mount(RegisterView, { global: { stubs: { RouterLink: true } } })
      await flushPromises()
      await googleCallback!({ credential: 'fake-token' })
      await flushPromises()

      expect(wrapper.text()).toContain('Link your accounts')
      expect(wrapper.text()).not.toContain('Create your account')
    })

    it('RegisterView: correct password links accounts and navigates to dashboard', async () => {
      setupGoogleMock()
      const authState = makeAuthState({
        loginWithGoogle: vi.fn().mockRejectedValue(make409Error()),
        linkWithGoogle: vi.fn().mockResolvedValue(sampleUser),
      })
      useAuthMock.mockReturnValue(authState)

      const wrapper = mount(RegisterView, { global: { stubs: { RouterLink: true } } })
      await flushPromises()
      await googleCallback!({ credential: 'fake-token' })
      await flushPromises()

      await wrapper.get('input[type="password"]').setValue('correctpassword')
      await wrapper.get('form').trigger('submit.prevent')
      await flushPromises()

      expect(authState.linkWithGoogle).toHaveBeenCalledWith('fake-token', 'correctpassword')
      expect(pushMock).toHaveBeenCalledWith({ name: 'dashboard' })
    })

    it('RegisterView: wrong password shows inline error', async () => {
      setupGoogleMock()
      const authState = makeAuthState({
        loginWithGoogle: vi.fn().mockRejectedValue(make409Error()),
        linkWithGoogle: vi.fn().mockRejectedValue(make401Error()),
      })
      useAuthMock.mockReturnValue(authState)

      const wrapper = mount(RegisterView, { global: { stubs: { RouterLink: true } } })
      await flushPromises()
      await googleCallback!({ credential: 'fake-token' })
      await flushPromises()

      await wrapper.get('input[type="password"]').setValue('wrongpassword')
      await wrapper.get('form').trigger('submit.prevent')
      await flushPromises()

      expect(wrapper.text()).toContain('Incorrect password')
      expect(pushMock).not.toHaveBeenCalled()
    })

    it('RegisterView: cancel returns to normal registration form', async () => {
      setupGoogleMock()
      const authState = makeAuthState({ loginWithGoogle: vi.fn().mockRejectedValue(make409Error()) })
      useAuthMock.mockReturnValue(authState)

      const wrapper = mount(RegisterView, { global: { stubs: { RouterLink: true } } })
      await flushPromises()
      await googleCallback!({ credential: 'fake-token' })
      await flushPromises()

      expect(wrapper.text()).toContain('Link your accounts')
      await wrapper.get('button[type="button"]').trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('Create your account')
      expect(wrapper.text()).not.toContain('Link your accounts')
    })
  })

  it('renders account information and logs out from the dashboard', async () => {
    const authState = makeAuthState({
      logout: vi.fn().mockResolvedValue(undefined),
      user: ref(sampleUser),
    })
    useAuthMock.mockReturnValue(authState)

    const wrapper = mount(DashboardView, {
      global: {
        stubs: {
          RouterLink: true,
        },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Welcome back, Parent')
    expect(wrapper.text()).toContain('Create your first story')
    expect(wrapper.text()).toContain('Story setup')

    const logoutButton = wrapper.get('button[aria-label="Log out"]')
    await logoutButton.trigger('click')
    await flushPromises()

    expect(authState.logout).toHaveBeenCalledTimes(1)
    expect(pushMock).toHaveBeenCalledWith({ name: 'login' })
  })
})

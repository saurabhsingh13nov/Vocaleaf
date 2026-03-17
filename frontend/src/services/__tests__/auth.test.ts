import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/services/api'
import {
  googleAuth,
  linkGoogleAccount,
  login,
  refreshSession,
  register,
  type User,
} from '@/services/auth'

vi.mock('@/services/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

const mockedPost = vi.mocked(api.post)

const sampleUser: User = {
  id: 'cc4e3be9-0e56-4d1b-9128-655ddcf06092',
  primary_email: 'parent@example.com',
  full_name: 'Parent Reader',
  avatar_url: null,
  status: 'active',
  role: 'customer',
  email_verified_at: null,
  created_at: '2026-03-11T20:00:00Z',
}

describe('auth service', () => {
  beforeEach(() => {
    mockedPost.mockReset()
  })

  it('unwraps the nested user from register', async () => {
    mockedPost.mockResolvedValueOnce({
      data: { access_token: 'access', refresh_token: 'refresh', user: sampleUser },
    } as never)

    const result = await register({
      email: 'parent@example.com',
      full_name: 'Parent Reader',
      password: 'securepass123',
    })

    expect(result).toEqual(sampleUser)
    expect(mockedPost).toHaveBeenCalledWith('/auth/register', {
      email: 'parent@example.com',
      full_name: 'Parent Reader',
      password: 'securepass123',
    })
  })

  it('unwraps the nested user from login and Google auth flows', async () => {
    mockedPost
      .mockResolvedValueOnce({ data: { access_token: 'a1', refresh_token: 'r1', user: sampleUser } } as never)
      .mockResolvedValueOnce({ data: { access_token: 'a2', refresh_token: 'r2', user: sampleUser } } as never)
      .mockResolvedValueOnce({ data: { access_token: 'a3', refresh_token: 'r3', user: sampleUser } } as never)

    expect(await login({ email: 'parent@example.com', password: 'securepass123' })).toEqual(sampleUser)
    expect(await googleAuth('google-credential')).toEqual(sampleUser)
    expect(await linkGoogleAccount('google-credential', 'securepass123')).toEqual(sampleUser)
  })

  it('returns the new refresh payload shape', async () => {
    mockedPost.mockResolvedValueOnce({ data: { access_token: 'new-access-token' } } as never)

    await expect(refreshSession()).resolves.toEqual({ access_token: 'new-access-token' })
    expect(mockedPost).toHaveBeenCalledWith('/auth/refresh')
  })
})

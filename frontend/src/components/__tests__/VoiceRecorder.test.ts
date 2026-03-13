import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import VoiceRecorder from '@/components/VoiceRecorder.vue'
import { getAudioDurationSeconds } from '@/services/voice'

vi.mock('@/services/voice', () => ({
  getAudioDurationSeconds: vi.fn(),
  isSupportedVoiceSampleMimeType: vi.fn(() => true),
  normalizeVoiceSampleMimeType: vi.fn((mimeType: string) => mimeType.split(';', 1)[0]),
}))

const mockedGetAudioDurationSeconds = vi.mocked(getAudioDurationSeconds)

class FakeMediaRecorder {
  static instances: FakeMediaRecorder[] = []

  mimeType = 'audio/webm'
  ondataavailable: ((event: BlobEvent) => void) | null = null
  onstop: (() => void) | null = null

  constructor(public stream: MediaStream) {
    FakeMediaRecorder.instances.push(this)
  }

  start() {
    return undefined
  }

  stop() {
    this.ondataavailable?.({ data: new Blob(['recorded'], { type: this.mimeType }) } as BlobEvent)
    this.onstop?.()
  }
}

describe('VoiceRecorder', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    FakeMediaRecorder.instances = []
    mockedGetAudioDurationSeconds.mockResolvedValue(6.4)
    vi.stubGlobal('MediaRecorder', FakeMediaRecorder)
    Object.defineProperty(globalThis.navigator, 'mediaDevices', {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockResolvedValue({
          getTracks: () => [{ stop: vi.fn() }],
        }),
      },
    })
  })

  it('emits a recorded sample after stop and upload', async () => {
    const wrapper = mount(VoiceRecorder)

    await wrapper.get('[data-testid="voice-start-recording"]').trigger('click')
    await flushPromises()
    expect(FakeMediaRecorder.instances).toHaveLength(1)

    await wrapper.get('[data-testid="voice-stop-recording"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Recorded sample ready')
    await wrapper.get('[data-testid="voice-submit-sample"]').trigger('click')

    const emitted = wrapper.emitted('submit')
    expect(emitted).toHaveLength(1)
    expect(emitted?.[0]?.[0]).toMatchObject({
      mimeType: 'audio/webm',
      durationSeconds: 6.4,
    })
  })

  it('normalizes codec-parameterized recorder mime types', async () => {
    FakeMediaRecorder.prototype.mimeType = 'audio/webm;codecs=opus'
    const wrapper = mount(VoiceRecorder)

    await wrapper.get('[data-testid="voice-start-recording"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="voice-stop-recording"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="voice-submit-sample"]').trigger('click')

    const emitted = wrapper.emitted('submit')
    expect(emitted).toHaveLength(1)
    expect(emitted?.[0]?.[0]).toMatchObject({
      mimeType: 'audio/webm',
    })
  })

  it('accepts a selected audio file and emits it', async () => {
    const wrapper = mount(VoiceRecorder)
    await wrapper.get('[data-testid="voice-mode-upload"]').trigger('click')

    const file = new File(['voice'], 'sample.webm', { type: 'audio/webm' })
    const input = wrapper.get('[data-testid="voice-file-input"]')
    Object.defineProperty(input.element, 'files', {
      configurable: true,
      value: [file],
    })
    await input.trigger('change')
    await flushPromises()

    expect(wrapper.text()).toContain('sample.webm')
    await wrapper.get('[data-testid="voice-submit-sample"]').trigger('click')

    const emitted = wrapper.emitted('submit')
    expect(emitted).toHaveLength(1)
    expect(emitted?.[0]?.[0]).toMatchObject({
      file,
      mimeType: 'audio/webm',
      durationSeconds: 6.4,
    })
  })
})

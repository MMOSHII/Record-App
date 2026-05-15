import { describe, it, expect, vi } from 'vitest'

function makeResponse(body, ok = true, status = 200) {
  return {
    ok,
    status,
    json: vi.fn().mockResolvedValue(body),
    text: vi.fn().mockResolvedValue(typeof body === 'string' ? body : JSON.stringify(body))
  }
}

vi.mock('../stores/appStore.js', () => {
  const state = {
    token: 'test-token',
    settings: {
      apiUrl: 'https://api.example.com',
      provider: 'ollama',
      model: '',
      apiKey: ''
    }
  }
  return {
    useAppStore: () => ({
      state,
      getBaseUrl: () => 'https://api.example.com'
    })
  }
})

const chatbotApi = await import('../services/chatbotApi.js')

describe('chatbotApi', () => {
  it('creates a chat session', async () => {
    global.fetch = vi.fn().mockResolvedValue(makeResponse({ session_id: 's1' }))
    const data = await chatbotApi.createChatbotSession('job_1', { title: 'My Session' })
    expect(data.session_id).toBe('s1')
    const [url, opts] = global.fetch.mock.calls[0]
    expect(url).toBe('https://api.example.com/api/v1/chat/job_1/session')
    expect(opts.method).toBe('POST')
  })

  it('sends a chat message to history session endpoint', async () => {
    global.fetch = vi.fn().mockResolvedValue(makeResponse({ answer: 'ok', session_id: 's1' }))
    const data = await chatbotApi.sendChatbotMessage('job_1', { question: 'q', sessionId: 's1' })
    expect(data.answer).toBe('ok')
    const [url] = global.fetch.mock.calls[0]
    expect(url).toBe('https://api.example.com/api/v1/chat/job_1/message')
  })
})


import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../services/chatbotApi.js', () => ({
  fetchChatbotSessions: vi.fn().mockResolvedValue({ sessions: [{ session_id: 's1', title: 'Conversation' }] }),
  fetchChatbotSession: vi.fn().mockResolvedValue({ messages: [{ role: 'assistant', content: 'hello' }] }),
  sendChatbotMessage: vi.fn().mockResolvedValue({
    session_id: 's1',
    session: { messages: [{ role: 'user', content: 'q' }, { role: 'assistant', content: 'a' }] }
  }),
  createChatbotSession: vi.fn().mockResolvedValue({ session_id: 's2', title: 'New' }),
  deleteChatbotSession: vi.fn().mockResolvedValue({ deleted: true })
}))

describe('chatbotStore', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  it('loads sessions and selects active messages', async () => {
    const { useChatbotStore } = await import('../stores/chatbotStore.js')
    const store = useChatbotStore()
    await store.loadSessions('job_1', { autoSelect: true })
    const state = store.ensureHistoryState('job_1')
    expect(state.sessions.length).toBe(1)
    expect(state.messages.length).toBe(1)
  })
})


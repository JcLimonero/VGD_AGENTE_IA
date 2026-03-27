import { create } from 'zustand'
import { ChatMessage, AgentResponse } from '@/types'

interface ChatStore {
  messages: ChatMessage[]
  isLoading: boolean
  error: string | null

  addMessage: (message: ChatMessage) => void
  setMessages: (messages: ChatMessage[]) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  clearMessages: () => void
}

export const useChatStore = create<ChatStore>((set) => ({
  messages: [],
  isLoading: false,
  error: null,

  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, message],
    })),

  setMessages: (messages) => set({ messages }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  clearMessages: () => set({ messages: [] }),
}))

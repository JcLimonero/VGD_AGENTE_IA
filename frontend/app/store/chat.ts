import { create } from 'zustand'
import { ChatMessage } from '@/types'

interface ChatStore {
  messages: ChatMessage[]
  isLoading: boolean
  error: string | null
  /** Texto a restaurar en el input tras cancelar el envío (se consume en la página). */
  cancelledDraft: string | null

  addMessage: (message: ChatMessage) => void
  removeMessage: (id: string) => void
  setMessages: (messages: ChatMessage[]) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  setCancelledDraft: (text: string | null) => void
  clearMessages: () => void
}

export const useChatStore = create<ChatStore>((set) => ({
  messages: [],
  isLoading: false,
  error: null,
  cancelledDraft: null,

  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, message],
    })),

  removeMessage: (id) =>
    set((state) => ({
      messages: state.messages.filter((m) => m.id !== id),
    })),

  setMessages: (messages) => set({ messages }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  setCancelledDraft: (text) => set({ cancelledDraft: text }),
  clearMessages: () => set({ messages: [], cancelledDraft: null }),
}))

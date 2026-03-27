import { useRef, useCallback } from 'react'
import axios from 'axios'
import { useChatStore } from '@/store/chat'
import { apiClient } from '@/services/api'
import { ChatMessage } from '@/types'
import { v4 as uuidv4 } from 'uuid'

function isAbortError(err: unknown): boolean {
  if (axios.isCancel(err)) return true
  const code = err && typeof err === 'object' && 'code' in err ? String((err as { code: unknown }).code) : ''
  return code === 'ERR_CANCELED'
}

export function useChat() {
  const {
    messages,
    isLoading,
    error,
    cancelledDraft,
    addMessage,
    removeMessage,
    setLoading,
    setError,
    setCancelledDraft,
    clearMessages,
  } = useChatStore()

  const abortRef = useRef<AbortController | null>(null)
  const pendingUserMessageIdRef = useRef<string | null>(null)
  const lastOutgoingContentRef = useRef<string | null>(null)

  const cancelPendingRequest = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  const sendMessage = async (content: string) => {
    const userMessage: ChatMessage = {
      id: uuidv4(),
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    }

    pendingUserMessageIdRef.current = userMessage.id
    lastOutgoingContentRef.current = content
    addMessage(userMessage)
    setLoading(true)
    setError(null)

    abortRef.current = new AbortController()

    try {
      const response = await apiClient.sendMessage(content, undefined, abortRef.current.signal)

      const assistantMessage: ChatMessage = {
        id: uuidv4(),
        role: 'assistant',
        content: response.message,
        timestamp: new Date().toISOString(),
        metadata: {
          query_executed: response.query_executed,
          query_id: response.query_id,
          context: response.context,
          results: response.results ?? undefined,
          user_question: content,
        },
      }

      addMessage(assistantMessage)
      setError(null)
    } catch (err: unknown) {
      if (isAbortError(err)) {
        const uid = pendingUserMessageIdRef.current
        if (uid) removeMessage(uid)
        setError(null)
        setCancelledDraft(lastOutgoingContentRef.current ?? '')
      } else {
        const msg = err instanceof Error ? err.message : 'Error al enviar el mensaje'
        setError(msg)
      }
    } finally {
      setLoading(false)
      pendingUserMessageIdRef.current = null
      lastOutgoingContentRef.current = null
      abortRef.current = null
    }
  }

  return {
    messages,
    isLoading,
    error,
    cancelledDraft,
    sendMessage,
    cancelPendingRequest,
    setCancelledDraft,
    clearMessages,
  }
}

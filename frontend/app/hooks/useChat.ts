import { useChatStore } from '@/store/chat'
import { apiClient } from '@/services/api'
import { ChatMessage } from '@/types'
import { v4 as uuidv4 } from 'uuid'

export function useChat() {
  const { messages, isLoading, error, addMessage, setMessages, setLoading, setError, clearMessages } = useChatStore()

  const sendMessage = async (content: string) => {
    // Agregar mensaje del usuario
    const userMessage: ChatMessage = {
      id: uuidv4(),
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    }

    addMessage(userMessage)
    setLoading(true)

    try {
      const response = await apiClient.sendMessage(content)

      // Agregar respuesta del asistente
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
        },
      }

      addMessage(assistantMessage)
      setError(null)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return {
    messages,
    isLoading,
    error,
    sendMessage,
    clearMessages,
  }
}

'use client'

import { useEffect, useState, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'
import { useChat } from '@/hooks/useChat'
import { AppBreadcrumb } from '@/components/AppBreadcrumb'
import { ChatMessageList } from '@/components/ChatMessageList'

export default function ChatPage() {
  const router = useRouter()
  const { isAuthenticated, logout } = useAuth()
  const { messages, isLoading, error, cancelledDraft, sendMessage, cancelPendingRequest, setCancelledDraft } =
    useChat()
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/auth/login')
    }
  }, [isAuthenticated, router])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (cancelledDraft === null) return
    if (cancelledDraft !== '') setInput(cancelledDraft)
    setCancelledDraft(null)
  }, [cancelledDraft, setCancelledDraft])

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim()) return
    const userInput = input
    setInput('')
    await sendMessage(userInput)
    inputRef.current?.focus()
  }

  if (!isAuthenticated) return null

  return (
    <div className="min-h-screen flex flex-col bg-gray-50 dark:bg-slate-900">
      <header className="bg-white dark:bg-slate-800 border-b border-gray-200 dark:border-slate-700">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <AppBreadcrumb
            items={[
              { label: 'Dashboard', href: '/dashboard' },
              { label: 'Chat' },
            ]}
          />

          <button
            type="button"
            onClick={() => {
              logout()
              router.push('/auth/login')
            }}
            aria-label="Cerrar sesión"
            className="text-sm px-3 py-1.5 bg-red-50 hover:bg-red-100 dark:bg-red-900/30 dark:hover:bg-red-900/50 text-red-600 dark:text-red-400 rounded-lg transition"
          >
            Cerrar sesión
          </button>
        </div>
      </header>

      <main className="flex-1 max-w-4xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8 overflow-y-auto">
        <ChatMessageList
          messages={messages}
          isLoading={isLoading}
          error={error}
          cancelPendingRequest={cancelPendingRequest}
          messagesEndRef={messagesEndRef}
          emptyHint="Comienza una conversación. Pregunta sobre tus datos."
        />
      </main>

      <footer className="border-t border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800">
        <form
          onSubmit={handleSendMessage}
          className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-4"
        >
          <div className="flex flex-wrap items-center gap-2">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={isLoading}
              placeholder="Escribe tu pregunta..."
              aria-label="Mensaje para el agente"
              className="min-w-0 flex-1 px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-slate-700 dark:text-white disabled:opacity-50"
            />
            {isLoading && (
              <button
                type="button"
                onClick={() => cancelPendingRequest()}
                aria-label="Cancelar consulta al agente"
                className="px-4 py-3 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 transition hover:bg-gray-50 dark:border-slate-600 dark:text-gray-200 dark:hover:bg-slate-700"
              >
                Cancelar
              </button>
            )}
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              aria-label="Enviar mensaje"
              className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg transition"
            >
              Enviar
            </button>
          </div>
        </form>
      </footer>
    </div>
  )
}

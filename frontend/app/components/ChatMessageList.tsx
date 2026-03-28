'use client'

import type { Ref } from 'react'
import { AgentResponseDataPanel } from '@/components/AgentResponseDataPanel'
import { SimpleMarkdown } from '@/components/SimpleMarkdown'
import type { ChatMessage } from '@/types'

type Props = {
  messages: ChatMessage[]
  isLoading: boolean
  error: string | null
  cancelPendingRequest: () => void
  messagesEndRef: Ref<HTMLDivElement>
  /** Texto bajo el icono cuando no hay mensajes (p. ej. página completa vs widget). */
  emptyHint?: string
}

export function ChatMessageList({
  messages,
  isLoading,
  error,
  cancelPendingRequest,
  messagesEndRef,
  emptyHint,
}: Props) {
  return (
    <div className="space-y-4">
      {messages.length === 0 && (
        <div className="py-8 text-center">
          <div className="mb-3 text-3xl">💬</div>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            {emptyHint ?? 'Pregunta sobre tus datos del DWH en lenguaje natural.'}
          </p>
        </div>
      )}

      {messages.map((msg) => (
        <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
          {msg.role === 'user' ? (
            <div className="max-w-[85%] rounded-lg rounded-br-none bg-blue-600 px-3 py-2.5 text-white">
              <p className="text-sm">{msg.content}</p>
            </div>
          ) : (
            <div className="max-w-[95%] rounded-lg rounded-bl-none border border-gray-200 bg-white px-3 py-2.5 text-gray-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white">
              <AgentResponseDataPanel message={msg} summary={<SimpleMarkdown text={msg.content} />} />
            </div>
          )}
        </div>
      ))}

      {isLoading && (
        <div className="flex justify-start">
          <div className="flex max-w-md flex-col gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2.5 dark:border-slate-700 dark:bg-slate-800">
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-600 dark:text-gray-300">Consultando al agente…</span>
              <div className="flex space-x-1">
                <div className="h-2 w-2 animate-bounce rounded-full bg-gray-400" />
                <div className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:100ms]" />
                <div className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:200ms]" />
              </div>
            </div>
            <button
              type="button"
              onClick={() => cancelPendingRequest()}
              className="self-start rounded-lg border border-gray-300 px-2 py-1 text-xs font-medium text-gray-700 transition hover:bg-gray-50 dark:border-slate-600 dark:text-gray-200 dark:hover:bg-slate-700"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-600 dark:border-red-800 dark:bg-red-950/40 dark:text-red-200">
          {error}
        </div>
      )}

      <div ref={messagesEndRef} />
    </div>
  )
}

'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import * as Dialog from '@radix-ui/react-dialog'
import { MessageCircle, X } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { useChat } from '@/hooks/useChat'
import { ChatMessageList } from '@/components/ChatMessageList'
import { cn } from '@/lib/utils'

/**
 * FAB inferior derecho que abre el chat en un diálogo modal (Radix), con overlay,
 * foco atrapado y cierre con Escape o clic fuera — mismo historial que /chat (Zustand).
 */
export function FloatingChatWidget() {
  const pathname = usePathname()
  const { isAuthenticated } = useAuth()
  const { messages, isLoading, error, cancelledDraft, sendMessage, cancelPendingRequest, setCancelledDraft } =
    useChat()
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const hide =
    !isAuthenticated ||
    pathname?.startsWith('/auth') ||
    pathname === '/chat'

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, open, isLoading])

  useEffect(() => {
    if (cancelledDraft === null) return
    if (cancelledDraft !== '') setInput(cancelledDraft)
    setCancelledDraft(null)
  }, [cancelledDraft, setCancelledDraft])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim()) return
    const t = input
    setInput('')
    await sendMessage(t)
  }

  if (hide) return null

  return (
    <>
      <Dialog.Root open={open} onOpenChange={setOpen}>
        <Dialog.Portal>
          <Dialog.Overlay
            className={cn(
              'fixed inset-0 z-[190] bg-slate-950/55 backdrop-blur-[2px]',
              'data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
              'duration-200'
            )}
          />
          <Dialog.Content
            className={cn(
              'fixed z-[191] flex h-[min(70vh,560px)] w-[min(calc(100vw-2rem),420px)] flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-2xl',
              'bottom-[13.75rem] right-4 sm:bottom-[14.25rem] sm:right-6',
              'dark:border-slate-600 dark:bg-slate-900',
              'data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
              'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-bottom-2 data-[state=open]:slide-in-from-bottom-2',
              'duration-200 focus:outline-none'
            )}
            onOpenAutoFocus={(e) => {
              e.preventDefault()
              inputRef.current?.focus()
            }}
          >
            <Dialog.Title className="sr-only">Asistente DWH</Dialog.Title>
            <Dialog.Description className="sr-only">
              Ventana de chat con el agente de consultas al almacén de datos. Puedes escribir preguntas en lenguaje
              natural.
            </Dialog.Description>

            <div className="flex items-center justify-between border-b border-gray-100 bg-gradient-to-r from-slate-600 to-indigo-600 px-4 py-3 text-white dark:from-slate-700 dark:to-indigo-800">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold">Agente DWH</p>
                <p className="truncate text-xs text-white/80">Misma conversación que en Chat</p>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <Link
                  href="/chat"
                  className="rounded-lg px-2 py-1.5 text-xs font-medium text-white/90 transition hover:bg-white/10"
                  onClick={() => setOpen(false)}
                >
                  Pantalla completa
                </Link>
                <Dialog.Close asChild>
                  <button
                    type="button"
                    className="rounded-lg p-2 text-white/90 transition hover:bg-white/10"
                    aria-label="Cerrar chat"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </Dialog.Close>
              </div>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3">
              <ChatMessageList
                messages={messages}
                isLoading={isLoading}
                error={error}
                cancelPendingRequest={cancelPendingRequest}
                messagesEndRef={messagesEndRef}
              />
            </div>

            <form
              onSubmit={(e) => void handleSubmit(e)}
              className="border-t border-gray-200 p-3 dark:border-slate-700"
            >
              <div className="flex gap-2">
                <input
                  ref={inputRef}
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  disabled={isLoading}
                  placeholder="Escribe tu pregunta…"
                  className="min-w-0 flex-1 rounded-xl border border-gray-300 bg-gray-50 px-3 py-2.5 text-sm text-gray-900 placeholder:text-gray-500 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-500/20 dark:border-slate-600 dark:bg-slate-800 dark:text-white dark:placeholder:text-gray-400 disabled:opacity-50"
                />
                <button
                  type="submit"
                  disabled={isLoading || !input.trim()}
                  className="shrink-0 rounded-xl bg-slate-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-slate-700 disabled:opacity-50"
                >
                  Enviar
                </button>
              </div>
            </form>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'fixed bottom-4 right-4 z-[192] flex h-14 w-14 items-center justify-center rounded-full shadow-lg transition focus:outline-none focus:ring-4 focus:ring-slate-500/40 sm:bottom-6 sm:right-6',
          open
            ? 'bg-slate-700 text-white hover:bg-slate-800 dark:bg-slate-600 dark:hover:bg-slate-500'
            : 'bg-slate-600 text-white hover:bg-slate-700'
        )}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label={open ? 'Cerrar asistente' : 'Abrir asistente de chat'}
      >
        {open ? <X className="h-7 w-7" strokeWidth={2} /> : <MessageCircle className="h-7 w-7" strokeWidth={2} />}
      </button>
    </>
  )
}

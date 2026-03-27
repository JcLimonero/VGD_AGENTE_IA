'use client'

import { useEffect, useState, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'
import { useChat } from '@/hooks/useChat'
import { QueryResultData } from '@/types/index'

/** Renders simple markdown: **bold**, *italic*, - lists, line breaks */
function SimpleMarkdown({ text }: { text: string }) {
  const lines = text.split('\n')
  return (
    <div className="space-y-1 text-sm">
      {lines.map((line, i) => {
        // List item
        if (line.match(/^[-•]\s/)) {
          const content = line.replace(/^[-•]\s/, '')
          return (
            <div key={i} className="flex gap-1">
              <span className="shrink-0">•</span>
              <span dangerouslySetInnerHTML={{ __html: formatInline(content) }} />
            </div>
          )
        }
        // Numbered item
        if (line.match(/^\d+\.\s/)) {
          return (
            <div key={i} dangerouslySetInnerHTML={{ __html: formatInline(line) }} />
          )
        }
        // Empty line = spacing
        if (line.trim() === '') return <div key={i} className="h-1" />
        return (
          <div key={i} dangerouslySetInnerHTML={{ __html: formatInline(line) }} />
        )
      })}
    </div>
  )
}

function formatInline(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code class="bg-gray-100 dark:bg-slate-700 px-1 rounded text-xs">$1</code>')
}

function ResultsTable({ results }: { results: QueryResultData }) {
  const [showAll, setShowAll] = useState(false)
  const [showSql, setShowSql] = useState(false)
  const [copied, setCopied] = useState(false)
  const displayRows = showAll ? results.rows : results.rows.slice(0, 10)
  const cols = results.column_names

  const handleCopySql = () => {
    if (!results.generated_sql) return
    navigator.clipboard.writeText(results.generated_sql).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="mt-3 border border-gray-200 dark:border-slate-600 rounded-lg overflow-hidden text-xs">
      <div className="flex items-center justify-between px-3 py-2 bg-gray-50 dark:bg-slate-700 border-b border-gray-200 dark:border-slate-600">
        <span className="font-medium text-gray-700 dark:text-gray-300">
          {results.total_rows} registro{results.total_rows !== 1 ? 's' : ''}
        </span>
        <div className="flex gap-2">
          {results.generated_sql && (
            <>
              <button
                onClick={() => setShowSql(v => !v)}
                className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 underline"
              >
                {showSql ? 'Ocultar SQL' : 'Ver SQL'}
              </button>
              <button
                onClick={handleCopySql}
                className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 underline"
              >
                {copied ? '✓ Copiado' : 'Copiar SQL'}
              </button>
            </>
          )}
        </div>
      </div>

      {showSql && results.generated_sql && (
        <pre className="px-3 py-2 bg-gray-900 text-green-400 text-xs overflow-x-auto whitespace-pre-wrap">
          {results.generated_sql}
        </pre>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-gray-100 dark:bg-slate-600">
              {cols.map((col: string) => (
                <th key={col} className="px-3 py-2 font-semibold text-gray-700 dark:text-gray-200 whitespace-nowrap">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {displayRows.map((row: Record<string, unknown>, i: number) => (
              <tr
                key={i}
                className={i % 2 === 0 ? 'bg-white dark:bg-slate-800' : 'bg-gray-50 dark:bg-slate-750'}
              >
                {cols.map((col: string) => (
                  <td key={col} className="px-3 py-2 text-gray-800 dark:text-gray-200 whitespace-nowrap">
                    {row[col] === null || row[col] === undefined ? '—' : String(row[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {results.rows.length > 10 && (
        <div className="px-3 py-2 bg-gray-50 dark:bg-slate-700 border-t border-gray-200 dark:border-slate-600 text-center">
          <button
            onClick={() => setShowAll(v => !v)}
            className="text-blue-600 dark:text-blue-400 hover:underline"
          >
            {showAll ? 'Mostrar menos' : `Ver los ${results.rows.length} registros`}
          </button>
        </div>
      )}
    </div>
  )
}

export default function ChatPage() {
  const router = useRouter()
  const { isAuthenticated } = useAuth()
  const { messages, isLoading, error, sendMessage } = useChat()
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/auth/login')
    }
  }, [isAuthenticated, router])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim()) return
    const userInput = input
    setInput('')
    await sendMessage(userInput)
  }

  if (!isAuthenticated) return null

  return (
    <div className="min-h-screen flex flex-col bg-gray-50 dark:bg-slate-900">
      {/* Header */}
      <header className="bg-white dark:bg-slate-800 border-b border-gray-200 dark:border-slate-700">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            💬 Chat con Agente IA
          </h1>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Consulta el DWH usando lenguaje natural
          </p>
        </div>
      </header>

      {/* Chat Container */}
      <main className="flex-1 max-w-3xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8 overflow-y-auto">
        <div className="space-y-4">
          {messages.length === 0 && (
            <div className="text-center py-12">
              <div className="text-4xl mb-4">💬</div>
              <p className="text-gray-600 dark:text-gray-400">
                Comienza una conversación. Pregunta sobre tus datos.
              </p>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {msg.role === 'user' ? (
                <div className="max-w-xs lg:max-w-md px-4 py-3 rounded-lg bg-blue-600 text-white rounded-br-none">
                  <p className="text-sm">{msg.content}</p>
                </div>
              ) : (
                <div className="max-w-xl w-full px-4 py-3 rounded-lg bg-white dark:bg-slate-800 text-gray-900 dark:text-white rounded-bl-none border border-gray-200 dark:border-slate-700">
                  <SimpleMarkdown text={msg.content} />
                  {msg.metadata?.query_executed && msg.metadata?.results && (
                    <ResultsTable results={msg.metadata.results} />
                  )}
                  {msg.metadata?.query_executed && (
                    <p className="text-xs mt-2 text-gray-400 dark:text-gray-500">
                      ✓ Query ejecutada exitosamente
                    </p>
                  )}
                </div>
              )}
            </div>
          ))}

          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-white dark:bg-slate-800 text-gray-900 dark:text-white px-4 py-3 rounded-lg border border-gray-200 dark:border-slate-700">
                <div className="flex space-x-2">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-100"></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-200"></div>
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="p-4 bg-red-50 dark:bg-red-900 border border-red-200 dark:border-red-700 rounded-lg text-red-600 dark:text-red-200 text-sm">
              Error: {error}
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* Input Area */}
      <footer className="border-t border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800">
        <form
          onSubmit={handleSendMessage}
          className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-4"
        >
          <div className="flex space-x-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={isLoading}
              placeholder="Escribe tu pregunta..."
              className="flex-1 px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-slate-700 dark:text-white disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
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

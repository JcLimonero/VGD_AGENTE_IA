'use client'

/** Markdown mínimo: **negrita**, *cursiva*, listas, saltos de línea. */
export function SimpleMarkdown({ text }: { text: string }) {
  const lines = text.split('\n')
  return (
    <div className="space-y-1 text-sm">
      {lines.map((line, i) => {
        if (line.match(/^[-•]\s/)) {
          const content = line.replace(/^[-•]\s/, '')
          return (
            <div key={i} className="flex gap-1">
              <span className="shrink-0">•</span>
              <span dangerouslySetInnerHTML={{ __html: formatInline(content) }} />
            </div>
          )
        }
        if (line.match(/^\d+\.\s/)) {
          return <div key={i} dangerouslySetInnerHTML={{ __html: formatInline(line) }} />
        }
        if (line.trim() === '') return <div key={i} className="h-1" />
        return <div key={i} dangerouslySetInnerHTML={{ __html: formatInline(line) }} />
      })}
    </div>
  )
}

export function formatInline(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code class="bg-gray-100 dark:bg-slate-700 px-1 rounded text-xs">$1</code>')
}

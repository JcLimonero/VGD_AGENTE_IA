import type { Query } from '@/types'

/** La API FastAPI usa title / sql_text / original_question; el UI usa name / sql / description. */
export function normalizeSavedQuery(raw: Record<string, unknown>): Query {
  const sql = String(raw.sql ?? raw.sql_text ?? '')
  return {
    id: String(raw.id ?? ''),
    name: String(raw.name ?? raw.title ?? 'Sin título'),
    description: String(raw.description ?? raw.original_question ?? ''),
    sql,
    created_by: String(raw.created_by ?? raw.user_id ?? ''),
    created_at: String(raw.created_at ?? ''),
    updated_at: String(raw.updated_at ?? raw.created_at ?? ''),
    is_favorite: Boolean(raw.is_favorite),
    tags: Array.isArray(raw.tags) ? (raw.tags as unknown[]).map(String) : [],
  }
}

/** Cuerpo PUT /api/queries/{id} (campos del modelo QueryUpdate + original_question). */
export function toQueryUpdatePayload(input: {
  name: string
  description: string
  sql: string
}): Record<string, string> {
  return {
    title: input.name.trim(),
    original_question: input.description.trim(),
    sql_text: input.sql.trim(),
  }
}

import type { Query, QueryResultData, SavedQueryUpdatePayload } from '@/types'
import { fixSpanishSemicolonEnyeTypo } from '@/lib/spanishDisplay'

/** La API FastAPI usa title / sql_text / original_question. El UI usa name / sql / description. */
export function normalizeSavedQuery(raw: Record<string, unknown>): Query {
  const sql = String(raw.sql ?? raw.sql_text ?? '')
  return {
    id: String(raw.id ?? ''),
    name: fixSpanishSemicolonEnyeTypo(String(raw.name ?? raw.title ?? 'Sin título')),
    description: fixSpanishSemicolonEnyeTypo(
      String(raw.description ?? raw.original_question ?? '')
    ),
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
}): SavedQueryUpdatePayload {
  return {
    title: fixSpanishSemicolonEnyeTypo(input.name.trim()),
    original_question: fixSpanishSemicolonEnyeTypo(input.description.trim()),
    sql_text: input.sql.trim(),
  }
}

/** Normaliza la respuesta de POST /api/queries/{id}/execute → QueryResultData. */
export function queryResultFromExecuteApi(
  raw: Record<string, unknown>,
  sqlFallback?: string
): QueryResultData {
  const labels = raw.column_labels_es
  const gen = raw.generated_sql
  return {
    rows: (raw.rows as Record<string, unknown>[]) ?? [],
    column_names: (raw.column_names as string[]) ?? [],
    column_labels_es:
      labels && typeof labels === 'object' && !Array.isArray(labels)
        ? (labels as Record<string, string>)
        : undefined,
    total_rows: Number(raw.total_rows ?? 0),
    generated_sql:
      typeof gen === 'string' && gen.trim()
        ? gen.trim()
        : sqlFallback?.trim()
          ? sqlFallback.trim()
          : undefined,
  }
}

import { useQueryStore } from '@/store/queries'
import { apiClient } from '@/services/api'
import { normalizeSavedQuery } from '@/lib/savedQuery'
import { getApiErrorMessage } from '@/lib/apiError'
import type { SavedQueryCreatePayload, SavedQueryUpdatePayload } from '@/types'

export function useQuery() {
  const {
    queries,
    selectedQuery,
    queryResult,
    isLoading,
    error,
    setQueries,
    selectQuery,
    setQueryResult,
    setLoading,
    setError,
    addQuery,
    removeQuery,
    updateQuery,
  } = useQueryStore()

  const fetchQueries = async () => {
    setLoading(true)
    try {
      const data = await apiClient.getQueries()
      const list = Array.isArray(data) ? data : []
      setQueries(list.map((item) => normalizeSavedQuery(item as Record<string, unknown>)))
      setError(null)
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'No se pudieron cargar las consultas'))
    } finally {
      setLoading(false)
    }
  }

  const executeQuery = async (queryId: string) => {
    setLoading(true)
    try {
      const result = await apiClient.executeQuery(queryId)
      setQueryResult(result)
      setError(null)
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'Error al ejecutar la consulta'))
    } finally {
      setLoading(false)
    }
  }

  const createQuery = async (query: SavedQueryCreatePayload) => {
    try {
      const newQuery = await apiClient.createQuery(query)
      const normalized = normalizeSavedQuery(newQuery as Record<string, unknown>)
      addQuery(normalized)
      setError(null)
      return normalized
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'No se pudo crear la consulta'))
      throw err
    }
  }

  const deleteQueryById = async (id: string) => {
    try {
      await apiClient.deleteQuery(id)
      removeQuery(id)
      setError(null)
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'No se pudo eliminar la consulta'))
      throw err
    }
  }

  const modifyQuery = async (id: string, updates: SavedQueryUpdatePayload) => {
    try {
      const updated = await apiClient.updateQuery(id, updates)
      const normalized = normalizeSavedQuery(updated as Record<string, unknown>)
      updateQuery(id, normalized)
      setError(null)
      return normalized
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'No se pudo actualizar la consulta'))
      throw err
    }
  }

  return {
    queries,
    selectedQuery,
    queryResult,
    isLoading,
    error,
    selectQuery,
    fetchQueries,
    executeQuery,
    createQuery,
    deleteQuery: deleteQueryById,
    updateQuery: modifyQuery,
  }
}

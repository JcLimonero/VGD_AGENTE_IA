import { create } from 'zustand'
import { Query, QueryResult } from '@/types'

interface QueryStore {
  queries: Query[]
  selectedQuery: Query | null
  queryResult: QueryResult | null
  isLoading: boolean
  error: string | null

  setQueries: (queries: Query[]) => void
  selectQuery: (query: Query | null) => void
  setQueryResult: (result: QueryResult | null) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  addQuery: (query: Query) => void
  removeQuery: (id: string) => void
  updateQuery: (id: string, query: Query) => void
}

export const useQueryStore = create<QueryStore>((set) => ({
  queries: [],
  selectedQuery: null,
  queryResult: null,
  isLoading: false,
  error: null,

  setQueries: (queries) => set({ queries }),
  selectQuery: (query) => set({ selectedQuery: query }),
  setQueryResult: (result) => set({ queryResult: result }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),

  addQuery: (query) =>
    set((state) => ({
      queries: [...state.queries, query],
    })),

  removeQuery: (id) =>
    set((state) => ({
      queries: state.queries.filter((q) => q.id !== id),
    })),

  updateQuery: (id, query) =>
    set((state) => ({
      queries: state.queries.map((q) => (q.id === id ? query : q)),
    })),
}))

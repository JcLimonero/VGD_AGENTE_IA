import { AxiosError } from 'axios'

export type FastApiValidationItem = { loc?: unknown[]; msg?: string; type?: string }

/** Convierte `detail` de FastAPI (string, lista de errores Pydantic u objeto) en texto para la UI. */
export function messageFromFastApiDetail(detail: unknown): string {
  if (detail == null) return ''
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item && typeof item === 'object' && 'msg' in item) {
          const m = (item as FastApiValidationItem).msg
          if (typeof m === 'string') return m
        }
        return JSON.stringify(item)
      })
      .join('; ')
  }
  if (typeof detail === 'object' && detail !== null && 'msg' in detail) {
    const m = (detail as FastApiValidationItem).msg
    if (typeof m === 'string') return m
  }
  return String(detail)
}

/**
 * Mensaje legible a partir de un error de Axios (cuerpo FastAPI) o Error genérico.
 */
export function getApiErrorMessage(err: unknown, fallback = 'Ha ocurrido un error'): string {
  if (err instanceof AxiosError) {
    const body = err.response?.data
    if (body && typeof body === 'object' && body !== null && 'detail' in body) {
      const msg = messageFromFastApiDetail((body as { detail: unknown }).detail)
      if (msg) return msg
    }
    if (typeof err.message === 'string' && err.message) return err.message
  }
  if (err instanceof Error && err.message) return err.message
  return fallback
}

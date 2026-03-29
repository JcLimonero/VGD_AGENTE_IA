'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/hooks/useAuth'
import { apiClient } from '@/services/api'
import { AppBreadcrumb } from '@/components/AppBreadcrumb'
import type { PlatformRole } from '@/types'
import { getApiErrorMessage } from '@/lib/apiError'

export default function AdminRolesPage() {
  const router = useRouter()
  const { user, isAuthenticated } = useAuth()
  const [roles, setRoles] = useState<PlatformRole[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<PlatformRole | null>(null)

  const isSysAdmin = user?.role === 'sysadmin'

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/auth/login')
      return
    }
    if (!isSysAdmin) {
      router.push('/dashboard')
      return
    }
    loadRoles()
  }, [isAuthenticated])

  async function loadRoles() {
    setLoading(true)
    setError(null)
    try {
      const data = await apiClient.getAdminRoles()
      setRoles(data)
    } catch (e) {
      setError(getApiErrorMessage(e, 'No se pudieron cargar los roles'))
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete(role: PlatformRole) {
    setDeletingId(role.id)
    try {
      await apiClient.deleteAdminRole(role.id)
      setConfirmDelete(null)
      await loadRoles()
    } catch (e) {
      alert(getApiErrorMessage(e, 'Error al eliminar el rol'))
    } finally {
      setDeletingId(null)
    }
  }

  if (!isAuthenticated || !isSysAdmin) return null

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-900">
      <header className="border-b border-gray-200 bg-white dark:border-slate-700 dark:bg-slate-800">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <div>
            <AppBreadcrumb
              items={[
                { label: 'Dashboard', href: '/dashboard' },
                { label: 'Administración' },
                { label: 'Roles' },
              ]}
            />
            <h1 className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">Gestión de Roles</h1>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/admin/users"
              className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 transition hover:bg-gray-50 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200 dark:hover:bg-slate-600"
            >
              Gestionar Usuarios
            </Link>
            <Link
              href="/admin/roles/new"
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700"
            >
              + Nuevo Rol
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-6 sm:px-6">
        {loading && (
          <div className="flex items-center justify-center py-12 text-gray-400">Cargando roles…</div>
        )}
        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
            {error}
          </div>
        )}
        {!loading && !error && (
          <div className="space-y-4">
            {/* Base roles */}
            <div>
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-slate-400">
                Roles base del sistema
              </h2>
              <div className="grid gap-3 sm:grid-cols-2">
                {roles.filter((r) => r.is_base_role).map((role) => (
                  <RoleCard key={role.id} role={role} onEdit={undefined} onDelete={undefined} />
                ))}
              </div>
            </div>

            {/* Dynamic roles */}
            <div className="mt-6">
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-slate-400">
                Roles dinámicos
              </h2>
              {roles.filter((r) => !r.is_base_role).length === 0 ? (
                <div className="rounded-xl border border-dashed border-gray-300 bg-white p-8 text-center dark:border-slate-600 dark:bg-slate-800">
                  <p className="text-gray-400 dark:text-slate-400">No hay roles dinámicos creados.</p>
                  <Link
                    href="/admin/roles/new"
                    className="mt-3 inline-block text-sm text-blue-600 transition hover:text-blue-700 dark:text-blue-400"
                  >
                    Crear el primer rol →
                  </Link>
                </div>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {roles.filter((r) => !r.is_base_role).map((role) => (
                    <RoleCard
                      key={role.id}
                      role={role}
                      onEdit={() => router.push(`/admin/roles/${role.id}`)}
                      onDelete={() => setConfirmDelete(role)}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      {/* Confirm delete modal */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm">
          <div className="w-full max-w-sm rounded-2xl border border-gray-200 bg-white p-6 shadow-2xl dark:border-slate-700 dark:bg-slate-800">
            <h2 className="mb-3 text-lg font-semibold text-gray-900 dark:text-white">Eliminar Rol</h2>
            <p className="text-sm text-gray-600 dark:text-slate-300">
              ¿Eliminar el rol <strong>{confirmDelete.name}</strong>? Los usuarios asignados a este rol
              quedarán sin rol asignado.
            </p>
            <div className="mt-5 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setConfirmDelete(null)}
                className="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm text-gray-700 transition hover:bg-gray-50 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={() => handleDelete(confirmDelete)}
                disabled={deletingId === confirmDelete.id}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-red-700 disabled:opacity-50"
              >
                {deletingId === confirmDelete.id ? 'Eliminando…' : 'Eliminar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function RoleCard({
  role,
  onEdit,
  onDelete,
}: {
  role: PlatformRole
  onEdit: (() => void) | undefined
  onDelete: (() => void) | undefined
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-gray-900 dark:text-white">{role.name}</span>
            {role.is_base_role && (
              <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500 dark:bg-slate-700 dark:text-slate-400">
                base
              </span>
            )}
          </div>
          {role.description && (
            <p className="mt-0.5 truncate text-xs text-gray-500 dark:text-slate-400">{role.description}</p>
          )}
        </div>
        <span className="shrink-0 rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-600 dark:bg-blue-900/30 dark:text-blue-300">
          {role.user_count ?? 0} usuarios
        </span>
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        <FeatureBadge active={role.all_agencies} label="Todas las agencias" />
        <FeatureBadge active={role.can_create_users} label="Crea usuarios" />
        <FeatureBadge active={role.can_access_config} label="Configuración" />
      </div>
      {!role.is_base_role && (onEdit || onDelete) && (
        <div className="mt-3 flex justify-end gap-2 border-t border-gray-100 pt-3 dark:border-slate-700">
          {onEdit && (
            <button
              type="button"
              onClick={onEdit}
              className="rounded px-2 py-1 text-xs text-blue-600 transition hover:bg-blue-50 dark:text-blue-400 dark:hover:bg-blue-900/20"
            >
              Editar
            </button>
          )}
          {onDelete && (
            <button
              type="button"
              onClick={onDelete}
              className="rounded px-2 py-1 text-xs text-red-600 transition hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-900/20"
            >
              Eliminar
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function FeatureBadge({ active, label }: { active: boolean; label: string }) {
  return (
    <span
      className={`rounded px-2 py-0.5 text-xs font-medium ${
        active
          ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
          : 'bg-gray-100 text-gray-400 line-through dark:bg-slate-700 dark:text-slate-500'
      }`}
    >
      {label}
    </span>
  )
}

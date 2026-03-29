'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/hooks/useAuth'
import { apiClient } from '@/services/api'
import { AppBreadcrumb } from '@/components/AppBreadcrumb'
import type { PlatformUser, PlatformRole } from '@/types'
import { getApiErrorMessage } from '@/lib/apiError'

function Badge({ children, variant = 'default' }: { children: React.ReactNode; variant?: 'default' | 'blue' | 'green' | 'red' }) {
  const cls = {
    default: 'bg-gray-100 text-gray-700 dark:bg-slate-700 dark:text-slate-300',
    blue: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
    green: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300',
    red: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
  }[variant]
  return <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${cls}`}>{children}</span>
}

interface UserFormState {
  email: string
  display_name: string
  password: string
  role_id: number | ''
}

interface EditFormState {
  display_name: string
  role_id: number | ''
}

interface ResetPwState {
  new_password: string
  confirm: string
}

export default function AdminUsersPage() {
  const router = useRouter()
  const { user, isAuthenticated } = useAuth()
  const [users, setUsers] = useState<PlatformUser[]>([])
  const [roles, setRoles] = useState<PlatformRole[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Create modal
  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState<UserFormState>({ email: '', display_name: '', password: '', role_id: '' })
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  // Edit modal
  const [editUser, setEditUser] = useState<PlatformUser | null>(null)
  const [editForm, setEditForm] = useState<EditFormState>({ display_name: '', role_id: '' })
  const [saving, setSaving] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)

  // Reset password modal
  const [resetUser, setResetUser] = useState<PlatformUser | null>(null)
  const [resetPw, setResetPw] = useState<ResetPwState>({ new_password: '', confirm: '' })
  const [resetting, setResetting] = useState(false)
  const [resetError, setResetError] = useState<string | null>(null)

  // Delete confirm
  const [deleteUser, setDeleteUser] = useState<PlatformUser | null>(null)
  const [deleting, setDeleting] = useState(false)

  const canManage = user?.role === 'sysadmin' || user?.can_create_users
  const isSysAdmin = user?.role === 'sysadmin'

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/auth/login')
      return
    }
    if (!canManage) {
      router.push('/dashboard')
      return
    }
    loadData()
  }, [isAuthenticated])

  async function loadData() {
    setLoading(true)
    setError(null)
    try {
      const [u, r] = await Promise.all([apiClient.getAdminUsers(), apiClient.getAdminRoles()])
      setUsers(u)
      setRoles(r)
    } catch (e) {
      setError(getApiErrorMessage(e, 'No se pudieron cargar los datos'))
    } finally {
      setLoading(false)
    }
  }

  async function handleCreate() {
    if (!createForm.email || !createForm.display_name || !createForm.password || createForm.role_id === '') return
    setCreating(true)
    setCreateError(null)
    try {
      await apiClient.createAdminUser({
        email: createForm.email,
        display_name: createForm.display_name,
        password: createForm.password,
        role_id: Number(createForm.role_id),
      })
      setShowCreate(false)
      setCreateForm({ email: '', display_name: '', password: '', role_id: '' })
      await loadData()
    } catch (e) {
      setCreateError(getApiErrorMessage(e, 'Error al crear usuario'))
    } finally {
      setCreating(false)
    }
  }

  function openEdit(u: PlatformUser) {
    setEditUser(u)
    setEditForm({ display_name: u.display_name, role_id: u.role_id ?? '' })
    setEditError(null)
  }

  async function handleEdit() {
    if (!editUser) return
    setSaving(true)
    setEditError(null)
    try {
      await apiClient.updateAdminUser(editUser.id, {
        display_name: editForm.display_name || undefined,
        role_id: editForm.role_id !== '' ? Number(editForm.role_id) : undefined,
      })
      setEditUser(null)
      await loadData()
    } catch (e) {
      setEditError(getApiErrorMessage(e, 'Error al actualizar usuario'))
    } finally {
      setSaving(false)
    }
  }

  function openReset(u: PlatformUser) {
    setResetUser(u)
    setResetPw({ new_password: '', confirm: '' })
    setResetError(null)
  }

  async function handleReset() {
    if (!resetUser) return
    if (resetPw.new_password !== resetPw.confirm) {
      setResetError('Las contraseñas no coinciden')
      return
    }
    if (!resetPw.new_password) return
    setResetting(true)
    setResetError(null)
    try {
      await apiClient.resetAdminUserPassword(resetUser.id, resetPw.new_password)
      setResetUser(null)
    } catch (e) {
      setResetError(getApiErrorMessage(e, 'Error al resetear contraseña'))
    } finally {
      setResetting(false)
    }
  }

  async function handleDelete() {
    if (!deleteUser) return
    setDeleting(true)
    try {
      await apiClient.deleteAdminUser(deleteUser.id)
      setDeleteUser(null)
      await loadData()
    } catch (e) {
      alert(getApiErrorMessage(e, 'Error al eliminar usuario'))
    } finally {
      setDeleting(false)
    }
  }

  if (!isAuthenticated || !canManage) return null

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-900">
      <header className="border-b border-gray-200 bg-white dark:border-slate-700 dark:bg-slate-800">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <div>
            <AppBreadcrumb
              items={[
                { label: 'Dashboard', href: '/dashboard' },
                { label: 'Administración' },
                { label: 'Usuarios' },
              ]}
            />
            <h1 className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">Gestión de Usuarios</h1>
          </div>
          <div className="flex items-center gap-3">
            {isSysAdmin && (
              <Link
                href="/admin/roles"
                className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 transition hover:bg-gray-50 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200 dark:hover:bg-slate-600"
              >
                Gestionar Roles
              </Link>
            )}
            <button
              type="button"
              onClick={() => { setShowCreate(true); setCreateError(null) }}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700"
            >
              + Nuevo Usuario
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
        {loading && (
          <div className="flex items-center justify-center py-12 text-gray-400">Cargando usuarios…</div>
        )}
        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
            {error}
          </div>
        )}
        {!loading && !error && (
          <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-slate-700 dark:bg-slate-800">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:border-slate-700 dark:bg-slate-700/50 dark:text-slate-400">
                  <th className="px-5 py-3">Usuario</th>
                  <th className="px-5 py-3">Rol</th>
                  <th className="px-5 py-3 hidden sm:table-cell">Permisos</th>
                  <th className="px-5 py-3 hidden md:table-cell">Último acceso</th>
                  <th className="px-5 py-3 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-slate-700">
                {users.map((u) => (
                  <tr key={u.id} className="group transition hover:bg-gray-50 dark:hover:bg-slate-700/30">
                    <td className="px-5 py-3">
                      <div className="font-medium text-gray-900 dark:text-white">{u.display_name}</div>
                      <div className="text-xs text-gray-400">{u.username}</div>
                    </td>
                    <td className="px-5 py-3">
                      <Badge variant={u.role_name === 'sysadmin' ? 'red' : u.role_name === 'director' ? 'blue' : 'default'}>
                        {u.role_name ?? '—'}
                      </Badge>
                    </td>
                    <td className="px-5 py-3 hidden sm:table-cell">
                      <div className="flex flex-wrap gap-1">
                        {u.can_create_users && <Badge variant="green">Crea usuarios</Badge>}
                        {u.can_access_config && <Badge variant="blue">Config</Badge>}
                      </div>
                    </td>
                    <td className="px-5 py-3 hidden md:table-cell text-gray-500 dark:text-slate-400">
                      {u.last_login_at
                        ? new Date(u.last_login_at).toLocaleDateString('es-MX', { day: '2-digit', month: 'short', year: 'numeric' })
                        : 'Nunca'}
                    </td>
                    <td className="px-5 py-3 text-right">
                      <div className="flex justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => openEdit(u)}
                          className="rounded px-2 py-1 text-xs text-blue-600 transition hover:bg-blue-50 dark:text-blue-400 dark:hover:bg-blue-900/20"
                        >
                          Editar
                        </button>
                        {isSysAdmin && (
                          <>
                            <button
                              type="button"
                              onClick={() => openReset(u)}
                              className="rounded px-2 py-1 text-xs text-amber-600 transition hover:bg-amber-50 dark:text-amber-400 dark:hover:bg-amber-900/20"
                            >
                              Reset pwd
                            </button>
                            <button
                              type="button"
                              onClick={() => setDeleteUser(u)}
                              className="rounded px-2 py-1 text-xs text-red-600 transition hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-900/20"
                              disabled={String(u.id) === user?.id}
                            >
                              Eliminar
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {users.length === 0 && (
              <div className="py-10 text-center text-gray-400">No hay usuarios registrados.</div>
            )}
          </div>
        )}
      </main>

      {/* Modal: Crear usuario */}
      {showCreate && (
        <ModalOverlay onClose={() => setShowCreate(false)}>
          <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Nuevo Usuario</h2>
          <div className="space-y-3">
            <FormField label="Email" required>
              <input
                type="email"
                value={createForm.email}
                onChange={(e) => setCreateForm((p) => ({ ...p, email: e.target.value }))}
                className={inputCls}
                placeholder="usuario@empresa.com"
              />
            </FormField>
            <FormField label="Nombre completo" required>
              <input
                type="text"
                value={createForm.display_name}
                onChange={(e) => setCreateForm((p) => ({ ...p, display_name: e.target.value }))}
                className={inputCls}
                placeholder="Nombre Apellido"
              />
            </FormField>
            <FormField label="Contraseña" required>
              <input
                type="password"
                value={createForm.password}
                onChange={(e) => setCreateForm((p) => ({ ...p, password: e.target.value }))}
                className={inputCls}
                placeholder="••••••••"
              />
            </FormField>
            <FormField label="Rol" required>
              <select
                value={createForm.role_id}
                onChange={(e) => setCreateForm((p) => ({ ...p, role_id: e.target.value === '' ? '' : Number(e.target.value) }))}
                className={inputCls}
              >
                <option value="">Seleccionar rol…</option>
                {roles.map((r) => (
                  <option key={r.id} value={r.id}>{r.name}{r.is_base_role ? ' (base)' : ''}</option>
                ))}
              </select>
            </FormField>
            {createError && <p className="text-sm text-red-600 dark:text-red-400">{createError}</p>}
          </div>
          <div className="mt-5 flex justify-end gap-3">
            <button type="button" onClick={() => setShowCreate(false)} className={cancelBtnCls}>Cancelar</button>
            <button
              type="button"
              onClick={handleCreate}
              disabled={creating || !createForm.email || !createForm.display_name || !createForm.password || createForm.role_id === ''}
              className={primaryBtnCls}
            >
              {creating ? 'Creando…' : 'Crear Usuario'}
            </button>
          </div>
        </ModalOverlay>
      )}

      {/* Modal: Editar usuario */}
      {editUser && (
        <ModalOverlay onClose={() => setEditUser(null)}>
          <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Editar Usuario</h2>
          <p className="mb-3 text-sm text-gray-500 dark:text-slate-400">{editUser.username}</p>
          <div className="space-y-3">
            <FormField label="Nombre completo">
              <input
                type="text"
                value={editForm.display_name}
                onChange={(e) => setEditForm((p) => ({ ...p, display_name: e.target.value }))}
                className={inputCls}
              />
            </FormField>
            {isSysAdmin && (
              <FormField label="Rol">
                <select
                  value={editForm.role_id}
                  onChange={(e) => setEditForm((p) => ({ ...p, role_id: e.target.value === '' ? '' : Number(e.target.value) }))}
                  className={inputCls}
                >
                  <option value="">Sin cambio</option>
                  {roles.map((r) => (
                    <option key={r.id} value={r.id}>{r.name}{r.is_base_role ? ' (base)' : ''}</option>
                  ))}
                </select>
              </FormField>
            )}
            {editError && <p className="text-sm text-red-600 dark:text-red-400">{editError}</p>}
          </div>
          <div className="mt-5 flex justify-end gap-3">
            <button type="button" onClick={() => setEditUser(null)} className={cancelBtnCls}>Cancelar</button>
            <button type="button" onClick={handleEdit} disabled={saving} className={primaryBtnCls}>
              {saving ? 'Guardando…' : 'Guardar'}
            </button>
          </div>
        </ModalOverlay>
      )}

      {/* Modal: Resetear contraseña */}
      {resetUser && (
        <ModalOverlay onClose={() => setResetUser(null)}>
          <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Resetear Contraseña</h2>
          <p className="mb-3 text-sm text-gray-500 dark:text-slate-400">{resetUser.display_name} ({resetUser.username})</p>
          <div className="space-y-3">
            <FormField label="Nueva contraseña" required>
              <input
                type="password"
                value={resetPw.new_password}
                onChange={(e) => setResetPw((p) => ({ ...p, new_password: e.target.value }))}
                className={inputCls}
                placeholder="••••••••"
              />
            </FormField>
            <FormField label="Confirmar contraseña" required>
              <input
                type="password"
                value={resetPw.confirm}
                onChange={(e) => setResetPw((p) => ({ ...p, confirm: e.target.value }))}
                className={inputCls}
                placeholder="••••••••"
              />
            </FormField>
            {resetError && <p className="text-sm text-red-600 dark:text-red-400">{resetError}</p>}
          </div>
          <div className="mt-5 flex justify-end gap-3">
            <button type="button" onClick={() => setResetUser(null)} className={cancelBtnCls}>Cancelar</button>
            <button
              type="button"
              onClick={handleReset}
              disabled={resetting || !resetPw.new_password}
              className={primaryBtnCls}
            >
              {resetting ? 'Reseteando…' : 'Resetear'}
            </button>
          </div>
        </ModalOverlay>
      )}

      {/* Modal: Confirmar eliminar */}
      {deleteUser && (
        <ModalOverlay onClose={() => setDeleteUser(null)}>
          <h2 className="mb-3 text-lg font-semibold text-gray-900 dark:text-white">Eliminar Usuario</h2>
          <p className="text-sm text-gray-600 dark:text-slate-300">
            ¿Estás seguro de que quieres eliminar a{' '}
            <strong>{deleteUser.display_name}</strong> ({deleteUser.username})?
            Esta acción eliminará también sus dashboards y consultas guardadas.
          </p>
          <div className="mt-5 flex justify-end gap-3">
            <button type="button" onClick={() => setDeleteUser(null)} className={cancelBtnCls}>Cancelar</button>
            <button
              type="button"
              onClick={handleDelete}
              disabled={deleting}
              className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-red-700 disabled:opacity-50"
            >
              {deleting ? 'Eliminando…' : 'Eliminar'}
            </button>
          </div>
        </ModalOverlay>
      )}
    </div>
  )
}

// ---- Helpers de UI ----
const inputCls =
  'w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 transition focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:border-slate-600 dark:bg-slate-700 dark:text-white dark:focus:border-blue-400'
const primaryBtnCls =
  'rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-50'
const cancelBtnCls =
  'rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm text-gray-700 transition hover:bg-gray-50 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200'

function FormField({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-gray-700 dark:text-slate-300">
        {label}{required && <span className="ml-0.5 text-red-500">*</span>}
      </label>
      {children}
    </div>
  )
}

function ModalOverlay({ onClose, children }: { onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm">
      <div
        className="w-full max-w-md rounded-2xl border border-gray-200 bg-white p-6 shadow-2xl dark:border-slate-700 dark:bg-slate-800"
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  )
}

'use client'

import { useEffect, useState } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'
import { apiClient } from '@/services/api'
import { AppBreadcrumb } from '@/components/AppBreadcrumb'
import type { DwhAgency, RoleAgencyPermission, PlatformRole } from '@/types'
import { getApiErrorMessage } from '@/lib/apiError'

const DWH_OBJECTS: { key: string; label: string }[] = [
  { key: 'h_agencies', label: 'Agencias (h_agencies)' },
  { key: 'h_customers', label: 'Clientes (h_customers)' },
  { key: 'h_inventory', label: 'Inventario (h_inventory)' },
  { key: 'h_invoices', label: 'Facturas / Ventas (h_invoices)' },
  { key: 'h_orders', label: 'Órdenes (h_orders)' },
  { key: 'h_services', label: 'Servicios (h_services)' },
  { key: 'h_customer_vehicle', label: 'Vehículos por cliente (h_customer_vehicle)' },
]

interface AgencyPerm extends RoleAgencyPermission {
  expanded: boolean
}

interface FormState {
  name: string
  description: string
  can_create_users: boolean
  can_access_config: boolean
  all_agencies: boolean
  agencies: AgencyPerm[]
}

export default function RoleEditorPage() {
  const router = useRouter()
  const { id } = useParams<{ id: string }>()
  const isNew = id === 'new'

  const { user, isAuthenticated } = useAuth()
  const [dwhAgencies, setDwhAgencies] = useState<DwhAgency[]>([])
  const [loadingData, setLoadingData] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const [form, setForm] = useState<FormState>({
    name: '',
    description: '',
    can_create_users: false,
    can_access_config: false,
    all_agencies: false,
    agencies: [],
  })

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
    loadInitialData()
  }, [isAuthenticated])

  async function loadInitialData() {
    setLoadingData(true)
    setError(null)
    try {
      const [agencies, roleData] = await Promise.all([
        apiClient.getAdminAgencies(),
        isNew ? Promise.resolve(null) : apiClient.getAdminRole(Number(id)),
      ])
      setDwhAgencies(agencies)

      if (roleData) {
        setForm({
          name: roleData.name,
          description: roleData.description,
          can_create_users: roleData.can_create_users,
          can_access_config: roleData.can_access_config,
          all_agencies: roleData.all_agencies,
          agencies: (roleData.agencies ?? []).map((a) => ({ ...a, expanded: false })),
        })
      }
    } catch (e) {
      setError(getApiErrorMessage(e, 'No se pudieron cargar los datos'))
    } finally {
      setLoadingData(false)
    }
  }

  function toggleAgency(id_agency: string) {
    setForm((prev) => {
      const existing = prev.agencies.find((a) => a.id_agency === id_agency)
      if (existing) {
        return { ...prev, agencies: prev.agencies.filter((a) => a.id_agency !== id_agency) }
      }
      return {
        ...prev,
        agencies: [
          ...prev.agencies,
          { id_agency, all_objects: true, objects: [], expanded: true },
        ],
      }
    })
  }

  function setAgencyAllObjects(id_agency: string, value: boolean) {
    setForm((prev) => ({
      ...prev,
      agencies: prev.agencies.map((a) =>
        a.id_agency === id_agency ? { ...a, all_objects: value, objects: value ? [] : a.objects } : a
      ),
    }))
  }

  function toggleObject(id_agency: string, obj: string) {
    setForm((prev) => ({
      ...prev,
      agencies: prev.agencies.map((a) => {
        if (a.id_agency !== id_agency) return a
        const has = a.objects.includes(obj)
        return { ...a, objects: has ? a.objects.filter((o) => o !== obj) : [...a.objects, obj] }
      }),
    }))
  }

  function toggleExpand(id_agency: string) {
    setForm((prev) => ({
      ...prev,
      agencies: prev.agencies.map((a) =>
        a.id_agency === id_agency ? { ...a, expanded: !a.expanded } : a
      ),
    }))
  }

  async function handleSave() {
    if (!form.name.trim()) {
      setSaveError('El nombre del rol es requerido')
      return
    }
    setSaving(true)
    setSaveError(null)
    const payload = {
      name: form.name.trim(),
      description: form.description.trim(),
      can_create_users: form.can_create_users,
      can_access_config: form.can_access_config,
      all_agencies: form.all_agencies,
      agencies: form.all_agencies
        ? []
        : form.agencies.map(({ id_agency, all_objects, objects }) => ({
            id_agency,
            all_objects,
            objects,
          })),
    }
    try {
      if (isNew) {
        await apiClient.createAdminRole(payload)
      } else {
        await apiClient.updateAdminRole(Number(id), payload)
      }
      router.push('/admin/roles')
    } catch (e) {
      setSaveError(getApiErrorMessage(e, 'Error al guardar el rol'))
    } finally {
      setSaving(false)
    }
  }

  if (!isAuthenticated || !isSysAdmin) return null

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-900">
      <header className="border-b border-gray-200 bg-white dark:border-slate-700 dark:bg-slate-800">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <div>
            <AppBreadcrumb
              items={[
                { label: 'Dashboard', href: '/dashboard' },
                { label: 'Roles', href: '/admin/roles' },
                { label: isNew ? 'Nuevo Rol' : 'Editar Rol' },
              ]}
            />
            <h1 className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">
              {isNew ? 'Nuevo Rol' : 'Editar Rol'}
            </h1>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-6 sm:px-6">
        {loadingData ? (
          <div className="py-12 text-center text-gray-400">Cargando…</div>
        ) : error ? (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
            {error}
          </div>
        ) : (
          <div className="space-y-6">
            {/* Datos básicos */}
            <Section title="Datos del rol">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="sm:col-span-2">
                  <label className={labelCls}>Nombre del rol <Required /></label>
                  <input
                    type="text"
                    value={form.name}
                    onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                    className={inputCls}
                    placeholder="Ej: Gerente Geely, Supervisor Servicios…"
                  />
                </div>
                <div className="sm:col-span-2">
                  <label className={labelCls}>Descripción</label>
                  <input
                    type="text"
                    value={form.description}
                    onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
                    className={inputCls}
                    placeholder="Breve descripción del rol"
                  />
                </div>
              </div>
            </Section>

            {/* Permisos del sistema */}
            <Section title="Permisos del sistema">
              <div className="space-y-3">
                <Checkbox
                  checked={form.can_create_users}
                  onChange={(v) => setForm((p) => ({ ...p, can_create_users: v }))}
                  label="Puede crear y editar usuarios"
                  description="El usuario con este rol podrá acceder a la gestión de usuarios y dar de alta nuevas cuentas."
                />
                <Checkbox
                  checked={form.can_access_config}
                  onChange={(v) => setForm((p) => ({ ...p, can_access_config: v }))}
                  label="Puede acceder a Configuración"
                  description="Permite acceder a la sección de configuración del sistema."
                />
              </div>
            </Section>

            {/* Permisos de agencias */}
            <Section title="Acceso a agencias y datos">
              <div className="space-y-4">
                <Checkbox
                  checked={form.all_agencies}
                  onChange={(v) => setForm((p) => ({ ...p, all_agencies: v, agencies: v ? [] : p.agencies }))}
                  label="Acceso a todas las agencias"
                  description="El rol puede consultar datos de cualquier agencia del grupo sin restricción."
                />

                {!form.all_agencies && (
                  <div className="rounded-xl border border-gray-200 bg-white dark:border-slate-700 dark:bg-slate-800">
                    <div className="border-b border-gray-100 px-4 py-3 dark:border-slate-700">
                      <p className="text-sm font-medium text-gray-700 dark:text-slate-200">
                        Selecciona las agencias a las que tendrá acceso este rol
                      </p>
                      <p className="mt-0.5 text-xs text-gray-400 dark:text-slate-500">
                        Por cada agencia podrás elegir a qué tablas del DWH puede acceder.
                      </p>
                    </div>

                    {dwhAgencies.length === 0 ? (
                      <div className="px-4 py-4 text-sm text-gray-400">
                        No se pudieron cargar las agencias del DWH.
                      </div>
                    ) : (
                      <ul className="divide-y divide-gray-100 dark:divide-slate-700">
                        {dwhAgencies.map((agency) => {
                          const perm = form.agencies.find((a) => a.id_agency === agency.id_agency)
                          const selected = !!perm
                          return (
                            <li key={agency.id_agency}>
                              <div className="flex items-center gap-3 px-4 py-3">
                                <input
                                  type="checkbox"
                                  id={`agency-${agency.id_agency}`}
                                  checked={selected}
                                  onChange={() => toggleAgency(agency.id_agency)}
                                  className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                                />
                                <label
                                  htmlFor={`agency-${agency.id_agency}`}
                                  className="flex-1 cursor-pointer text-sm font-medium text-gray-800 dark:text-slate-200"
                                >
                                  {agency.name}
                                  <span className="ml-2 text-xs text-gray-400 dark:text-slate-500">
                                    {agency.id_agency}
                                  </span>
                                </label>
                                {selected && (
                                  <button
                                    type="button"
                                    onClick={() => toggleExpand(agency.id_agency)}
                                    className="text-xs text-blue-600 transition hover:text-blue-700 dark:text-blue-400"
                                  >
                                    {perm!.expanded ? 'Ocultar ▲' : 'Ver objetos ▼'}
                                  </button>
                                )}
                              </div>

                              {/* Object permissions for this agency */}
                              {selected && perm!.expanded && (
                                <div className="border-t border-gray-100 bg-gray-50 px-8 py-3 dark:border-slate-700 dark:bg-slate-800/50">
                                  <Checkbox
                                    checked={perm!.all_objects}
                                    onChange={(v) => setAgencyAllObjects(agency.id_agency, v)}
                                    label="Acceso a todos los objetos DWH de esta agencia"
                                    description=""
                                  />
                                  {!perm!.all_objects && (
                                    <div className="mt-3 space-y-2">
                                      <p className="text-xs font-medium text-gray-600 dark:text-slate-400">
                                        Selecciona las tablas/vistas permitidas:
                                      </p>
                                      {DWH_OBJECTS.map((obj) => (
                                        <label
                                          key={obj.key}
                                          className="flex cursor-pointer items-center gap-2 text-sm text-gray-700 dark:text-slate-300"
                                        >
                                          <input
                                            type="checkbox"
                                            checked={perm!.objects.includes(obj.key)}
                                            onChange={() => toggleObject(agency.id_agency, obj.key)}
                                            className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                                          />
                                          {obj.label}
                                        </label>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              )}
                            </li>
                          )
                        })}
                      </ul>
                    )}

                    {form.agencies.length > 0 && (
                      <div className="border-t border-gray-100 px-4 py-2 dark:border-slate-700">
                        <p className="text-xs text-gray-500 dark:text-slate-400">
                          {form.agencies.length} agencia{form.agencies.length !== 1 ? 's' : ''} seleccionada{form.agencies.length !== 1 ? 's' : ''}
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </Section>

            {/* Save button */}
            {saveError && (
              <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
                {saveError}
              </div>
            )}
            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => router.push('/admin/roles')}
                className="rounded-lg border border-gray-200 bg-white px-5 py-2.5 text-sm text-gray-700 transition hover:bg-gray-50 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={saving}
                className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
              >
                {saving ? 'Guardando…' : isNew ? 'Crear Rol' : 'Guardar Cambios'}
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

// ---- UI helpers ----
const labelCls = 'mb-1 block text-xs font-medium text-gray-700 dark:text-slate-300'
const inputCls =
  'w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 transition focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:border-slate-600 dark:bg-slate-700 dark:text-white dark:focus:border-blue-400'

function Required() {
  return <span className="ml-0.5 text-red-500">*</span>
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-800">
      <h2 className="mb-4 text-sm font-semibold text-gray-900 dark:text-white">{title}</h2>
      {children}
    </div>
  )
}

function Checkbox({
  checked,
  onChange,
  label,
  description,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label: string
  description: string
}) {
  return (
    <label className="flex cursor-pointer items-start gap-3">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
      />
      <div>
        <span className="text-sm font-medium text-gray-800 dark:text-slate-200">{label}</span>
        {description && <p className="mt-0.5 text-xs text-gray-500 dark:text-slate-400">{description}</p>}
      </div>
    </label>
  )
}

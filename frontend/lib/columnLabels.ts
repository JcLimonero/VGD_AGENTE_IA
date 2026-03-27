/**
 * Etiquetas en español para cabeceras de tabla, leyendas y CSV.
 * Debe alinearse con `agente_dwh/column_labels.py`; si la API envía
 * `column_labels_es`, preferir ese mapa vía `columnHeaderLabel`.
 */

const SPANISH_BY_ALIAS: Record<string, string> = {
  agency_name: 'Nombre de agencia',
  name: 'Nombre',
  sales_count: 'Número de ventas',
  total_ventas: 'Total de ventas',
  total_sales: 'Total de ventas',
  ventas: 'Ventas',
  count: 'Cantidad',
  cnt: 'Cantidad',
  n: 'Cantidad',
  total: 'Total',
  month: 'Mes',
  mes: 'Mes',
  year: 'Año',
  año: 'Año',
  billing_date: 'Fecha de facturación',
  sale_date: 'Fecha de venta',
  service_date: 'Fecha de servicio',
  created_at: 'Fecha de creación',
  updated_at: 'Fecha de actualización',
  state: 'Estado',
  status: 'Estado',
  vin: 'VIN',
  brand: 'Marca',
  model: 'Modelo',
  version: 'Versión',
  amount: 'Importe',
  km: 'Kilometraje',
  order_dms: 'Pedido DMS',
  nd_client_dms: 'Cliente DMS',
  id_agency: 'ID agencia',
  bussines_name: 'Nombre del cliente',
  business_name: 'Nombre del cliente',
  customer_name: 'Nombre del cliente',
  service_type: 'Tipo de servicio',
  exterior_color: 'Color exterior',
  interior_color: 'Color interior',
  exterior_color_name: 'Color exterior',
  interior_color_name: 'Color interior',
  stage_name: 'Etapa',
  test: 'Prueba',
  value: 'Valor',
}

const TOKEN_ES: [string, string][] = [
  ['agency', 'agencia'],
  ['sales', 'ventas'],
  ['billing', 'facturación'],
  ['customer', 'cliente'],
  ['service', 'servicio'],
  ['invoice', 'factura'],
  ['inventory', 'inventario'],
  ['vehicle', 'vehículo'],
  ['count', 'conteo'],
  ['total', 'total'],
  ['name', 'nombre'],
  ['date', 'fecha'],
  ['time', 'hora'],
  ['month', 'mes'],
  ['year', 'año'],
  ['brand', 'marca'],
  ['model', 'modelo'],
  ['amount', 'importe'],
  ['price', 'precio'],
  ['order', 'pedido'],
  ['state', 'estado'],
  ['status', 'estado'],
  ['type', 'tipo'],
  ['id', 'id'],
]

export function spanishColumnLabel(key: string): string {
  if (!key || !String(key).trim()) return key
  const k = String(key).trim()
  const lower = k.toLowerCase()
  if (lower in SPANISH_BY_ALIAS) return SPANISH_BY_ALIAS[lower]

  const parts = lower.split('_').filter(Boolean)
  const out: string[] = []
  for (const p of parts) {
    const pl = p.toLowerCase()
    const hit = TOKEN_ES.find(([en]) => en === pl)
    out.push(hit ? hit[1] : p)
  }
  if (out.length === 0) return k
  const label = out.join(' ')
  return label.length > 1 ? label[0]!.toUpperCase() + label.slice(1) : label.toUpperCase()
}

export function columnHeaderLabel(col: string, labelsEs?: Record<string, string>): string {
  const fromApi = labelsEs?.[col]
  if (fromApi && fromApi.trim()) return fromApi
  return spanishColumnLabel(col)
}

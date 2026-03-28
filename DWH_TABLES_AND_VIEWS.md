# DWH — Tablas y Vistas Principales

Este documento describe las tablas y vistas que usamos en el DWH `dwh` (esquema `public`), con su propósito, columnas clave y reglas de combinación.

## Convenciones generales

- Las tablas base del origen usan nombres `camelCase` / `snake_case` según la extracción.
- Las vistas homologadas que usa el agente empiezan con `h_` y tienen columnas en snake_case.
- Las columnas de relación más importantes son:
  - `id_agency` → agencia
  - `nd_client_dms` → cliente
  - `order_dms` → pedido / factura
  - `vin` → vehículo
- Todas las consultas deben usar únicamente las tablas/vistas y columnas listadas en este repositorio.

---

## Vistas homologadas

### `h_agencies`
- Tipo: VIEW
- Filas estimadas: ~20
- Propósito: catálogo de agencias del grupo.
- Claves y columnas principales:
  - `id`
  - `id_agency`
  - `name`
  - `is_active`
- Uso típico: obtener nombre de agencia en cualquier informe de ventas, servicios o clientes.
- Join estándar:
  - `JOIN h_agencies a ON tabla.id_agency = a.id_agency`

### `h_customers`
- Tipo: VIEW
- Filas estimadas: ~154691
- Propósito: datos maestros de clientes.
- Clave compuesta: `nd_client_dms + id_agency`.
- Columnas útiles:
  - `bussines_name`
  - `name`, `paternal_surname`, `maternal_surname`
  - `mail`, `mobile_phone`, `phone`
  - `city`, `state`
- Uso típico: obtener información del cliente asociado a un pedido o para segmentaciones por agencia.
- Join estándar:
  - `JOIN h_customers c ON c.nd_client_dms = o.nd_client_dms AND c.id_agency = o.id_agency`

### `h_inventory`
- Tipo: VIEW
- Filas estimadas: ~141132
- Propósito: catálogo maestro de unidades / vehículos.
- Columnas clave:
  - `vin`
  - `id_agency`
  - `brand`, `model`, `version`, `year`
  - `external_color`, `internal_color`
  - `status`, `amount`, `km`
- Uso típico: sumar datos de vehículo a facturas, servicios o vehículos de cliente.
- Join estándar:
  - `JOIN h_inventory inv ON tabla.vin = inv.vin`
- Nota importante: no usar `h_inventory` para consultas de conteo de ventas cuando `h_invoices` ya responde la pregunta.

### `h_invoices`
- Tipo: VIEW
- Filas estimadas: ~62757
- Propósito: registro de ventas efectivas.
- Filtro obligatorio para ventas válidas:
  - `state IN ('Vendido', 'Facturacion del vehiculo')`
- Columnas útiles:
  - `id_agency`, `order_dms`, `vin`
  - `billing_date`, `amount`, `state`
- Regla clave:
  - No tiene `nd_client_dms`. Para cliente usar `h_orders`.
- Uso típico:
  - Conteos y montos de ventas.
  - Reporting por agencia.
- Joins permitidos:
  - `JOIN h_agencies a ON h_invoices.id_agency = a.id_agency`
  - `JOIN h_inventory inv ON h_invoices.vin = inv.vin`
  - `JOIN h_orders o ON h_invoices.order_dms = o.order_dms` cuando se necesita información de cliente o proceso de venta.

### `h_orders`
- Tipo: VIEW
- Filas estimadas: ~70532
- Propósito: movimientos y detalles del proceso de venta.
- Columnas clave:
  - `order_dms`
  - `nd_client_dms`
  - `id_agency`
  - `vin`
  - `brand`, `model`, `version`, `year`
- Uso típico: conectar ventas con clientes.
- Join principales:
  - `JOIN h_invoices i ON i.order_dms = h_orders.order_dms`
  - `JOIN h_customers c ON c.nd_client_dms = h_orders.nd_client_dms AND c.id_agency = h_orders.id_agency`

### `h_services`
- Tipo: VIEW
- Filas estimadas: ~286885
- Propósito: servicios realizados a unidades.
- Columnas clave:
  - `id_agency`
  - `vin`
  - `order_dms` (folio de servicio, no es `h_orders.order_dms`)
- Uso típico: consultar historial de servicio por VIN o agencia.
- Joins permitidos:
  - `JOIN h_agencies a ON h_services.id_agency = a.id_agency`
  - `JOIN h_inventory inv ON h_services.vin = inv.vin`
- Regla clave:
  - `order_dms` en `h_services` es folio de servicio y no se debe unir con `h_orders.order_dms`.

### `h_customer_vehicle`
- Tipo: VIEW
- Filas estimadas: ~124638
- Propósito: autos asociados a cada cliente.
- Columnas clave:
  - `nd_client_dms`
  - `id_agency`
  - `vin`
- Uso típico: listar vehículos por cliente o validar unidades de cliente.
- Joins estándar:
  - `JOIN h_customers c ON c.nd_client_dms = h_customer_vehicle.nd_client_dms AND c.id_agency = h_customer_vehicle.id_agency`
  - `JOIN h_inventory inv ON h_customer_vehicle.vin = inv.vin`

---

## Tablas base principales

Estas tablas existen en el origen y sirven como base para las vistas homologadas `h_*`.

### `agencies`
- Catálogo base de agencias.
- Columnas: `id`, `idAgency`, `name`, `isActive`, `created_at`, `updated_at`.

### `customers`
- Base de clientes.
- Columnas clave: `idAgency`, `ndClientDMS`, `name`, `bussines_name`, `mail`, `mobile_phone`, `city`, `state`, `last_sale`, `timestamp`.

### `customer_vehicle`
- Base de vehículos que pertenecen a clientes.
- Columnas clave: `idAgency`, `ndClientDMS`, `vin`, `brand`, `model`, `year`, `plates`, `external_color`, `internal_color`.

### `customer_contact` y `customer_action`
- Estas tablas están disponibles en el esquema de origen y pueden contener detalles adicionales de contacto y actividad del cliente.
- No son las fuentes de datos principales del agente actual, pero pueden complementar análisis de clientes.

---

## Reglas de uso rápido

- Para ventas totales y montos: usa siempre `h_invoices`.
- Para nombre de agencia en ventas: une `h_agencies` por `id_agency`.
- Para datos de cliente en venta: cruza `h_invoices` → `h_orders` → `h_customers`.
- Para datos de la unidad en venta: une `h_invoices` → `h_inventory`.
- Para servicios de unidad: usa `h_services` y no mezcles su `order_dms` con `h_orders`.
- Para vehículos de cliente: usa `h_customer_vehicle` + `h_customers` + `h_inventory`.

---

## Uso recomendado para SQL

- `COUNT(*)` en `h_invoices` para total de ventas.
- Agregar un `WHERE state IN ('Vendido', 'Facturacion del vehiculo')` siempre que se consulte `h_invoices`.
- Evitar joins innecesarios.
- No usar tablas inexistentes: `sales`, `vehicles`, `service_appointments`, `insurance_policies`, `mv_sales_monthly`.

---

## Dónde encontrar el detalle de columnas

- `schema_hint_dwh.txt`: contiene el esquema completo y las reglas fijas de negocio para el agente.
- `dwh_schema_catalog.json`: exportación del catálogo de la base `dwh` con columnas y tipos.

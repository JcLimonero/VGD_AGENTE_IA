"""Respuestas directas para preguntas comunes que no requieren consulta a BD."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class DirectResponse:
    """Respuesta directa sin SQL."""

    name: str
    answer: str


# ---------------------------------------------------------------------------
# Categorías de respuestas
# ---------------------------------------------------------------------------

_COMMON_RESPONSES: list[tuple[list[str], DirectResponse]] = [
    # ── 1. Saludos y despedidas ──────────────────────────────────────────
    (
        [
            r"(?i)^(hola|hey|buenas|buenos\s+d[ií]as|buenas\s+tardes|buenas\s+noches|qu[eé]\s+tal|qu[eé]\s+onda|saludos)\s*[!.?]*$",
            r"(?i)^(hi|hello|good\s+morning|good\s+afternoon|good\s+evening)\s*[!.?]*$",
        ],
        DirectResponse(
            name="greeting",
            answer="¡Hola! Soy **Nex IA**, tu asistente de inteligencia comercial. ¿En qué puedo ayudarte hoy?",
        ),
    ),
    (
        [
            r"(?i)^(adi[oó]s|hasta\s+luego|nos\s+vemos|bye|chao|chau|hasta\s+pronto|hasta\s+ma[nñ]ana)\s*[!.?]*$",
        ],
        DirectResponse(
            name="farewell",
            answer="¡Hasta luego! Si necesitas algo más, aquí estaré. 👋",
        ),
    ),
    (
        [
            r"(?i)^(gracias|muchas\s+gracias|te\s+agradezco|thanks|thank\s+you|thx)\s*[!.?]*$",
        ],
        DirectResponse(
            name="thanks",
            answer="¡De nada! Si tienes más preguntas, no dudes en consultarme.",
        ),
    ),

    # ── 2. Identidad del asistente ───────────────────────────────────────
    (
        [
            r"(?i)(qui[eé]n|que)\s+eres",
            r"(?i)c[oó]mo\s+te\s+llamas",
            r"(?i)cu[aá]l\s+es\s+tu\s+nombre",
            r"(?i)eres\s+un\s+(bot|robot|ia|asistente)",
        ],
        DirectResponse(
            name="identity",
            answer=(
                "Soy **Nex IA**, un asistente de inteligencia comercial. "
                "Puedo ayudarte a consultar información de ventas, servicios, clientes, "
                "vehículos, órdenes, pólizas y más desde tu base de datos."
            ),
        ),
    ),
    (
        [
            r"(?i)qu[eé]\s+puedes\s+hacer",
            r"(?i)qu[eé]\s+sabes\s+hacer",
            r"(?i)para\s+qu[eé]\s+sirves",
            r"(?i)cu[aá]les\s+son\s+tus\s+funciones",
            r"(?i)qu[eé]\s+funciones\s+tienes",
            r"(?i)en\s+qu[eé]\s+me\s+puedes\s+ayudar",
        ],
        DirectResponse(
            name="capabilities",
            answer=(
                "Puedo ayudarte con:\n"
                "- **Ventas**: consultar facturas, tendencias de venta, comparativos por agencia o período.\n"
                "- **Clientes**: buscar información de clientes, historial de compras, frecuencia de recompra.\n"
                "- **Vehículos**: consultar inventario, propiedad de vehículos, historial por VIN.\n"
                "- **Servicios**: citas de servicio, tipos de servicio, historial de mantenimiento.\n"
                "- **Órdenes**: seguimiento de órdenes, estados, tiempos de entrega.\n"
                "- **Pólizas**: información de seguros y pólizas asociadas.\n"
                "- **KPIs**: métricas clave como tiempo promedio de recompra.\n\n"
                "Simplemente hazme una pregunta en lenguaje natural y yo genero la consulta por ti."
            ),
        ),
    ),

    # ── 3. Cómo usar el sistema ──────────────────────────────────────────
    (
        [
            r"(?i)c[oó]mo\s+(te\s+)?us[oa]",
            r"(?i)c[oó]mo\s+funciona(s)?",
            r"(?i)c[oó]mo\s+hago\s+(una\s+)?consulta",
            r"(?i)c[oó]mo\s+(le\s+)?pregunto",
        ],
        DirectResponse(
            name="how_to_use",
            answer=(
                "Es muy sencillo:\n"
                "1. Escribe tu pregunta en lenguaje natural (ej: *¿Cuántos autos se vendieron en enero?*).\n"
                "2. Yo genero la consulta SQL automáticamente y la ejecuto.\n"
                "3. Te muestro los resultados con un resumen, gráficas y tabla de datos.\n\n"
                "**Tips:**\n"
                "- Sé específico con fechas y filtros para mejores resultados.\n"
                "- Puedes hacer preguntas de seguimiento sobre los mismos datos.\n"
                "- Si ves un vehículo o agencia en los resultados, puedes hacer clic para profundizar."
            ),
        ),
    ),
    (
        [
            r"(?i)qu[eé]\s+tipo\s+de\s+preguntas",
            r"(?i)qu[eé]\s+puedo\s+preguntar",
            r"(?i)qu[eé]\s+consultas\s+puedo\s+hacer",
            r"(?i)dame\s+(un\s+)?ejemplo",
            r"(?i)ejemplos?\s+de\s+(preguntas?|consultas?)",
        ],
        DirectResponse(
            name="example_questions",
            answer=(
                "Aquí tienes algunos ejemplos de preguntas que puedo responder:\n\n"
                "**Ventas:**\n"
                "- ¿Cuántas unidades se vendieron en el último mes?\n"
                "- ¿Cuál es el top 10 de agencias por ventas?\n"
                "- Comparativo de ventas enero vs febrero 2025\n\n"
                "**Clientes:**\n"
                "- ¿Cuántos clientes nuevos tuvimos este año?\n"
                "- ¿Cuál es el tiempo promedio de recompra?\n"
                "- Buscar al cliente Juan Pérez\n\n"
                "**Servicios:**\n"
                "- ¿Cuántas citas de servicio hay programadas?\n"
                "- ¿Cuáles son los servicios de mantenimiento más solicitados?\n\n"
                "**Vehículos:**\n"
                "- ¿Qué vehículos tiene el cliente X?\n"
                "- Historial del VIN ABC123"
            ),
        ),
    ),

    # ── 4. Información del sistema / técnicas ────────────────────────────
    (
        [
            r"(?i)qu[eé]\s+base\s+de\s+datos\s+us[ao]s",
            r"(?i)qu[eé]\s+motor\s+de\s+base\s+de\s+datos",
            r"(?i)qu[eé]\s+bd\s+us[ao]s",
        ],
        DirectResponse(
            name="database_info",
            answer=(
                "Trabajo conectado a una base de datos PostgreSQL que contiene las vistas homologadas "
                "del DWH (Data Warehouse). Las principales tablas/vistas disponibles son: "
                "h_invoices, h_orders, h_customers, h_customer_vehicle, h_services, "
                "h_service_appointments, h_agencies, h_insurance_policies, entre otras."
            ),
        ),
    ),
    (
        [
            r"(?i)qu[eé]\s+tablas\s+(hay|tienes|existen|est[aá]n)",
            r"(?i)(cu[aá]les|lista)\s+(son\s+)?las\s+tablas",
            r"(?i)mu[eé]strame\s+las\s+tablas",
        ],
        DirectResponse(
            name="tables_list",
            answer=(
                "Las principales vistas/tablas disponibles en el DWH son:\n\n"
                "| Vista | Descripción |\n"
                "|-------|-------------|\n"
                "| **h_invoices** | Facturas de venta |\n"
                "| **h_orders** | Órdenes de venta |\n"
                "| **h_customers** | Clientes |\n"
                "| **h_customer_vehicle** | Relación cliente-vehículo (propiedad) |\n"
                "| **h_services** | Servicios realizados |\n"
                "| **h_service_appointments** | Citas de servicio |\n"
                "| **h_agencies** | Agencias/sucursales |\n"
                "| **h_insurance_policies** | Pólizas de seguro |\n\n"
                "Si necesitas saber las columnas de alguna tabla, pregúntame."
            ),
        ),
    ),
    (
        [
            r"(?i)qu[eé]\s+(es|significa)\s+(el\s+)?dwh",
            r"(?i)qu[eé]\s+(es|significa)\s+data\s*warehouse",
        ],
        DirectResponse(
            name="what_is_dwh",
            answer=(
                "**DWH (Data Warehouse)** es un almacén de datos centralizado que consolida "
                "información de múltiples fuentes (DMS, CRM, servicios, etc.) en un solo lugar. "
                "Las vistas homologadas (prefijo `h_`) estandarizan los datos para facilitar su consulta y análisis."
            ),
        ),
    ),

    # ── 5. Preguntas sobre datos específicos ─────────────────────────────
    (
        [
            r"(?i)qu[eé]\s+(es|significa)\s+(?:un|el)?\s*vin\b",
            r"(?i)qu[eé]\s+es\s+el\s+n[uú]mero\s+de\s+vin",
        ],
        DirectResponse(
            name="what_is_vin",
            answer=(
                "El **VIN** (Vehicle Identification Number) es un código único de 17 caracteres "
                "que identifica a cada vehículo de manera individual. Es como la \"huella digital\" del auto. "
                "Se usa en el sistema para rastrear historial de ventas, servicios y propiedad."
            ),
        ),
    ),
    (
        [
            r"(?i)qu[eé]\s+(es|significa)\s+(el\s+)?dms\b",
        ],
        DirectResponse(
            name="what_is_dms",
            answer=(
                "**DMS** (Dealer Management System) es el sistema de gestión del concesionario. "
                "Es la fuente principal de datos operativos como ventas, facturación, inventario y servicios. "
                "Los campos con sufijo `_dms` indican que provienen de este sistema."
            ),
        ),
    ),
    (
        [
            r"(?i)qu[eé]\s+(es|significa)\s+nd_client_dms",
        ],
        DirectResponse(
            name="what_is_nd_client_dms",
            answer=(
                "**nd_client_dms** es el número de cliente asignado en el DMS (sistema del concesionario). "
                "Es el identificador único de cada cliente y se usa para relacionar las tablas de "
                "clientes, vehículos, facturas y órdenes."
            ),
        ),
    ),
    (
        [
            r"(?i)qu[eé]\s+(es|significa)\s+(una\s+)?factura",
            r"(?i)qu[eé]\s+(es|significa)\s+h_invoices",
        ],
        DirectResponse(
            name="what_is_invoice",
            answer=(
                "**h_invoices** contiene las facturas de venta de vehículos. "
                "Cada registro representa una venta completada e incluye datos como: "
                "fecha de facturación (billing_date), VIN del vehículo, monto, agencia, "
                "y referencia al cliente. Es la tabla principal para analizar **compras/ventas**."
            ),
        ),
    ),
    (
        [
            r"(?i)qu[eé]\s+(es|significa)\s+(una\s+)?orden",
            r"(?i)qu[eé]\s+(es|significa)\s+h_orders",
            r"(?i)diferencia\s+entre\s+orden(es)?\s+y\s+factura",
            r"(?i)diferencia\s+entre\s+factura(s)?\s+y\s+orden",
        ],
        DirectResponse(
            name="what_is_order",
            answer=(
                "**h_orders** contiene las órdenes de venta (pedidos). Una orden es la solicitud "
                "de compra antes de ser facturada. No todas las órdenes se convierten en factura.\n\n"
                "**Diferencia clave:**\n"
                "- **Orden** = intención/pedido de compra\n"
                "- **Factura** = venta completada y facturada\n\n"
                "Para analizar ventas reales, se usa **h_invoices**. Para el pipeline de ventas, se usa **h_orders**."
            ),
        ),
    ),
    (
        [
            r"(?i)qu[eé]\s+(es|significa)\s+h_services",
            r"(?i)qu[eé]\s+tipos?\s+de\s+servicio",
        ],
        DirectResponse(
            name="what_is_services",
            answer=(
                "**h_services** contiene los servicios realizados a vehículos (mantenimiento, reparaciones, etc.). "
                "Incluye datos como: tipo de servicio (service_type), fecha, VIN del vehículo y agencia.\n\n"
                "Los tipos de servicio más comunes incluyen mantenimiento preventivo, "
                "mecánica, hojalatería y pintura, entre otros."
            ),
        ),
    ),
    (
        [
            r"(?i)qu[eé]\s+(es|significa)\s+h_service_appointments",
            r"(?i)qu[eé]\s+(es|son)\s+(las\s+)?citas?\s+de\s+servicio",
        ],
        DirectResponse(
            name="what_is_service_appointments",
            answer=(
                "**h_service_appointments** contiene las citas de servicio programadas. "
                "A diferencia de h_services (servicios ya realizados), esta tabla muestra las citas "
                "agendadas, con estados como: programada, confirmada, en proceso, completada o cancelada."
            ),
        ),
    ),
    (
        [
            r"(?i)qu[eé]\s+(es|significa)\s+h_customer_vehicle",
        ],
        DirectResponse(
            name="what_is_customer_vehicle",
            answer=(
                "**h_customer_vehicle** es la tabla que relaciona clientes con sus vehículos. "
                "Indica qué vehículos posee cada cliente (propiedad actual). "
                "Se usa para consultar la flotilla de un cliente o para conectar servicios/facturas con el dueño."
            ),
        ),
    ),
    (
        [
            r"(?i)qu[eé]\s+(es|significa)\s+h_insurance_policies",
            r"(?i)qu[eé]\s+(son\s+)?(las\s+)?p[oó]lizas",
        ],
        DirectResponse(
            name="what_is_insurance",
            answer=(
                "**h_insurance_policies** contiene las pólizas de seguro asociadas a los vehículos. "
                "Incluye información como el tipo de póliza, aseguradora, vigencia, estado "
                "y el vehículo/cliente asociado."
            ),
        ),
    ),
    (
        [
            r"(?i)qu[eé]\s+(es|significa)\s+h_agencies",
            r"(?i)qu[eé]\s+(es|son)\s+(las\s+)?agencias?",
        ],
        DirectResponse(
            name="what_is_agencies",
            answer=(
                "**h_agencies** contiene el catálogo de agencias/sucursales del grupo. "
                "Cada agencia tiene un identificador (id_agency), nombre y ubicación. "
                "Se usa para filtrar o agrupar datos por sucursal."
            ),
        ),
    ),

    # ── 6. Preguntas de negocio / conceptuales ───────────────────────────
    (
        [
            r"(?i)qu[eé]\s+(es|significa)\s+(la\s+)?recompra",
            r"(?i)qu[eé]\s+(es|significa)\s+(la\s+)?tasa\s+de\s+recompra",
        ],
        DirectResponse(
            name="what_is_repurchase",
            answer=(
                "La **recompra** se refiere a cuando un cliente compra un vehículo adicional después de su primera compra. "
                "El **tiempo promedio de recompra** mide cuántos días/meses pasan en promedio entre compras consecutivas. "
                "Es un KPI clave de lealtad y retención de clientes."
            ),
        ),
    ),
    (
        [
            r"(?i)qu[eé]\s+(es|significa)\s+(?:un|el)?\s*kpi\b",
        ],
        DirectResponse(
            name="what_is_kpi",
            answer=(
                "**KPI** (Key Performance Indicator) es un indicador clave de rendimiento. "
                "Son métricas que miden el desempeño del negocio, por ejemplo:\n"
                "- Unidades vendidas por mes\n"
                "- Tiempo promedio de recompra\n"
                "- Tasa de conversión de órdenes a facturas\n"
                "- Citas de servicio completadas vs canceladas"
            ),
        ),
    ),
    (
        [
            r"(?i)qu[eé]\s+(es|significa)\s+(el\s+)?pipeline\s+de\s+ventas",
            r"(?i)qu[eé]\s+(es|significa)\s+(el\s+)?funnel\s+de\s+ventas",
            r"(?i)qu[eé]\s+(es|significa)\s+(el\s+)?embudo\s+de\s+ventas",
        ],
        DirectResponse(
            name="what_is_pipeline",
            answer=(
                "El **pipeline (embudo) de ventas** representa las etapas por las que pasa una venta:\n"
                "1. **Prospección** → contacto inicial con el cliente\n"
                "2. **Orden** → el cliente hace un pedido (h_orders)\n"
                "3. **Facturación** → se concreta la venta (h_invoices)\n"
                "4. **Entrega** → el vehículo se entrega al cliente\n\n"
                "Puedo ayudarte a analizar conversiones entre etapas y tiempos promedio."
            ),
        ),
    ),
    (
        [
            r"(?i)qu[eé]\s+(es|significa)\s+(la\s+)?retenci[oó]n\s+de\s+clientes",
        ],
        DirectResponse(
            name="what_is_retention",
            answer=(
                "La **retención de clientes** mide la capacidad del negocio para mantener a sus clientes "
                "a lo largo del tiempo. Se puede analizar mediante:\n"
                "- Frecuencia de recompra de vehículos\n"
                "- Uso recurrente del servicio de mantenimiento\n"
                "- Renovación de pólizas de seguro\n\n"
                "Puedo consultar estos datos si me indicas un período o segmento específico."
            ),
        ),
    ),
    (
        [
            r"(?i)qu[eé]\s+(es|significa)\s+(el\s+)?ticket\s+promedio",
        ],
        DirectResponse(
            name="what_is_avg_ticket",
            answer=(
                "El **ticket promedio** es el monto promedio de cada transacción de venta. "
                "Se calcula dividiendo el ingreso total entre el número de transacciones. "
                "Puedo calcularlo por agencia, período o tipo de vehículo si me lo pides."
            ),
        ),
    ),

    # ── 7. Ayuda y soporte ───────────────────────────────────────────────
    (
        [
            r"(?i)^(ayuda|help|socorro)\s*[!.?]*$",
            r"(?i)necesito\s+ayuda",
        ],
        DirectResponse(
            name="help",
            answer=(
                "¡Con gusto te ayudo! Aquí algunas opciones:\n\n"
                "- **Hacer una consulta**: Escribe tu pregunta en español (ej: *¿Cuántas ventas hubo en marzo?*)\n"
                "- **Ver tablas disponibles**: Pregunta *¿Qué tablas hay?*\n"
                "- **Ver ejemplos**: Pregunta *Dame ejemplos de preguntas*\n"
                "- **Entender un concepto**: Pregunta *¿Qué es el VIN?* o *¿Qué significa DMS?*\n\n"
                "Si algo no funciona como esperas, intenta reformular tu pregunta con más detalle."
            ),
        ),
    ),
    (
        [
            r"(?i)no\s+(entiendo|entend[ií]|comprendo)",
            r"(?i)no\s+me\s+qued[oó]\s+claro",
            r"(?i)expl[ií]ca(me)?\s+(mejor|m[aá]s|otra\s+vez)",
        ],
        DirectResponse(
            name="not_understood",
            answer=(
                "Disculpa si no fui claro. Intenta lo siguiente:\n"
                "- Reformula tu pregunta con más detalle.\n"
                "- Especifica el período de tiempo que te interesa.\n"
                "- Menciona la tabla o dato específico que buscas.\n\n"
                "Por ejemplo, en lugar de *¿Cómo van las ventas?*, prueba con "
                "*¿Cuántas unidades se vendieron en la agencia X en enero 2025?*"
            ),
        ),
    ),
    (
        [
            r"(?i)(hay\s+un\s+)?(error|problema|fallo|bug)",
            r"(?i)(no\s+funciona|no\s+sirve|no\s+jala)",
            r"(?i)algo\s+(est[aá]|anda)\s+mal",
        ],
        DirectResponse(
            name="report_error",
            answer=(
                "Lamento que algo no esté funcionando bien. Puedes intentar:\n"
                "1. **Reformular la pregunta** con diferentes palabras.\n"
                "2. **Ser más específico** con fechas, agencias o filtros.\n"
                "3. **Verificar la conexión** a la base de datos en la barra lateral.\n\n"
                "Si el problema persiste, contacta al equipo de soporte técnico."
            ),
        ),
    ),

    # ── 8. Confirmaciones y afirmaciones ─────────────────────────────────
    (
        [
            r"(?i)^(s[ií]|ok|okey|okay|vale|va|de\s+acuerdo|entendido|perfecto|genial|excelente|bien|listo)\s*[!.?]*$",
            r"(?i)^(está\s+bien|muy\s+bien|súper)\s*[!.?]*$",
        ],
        DirectResponse(
            name="affirmation",
            answer="¡Perfecto! ¿Hay algo más en lo que pueda ayudarte?",
        ),
    ),
    (
        [
            r"(?i)^(no|nada|nop|nel|ninguno)\s*[!.?]*$",
            r"(?i)^(no,?\s+gracias|nada\s+m[aá]s|eso\s+es\s+todo)\s*[!.?]*$",
        ],
        DirectResponse(
            name="negation",
            answer="Entendido. Si necesitas algo después, aquí estaré. ¡Buen día!",
        ),
    ),

    # ── 9. Preguntas sobre períodos y fechas ─────────────────────────────
    (
        [
            r"(?i)qu[eé]\s+per[ií]odos?\s+(hay|tienes|manejas|cubres)",
            r"(?i)desde\s+cu[aá]ndo\s+(hay|tienes)\s+datos",
            r"(?i)qu[eé]\s+rango\s+de\s+fechas",
            r"(?i)desde\s+qu[eé]\s+fecha\s+(hay|tienes)\s+datos",
        ],
        DirectResponse(
            name="date_range",
            answer=(
                "El rango de datos disponible depende de cada tabla y de la carga del DWH. "
                "Para saber el rango exacto de una tabla, puedo consultarlo. "
                "Por ejemplo, pregúntame: *¿Cuál es la factura más antigua?* o "
                "*¿Desde cuándo hay registros en h_invoices?*"
            ),
        ),
    ),

    # ── 10. Preguntas sobre agencias ─────────────────────────────────────
    (
        [
            r"(?i)cu[aá]ntas\s+agencias\s+(hay|existen|tenemos)",
            r"(?i)cu[aá]ntas\s+sucursales\s+(hay|existen|tenemos)",
        ],
        DirectResponse(
            name="how_many_agencies",
            answer=(
                "Para darte el número exacto de agencias activas necesito consultar la base de datos. "
                "¿Quieres que consulte cuántas agencias hay registradas en el sistema?"
            ),
        ),
    ),

    # ── 11. Seguridad y privacidad ───────────────────────────────────────
    (
        [
            r"(?i)puedes\s+(modificar|borrar|eliminar|cambiar|actualizar|insertar)",
            r"(?i)^(modifica|borra|elimina|cambia|actualiza|inserta)\b",
            r"(?i)\b(delete|drop|update|insert|alter|truncate)\s+(from|into|table|database)\b",
        ],
        DirectResponse(
            name="readonly_warning",
            answer=(
                "Por seguridad, solo tengo permisos de **lectura** (SELECT). "
                "No puedo modificar, eliminar ni insertar datos en la base de datos. "
                "Si necesitas hacer cambios, contacta al administrador del sistema."
            ),
        ),
    ),
    (
        [
            r"(?i)(es\s+)?segur[oa]\s+(usar|este\s+sistema)",
            r"(?i)mis\s+datos\s+(est[aá]n\s+)?(seguros|protegidos)",
            r"(?i)privacidad\s+de\s+(los\s+)?datos",
        ],
        DirectResponse(
            name="security",
            answer=(
                "Tu información está protegida:\n"
                "- Solo tengo acceso de **lectura** a los datos.\n"
                "- No puedo modificar ni eliminar información.\n"
                "- Las consultas se ejecutan directamente contra la base de datos sin almacenar resultados.\n"
                "- La conexión al DWH usa los protocolos de seguridad configurados por tu equipo de TI."
            ),
        ),
    ),

    # ── 12. Sobre el proceso de consulta ─────────────────────────────────
    (
        [
            r"(?i)c[oó]mo\s+generas?\s+(el\s+)?(sql|query|consulta)",
            r"(?i)c[oó]mo\s+construyes?\s+(el\s+)?(sql|query|consulta)",
            r"(?i)usas?\s+(ia|inteligencia\s+artificial|llm|modelo)",
        ],
        DirectResponse(
            name="how_sql_generation",
            answer=(
                "Utilizo un modelo de IA (LLM) para interpretar tu pregunta en lenguaje natural "
                "y traducirla a una consulta SQL. El proceso es:\n\n"
                "1. **Interpreto** tu pregunta y determino qué datos necesitas.\n"
                "2. **Genero** la consulta SQL usando el esquema de la base de datos.\n"
                "3. **Valido** que la consulta sea segura (solo lectura).\n"
                "4. **Ejecuto** la consulta y te muestro los resultados.\n"
                "5. **Resumo** los datos en lenguaje natural.\n\n"
                "Si la consulta tiene un error, intento corregirla automáticamente."
            ),
        ),
    ),
    (
        [
            r"(?i)puedo\s+ver\s+el\s+sql",
            r"(?i)(mu[eé]strame|ver|ense[nñ]ame)\s+el\s+(sql|query|consulta)",
            r"(?i)d[oó]nde\s+(veo|est[aá])\s+el\s+sql",
        ],
        DirectResponse(
            name="show_sql",
            answer=(
                "Sí, el SQL generado se muestra en la sección **\"SQL generado\"** debajo de cada respuesta "
                "(si estás en modo developer). Haz clic en el desplegable para verlo."
            ),
        ),
    ),
    (
        [
            r"(?i)(puedo|c[oó]mo)\s+(?:exportar|exporto|descargar|descargo|bajar|bajo)\s+(?:los\s+)?(?:datos|resultados|informaci[oó]n)",
        ],
        DirectResponse(
            name="export_data",
            answer=(
                "Sí, puedes descargar los resultados:\n"
                "1. Haz clic en **\"Ver datos\"** para expandir los paneles.\n"
                "2. En la sección **\"Detalle (tabla y descarga)\"** encontrarás las opciones de descarga.\n"
                "3. Puedes exportar en formato CSV o Excel."
            ),
        ),
    ),

    # ── 13. Preguntas sobre métricas de negocio ─────────────────────────
    (
        [
            r"(?i)qu[eé]\s+(es|significa)\s+(la\s+)?conversi[oó]n",
            r"(?i)qu[eé]\s+(es|significa)\s+(la\s+)?tasa\s+de\s+conversi[oó]n",
        ],
        DirectResponse(
            name="what_is_conversion",
            answer=(
                "La **tasa de conversión** mide el porcentaje de oportunidades que se convierten en ventas reales. "
                "Por ejemplo:\n"
                "- Órdenes → Facturas: ¿Cuántas órdenes se concretan en venta?\n"
                "- Citas → Servicios: ¿Cuántas citas programadas se completan?\n\n"
                "Puedo calcular estas métricas si me indicas el período."
            ),
        ),
    ),
    (
        [
            r"(?i)qu[eé]\s+(es|significa)\s+(el\s+)?market\s*share",
            r"(?i)qu[eé]\s+(es|significa)\s+(la\s+)?participaci[oó]n\s+de\s+mercado",
        ],
        DirectResponse(
            name="what_is_market_share",
            answer=(
                "La **participación de mercado (market share)** es el porcentaje de ventas "
                "que una agencia o marca tiene respecto al total del mercado. "
                "Para calcularla internamente, puedo comparar ventas entre agencias o períodos."
            ),
        ),
    ),
    (
        [
            r"(?i)qu[eé]\s+(es|significa)\s+(el\s+)?roi\b",
            r"(?i)qu[eé]\s+(es|significa)\s+(el\s+)?retorno\s+de\s+inversi[oó]n",
        ],
        DirectResponse(
            name="what_is_roi",
            answer=(
                "**ROI** (Return on Investment / Retorno de Inversión) mide la ganancia obtenida "
                "en relación con la inversión realizada. Se calcula como:\n\n"
                "**ROI = (Ganancia - Inversión) / Inversión × 100%**\n\n"
                "Puedo ayudarte a calcular métricas relacionadas con los datos disponibles en el DWH."
            ),
        ),
    ),

    # ── 14. Preguntas sobre estado y conexión ────────────────────────────
    (
        [
            r"(?i)est[aá]s?\s+(conectado|funcionando|activo|en\s+l[ií]nea)",
            r"(?i)(est[aá]|funciona)\s+(la\s+)?conexi[oó]n",
            r"(?i)(est[aá]\s+)?(todo\s+)?bien\s+con\s+(la\s+)?(conexi[oó]n|bd|base)",
        ],
        DirectResponse(
            name="connection_status",
            answer=(
                "Estoy activo y listo para responder. El estado de la conexión a la base de datos "
                "lo puedes verificar en la **barra lateral** (sidebar), donde aparece el indicador de conexión. "
                "Si ves un error de conexión, verifica la URL del DWH en la configuración."
            ),
        ),
    ),

    # ── 15. Preguntas sobre filtros y seguimiento ────────────────────────
    (
        [
            r"(?i)c[oó]mo\s+filtro\s+por\s+agencia",
            r"(?i)c[oó]mo\s+(selecciono|escojo|elijo)\s+(una\s+)?agencia",
        ],
        DirectResponse(
            name="filter_by_agency",
            answer=(
                "Puedes filtrar por agencia de dos formas:\n"
                "1. **En tu pregunta**: Menciona la agencia directamente (ej: *ventas de la agencia Monterrey*).\n"
                "2. **Seguimiento por agencia**: En los resultados, haz clic en una agencia para fijarla "
                "y que las siguientes consultas se filtren automáticamente."
            ),
        ),
    ),
    (
        [
            r"(?i)c[oó]mo\s+filtro\s+por\s+veh[ií]culo",
            r"(?i)c[oó]mo\s+(busco|rastreo|sigo)\s+un\s+veh[ií]culo",
            r"(?i)c[oó]mo\s+uso\s+el\s+vin",
        ],
        DirectResponse(
            name="filter_by_vehicle",
            answer=(
                "Puedes consultar un vehículo de varias formas:\n"
                "1. **Por VIN**: *¿Cuál es el historial del VIN ABC123?*\n"
                "2. **Por placa**: Menciona la placa en tu pregunta.\n"
                "3. **Seguimiento por vehículo**: En los resultados, haz clic en un vehículo "
                "para fijarlo y que las consultas siguientes se centren en él."
            ),
        ),
    ),
    (
        [
            r"(?i)c[oó]mo\s+filtro\s+por\s+(fecha|per[ií]odo|mes|a[nñ]o)",
        ],
        DirectResponse(
            name="filter_by_date",
            answer=(
                "Simplemente incluye la fecha o período en tu pregunta:\n"
                "- *Ventas de enero 2025*\n"
                "- *Servicios del último trimestre*\n"
                "- *Órdenes entre marzo y junio 2024*\n"
                "- *Comparativo 2024 vs 2025*\n\n"
                "Yo interpreto la referencia temporal y genero los filtros de fecha correctos."
            ),
        ),
    ),

    # ── 16. Preguntas sobre gráficas y visualización ─────────────────────
    (
        [
            r"(?i)puedo\s+ver\s+(una\s+)?gr[aá]fica",
            r"(?i)(hay|tienes)\s+gr[aá]ficas?",
            r"(?i)c[oó]mo\s+veo\s+(la\s+)?gr[aá]fica",
        ],
        DirectResponse(
            name="charts",
            answer=(
                "Sí, las gráficas se generan automáticamente cuando los datos lo permiten. "
                "Para verlas:\n"
                "1. Haz clic en **\"Ver datos\"** para expandir los paneles.\n"
                "2. La sección **\"Gráfica\"** o **\"Vista de datos\"** muestra la visualización.\n"
                "3. Puedes elegir entre diferentes tipos de gráficas según los datos."
            ),
        ),
    ),

    # ── 17. Frases coloquiales / emotivas ────────────────────────────────
    (
        [
            r"(?i)eres\s+(muy\s+)?(inteligente|listo|crack|genio|bueno|chido|padre)",
            r"(?i)(me\s+)?ca(es|iste)\s+bien",
            r"(?i)buen\s+trabajo",
        ],
        DirectResponse(
            name="compliment",
            answer="¡Gracias! Me alegra poder ayudarte. ¿Hay algo más que necesites consultar?",
        ),
    ),
    (
        [
            r"(?i)eres\s+(tonto|malo|in[uú]til|burro|lento)",
            r"(?i)(no\s+sirves|no\s+sabes|eres\s+p[eé]simo)",
        ],
        DirectResponse(
            name="insult",
            answer=(
                "Lamento no haber cumplido tus expectativas. Estoy en constante mejora. "
                "¿Puedes reformular tu pregunta o decirme específicamente qué necesitas? "
                "Haré mi mejor esfuerzo."
            ),
        ),
    ),
    (
        [
            r"(?i)cu[eé]ntame\s+un\s+(chiste|joke)",
            r"(?i)d[ií]me\s+algo\s+(gracioso|chistoso|divertido)",
        ],
        DirectResponse(
            name="joke",
            answer=(
                "¿Por qué los programadores prefieren el modo oscuro? "
                "Porque la luz atrae a los bugs. 🐛\n\n"
                "Ahora sí, ¿en qué consulta te puedo ayudar?"
            ),
        ),
    ),
    (
        [
            r"(?i)qu[eé]\s+(hora|d[ií]a|fecha)\s+es",
            r"(?i)qu[eé]\s+d[ií]a\s+es\s+hoy",
        ],
        DirectResponse(
            name="current_time",
            answer=(
                "No tengo acceso al reloj del sistema, pero puedes ver la fecha y hora "
                "en la esquina de tu pantalla. Lo que sí puedo hacer es consultar datos por fecha. "
                "¿Necesitas información de algún período específico?"
            ),
        ),
    ),

    # ── 18. Preguntas sobre comparativos ─────────────────────────────────
    (
        [
            r"(?i)puedo\s+comparar",
            r"(?i)c[oó]mo\s+(hago|puedo\s+hacer)\s+(un\s+)?comparativo",
        ],
        DirectResponse(
            name="how_to_compare",
            answer=(
                "¡Claro! Puedes hacer comparativos de varias formas:\n"
                "- **Por período**: *Comparativo de ventas enero vs febrero 2025*\n"
                "- **Por agencia**: *Ventas por agencia en el último trimestre*\n"
                "- **Por año**: *Ventas 2024 vs 2025*\n"
                "- **Por tipo**: *Servicios de mantenimiento vs hojalatería*\n\n"
                "Solo describe qué quieres comparar y yo genero la consulta."
            ),
        ),
    ),

    # ── 19. Preguntas sobre límites del sistema ──────────────────────────
    (
        [
            r"(?i)cu[aá]ntos\s+registros\s+puedo\s+(ver|consultar|traer)",
            r"(?i)hay\s+(un\s+)?l[ií]mite\s+de\s+(datos|registros|filas)",
        ],
        DirectResponse(
            name="data_limits",
            answer=(
                "Las consultas pueden devolver hasta miles de registros, pero por rendimiento "
                "se recomienda usar filtros (fecha, agencia, etc.) para obtener resultados más específicos. "
                "Si necesitas datos masivos, es mejor hacer la extracción directamente desde la base de datos."
            ),
        ),
    ),
    (
        [
            r"(?i)puedo\s+(consultar|acceder\s+a)\s+otras?\s+(bases?|bd|sistemas?)",
            r"(?i)puedo\s+conectarme\s+a\s+otr[oa]",
        ],
        DirectResponse(
            name="other_databases",
            answer=(
                "Actualmente estoy configurado para trabajar con el DWH (Data Warehouse) que tienes conectado. "
                "Para conectar otra base de datos, se necesita actualizar la URL de conexión en la configuración. "
                "Consulta con tu equipo de TI para agregar nuevas fuentes de datos."
            ),
        ),
    ),

    # ── 20. Preguntas sobre lenguaje ─────────────────────────────────────
    (
        [
            r"(?i)(hablas|entiendes)\s+(ingl[eé]s|english)",
            r"(?i)can\s+you\s+speak\s+(english|spanish)",
            r"(?i)do\s+you\s+speak\s+(english|spanish)",
        ],
        DirectResponse(
            name="language",
            answer=(
                "Entiendo preguntas en **español** e **inglés**, pero mis respuestas están optimizadas "
                "para español ya que los datos del DWH usan terminología en ese idioma. "
                "Te recomiendo hacer tus consultas en español para mejores resultados."
            ),
        ),
    ),

    # ── 21. Solicitudes fuera de alcance ─────────────────────────────────
    (
        [
            r"(?i)(escribe|redacta|genera)\s+(un\s+)?(correo|email|carta|documento|reporte\s+en\s+word)",
            r"(?i)(hazme|crea)\s+(un\s+)?(presentaci[oó]n|powerpoint|ppt)",
        ],
        DirectResponse(
            name="out_of_scope_docs",
            answer=(
                "Mi especialidad es **consultar y analizar datos** del DWH. "
                "No puedo generar documentos, correos o presentaciones. "
                "Pero sí puedo darte los datos y análisis que necesitas para crearlos tú. "
                "¿Qué información necesitas?"
            ),
        ),
    ),
    (
        [
            r"(?i)(llama|marca|env[ií]a)\s+(un\s+)?(tel[eé]fono|mensaje|whatsapp|correo|email|sms)",
            r"(?i)(agenda|programa)\s+(una\s+)?(reuni[oó]n|junta|cita|llamada)",
        ],
        DirectResponse(
            name="out_of_scope_comms",
            answer=(
                "No tengo la capacidad de enviar mensajes, hacer llamadas o agendar reuniones. "
                "Mi función es ayudarte a consultar y analizar datos del negocio. "
                "¿Hay alguna consulta de datos en la que pueda ayudarte?"
            ),
        ),
    ),
    (
        [
            r"(?i)(busca|buscar)\s+en\s+(google|internet|la\s+web)",
            r"(?i)(clima|(?:el\s+)?tiempo\s+(?:de\s+hoy|en\s+\w+|libre|meteorol)|noticias|resultados?\s+deportivos?)",
            r"(?i)(recipe|receta|pel[ií]cula|canci[oó]n|m[uú]sica)",
        ],
        DirectResponse(
            name="out_of_scope_web",
            answer=(
                "No tengo acceso a internet ni a información externa. "
                "Mi alcance se limita a los datos del DWH (ventas, servicios, clientes, vehículos, etc.). "
                "¿Puedo ayudarte con alguna consulta de datos?"
            ),
        ),
    ),
    (
        [
            r"(?i)(predice|pron[oó]stico|forecast|estima)\s+(cu[aá]nto|cu[aá]ntas|las\s+ventas|el\s+futuro)",
            r"(?i)(cu[aá]nto\s+vamos?\s+a\s+vender|predicci[oó]n|proyecci[oó]n)",
        ],
        DirectResponse(
            name="out_of_scope_prediction",
            answer=(
                "Actualmente no cuento con modelos predictivos integrados. "
                "Lo que sí puedo hacer es mostrarte **tendencias históricas** y **comparativos** "
                "que te ayuden a hacer proyecciones. Por ejemplo:\n"
                "- Tendencia de ventas mensuales del último año\n"
                "- Comparativo mes a mes o año a año\n"
                "- Promedios y crecimiento porcentual\n\n"
                "¿Te gustaría ver alguna de estas métricas?"
            ),
        ),
    ),

    # ── 22. Sobre actualizaciones de datos ───────────────────────────────
    (
        [
            r"(?i)(cada\s+)?cu[aá]ndo\s+se\s+actualizan?\s+(los\s+)?datos",
            r"(?i)(qu[eé]\s+tan\s+)?actualizados?\s+(est[aá]n\s+)?(los\s+)?datos",
            r"(?i)los\s+datos\s+(son|est[aá]n)\s+(en\s+)?tiempo\s+real",
        ],
        DirectResponse(
            name="data_freshness",
            answer=(
                "Los datos del DWH se actualizan periódicamente mediante procesos de ETL "
                "(Extract, Transform, Load). La frecuencia de actualización depende de la "
                "configuración de tu equipo de TI (puede ser diaria, semanal, etc.). "
                "Para conocer la última fecha de actualización, puedo consultar el registro más reciente "
                "de cualquier tabla. ¿Quieres que lo verifique?"
            ),
        ),
    ),

    # ── 23. Formato y presentación de datos ──────────────────────────────
    (
        [
            r"(?i)los\s+(montos?|cantidades?|valores?)\s+(est[aá]n\s+)?en\s+(qu[eé]\s+)?(moneda|divisa)",
            r"(?i)(en\s+)?qu[eé]\s+moneda\s+(est[aá]n|son)",
            r"(?i)(d[oó]lares|pesos|usd|mxn)",
        ],
        DirectResponse(
            name="currency",
            answer=(
                "Los montos en el sistema generalmente están en **pesos mexicanos (MXN)**, "
                "aunque esto depende de la configuración del DMS de cada agencia. "
                "Si necesitas convertir a otra moneda, necesitarías aplicar el tipo de cambio externamente."
            ),
        ),
    ),

    # ── 24. Preguntas sobre rendimiento ──────────────────────────────────
    (
        [
            r"(?i)por\s*qu[eé]\s+tarda(s)?\s+(tanto|mucho)",
            r"(?i)(es|est[aá])\s+(muy\s+)?lent[oa]",
            r"(?i)cu[aá]nto\s+tarda\s+(una\s+)?consulta",
        ],
        DirectResponse(
            name="performance",
            answer=(
                "El tiempo de respuesta depende de:\n"
                "1. **Complejidad de la consulta**: Cruces entre muchas tablas toman más tiempo.\n"
                "2. **Volumen de datos**: Consultas sin filtros procesan más registros.\n"
                "3. **Conexión al servidor**: Latencia de red con la base de datos.\n"
                "4. **Generación de SQL**: El modelo de IA necesita unos segundos para interpretar tu pregunta.\n\n"
                "**Tip:** Usa filtros de fecha y agencia para consultas más rápidas."
            ),
        ),
    ),

    # ── 25. Confirmación de datos vacíos ─────────────────────────────────
    (
        [
            r"(?i)por\s*qu[eé]\s+no\s+(hay|aparecen?|sale|muestra)\s+(datos|resultados|nada|informaci[oó]n)",
            r"(?i)no\s+hay\s+resultados",
            r"(?i)la\s+consulta\s+(est[aá]|sali[oó])\s+vac[ií]a",
        ],
        DirectResponse(
            name="empty_results",
            answer=(
                "Si una consulta no devuelve resultados, puede deberse a:\n"
                "1. **Filtros muy restrictivos**: Intenta ampliar el rango de fechas o quitar filtros.\n"
                "2. **Datos no disponibles**: Puede que esa información no esté cargada en el DWH.\n"
                "3. **Nombre o valor incorrecto**: Verifica que los nombres de agencias/clientes estén bien escritos.\n\n"
                "Intenta con una consulta más amplia y luego ve refinando los filtros."
            ),
        ),
    ),

    # ── 26. Preguntas sobre clientes ─────────────────────────────────────
    (
        [
            r"(?i)qu[eé]\s+datos?\s+(tengo|hay|tienes)\s+de\s+(los\s+)?clientes",
            r"(?i)qu[eé]\s+informaci[oó]n\s+(hay|tienes)\s+de\s+(los\s+)?clientes",
        ],
        DirectResponse(
            name="customer_data_info",
            answer=(
                "La tabla **h_customers** contiene datos de clientes como:\n"
                "- Nombre del cliente (business_name)\n"
                "- Número de cliente DMS (nd_client_dms)\n"
                "- Tipo de cliente\n"
                "- Agencia asociada\n\n"
                "Además, puedo cruzar con otras tablas para obtener:\n"
                "- **Vehículos** que posee (h_customer_vehicle)\n"
                "- **Facturas** de compra (h_invoices)\n"
                "- **Servicios** a sus vehículos (h_services vía VIN)\n\n"
                "¿Qué información específica de clientes necesitas?"
            ),
        ),
    ),

    # ── 27. Sobre la IA / modelo ─────────────────────────────────────────
    (
        [
            r"(?i)qu[eé]\s+modelo\s+(de\s+ia\s+)?us[ao]s",
            r"(?i)(eres|usas)\s+(gpt|chatgpt|gemini|llama|mistral|claude)",
            r"(?i)qu[eé]\s+(ia|llm|modelo\s+de\s+lenguaje)\s+us[ao]s",
        ],
        DirectResponse(
            name="ai_model",
            answer=(
                "Utilizo un modelo de lenguaje (LLM) local configurado por tu equipo de TI "
                "para interpretar preguntas y generar consultas SQL. "
                "El modelo específico y su configuración los puedes ver en la barra lateral."
            ),
        ),
    ),

    # ── 28. Errores comunes explicados ───────────────────────────────────
    (
        [
            r"(?i)qu[eé]\s+(significa|es)\s+(el\s+)?(error|mensaje)\s+.*column.*does\s+not\s+exist",
            r"(?i)qu[eé]\s+significa\s+.*column.*no\s+existe",
        ],
        DirectResponse(
            name="error_column_not_exist",
            answer=(
                "El error **\"column does not exist\"** significa que la consulta SQL intentó usar "
                "un campo que no existe en la tabla. Esto puede pasar cuando el modelo de IA "
                "supone un nombre de columna incorrecto. Normalmente lo corrijo automáticamente "
                "en un segundo intento. Si persiste, reformula tu pregunta."
            ),
        ),
    ),
    (
        [
            r"(?i)qu[eé]\s+(significa|es)\s+(el\s+)?timeout",
            r"(?i)la\s+consulta\s+(expir[oó]|se\s+pas[oó]\s+de\s+tiempo)",
        ],
        DirectResponse(
            name="error_timeout",
            answer=(
                "Un **timeout** ocurre cuando la consulta tarda demasiado en ejecutarse. "
                "Soluciones:\n"
                "- Agrega filtros de fecha para reducir el volumen de datos.\n"
                "- Simplifica la pregunta (menos cruces de tablas).\n"
                "- Consulta rangos más cortos y luego amplía.\n"
                "- Verifica la conexión con tu equipo de TI si el problema persiste."
            ),
        ),
    ),

    # ── 29. Glosario automotriz ──────────────────────────────────────────
    (
        [
            r"(?i)qu[eé]\s+(es|significa)\s+(la\s+)?hojalater[ií]a",
        ],
        DirectResponse(
            name="what_is_hojalateria",
            answer=(
                "**Hojalatería y pintura** es el área de servicio automotriz dedicada a la reparación "
                "de la carrocería del vehículo: golpes, abolladuras, rayones y repintado. "
                "En el sistema aparece como un tipo de servicio en h_services."
            ),
        ),
    ),
    (
        [
            r"(?i)qu[eé]\s+(es|significa)\s+(el\s+)?mantenimiento\s+preventivo",
        ],
        DirectResponse(
            name="what_is_preventive_maintenance",
            answer=(
                "El **mantenimiento preventivo** son los servicios programados para mantener "
                "el vehículo en buen estado antes de que surjan fallas: cambio de aceite, "
                "revisión de frenos, alineación, etc. Se registra en h_services y "
                "se agenda mediante citas en h_service_appointments."
            ),
        ),
    ),
    (
        [
            r"(?i)qu[eé]\s+(es|significa)\s+(una\s+)?garant[ií]a",
            r"(?i)qu[eé]\s+tipos?\s+de\s+garant[ií]a",
        ],
        DirectResponse(
            name="what_is_warranty",
            answer=(
                "La **garantía** es el compromiso del fabricante o distribuidor de cubrir "
                "reparaciones o defectos durante un período determinado. "
                "Los servicios bajo garantía se registran en h_services con su tipo correspondiente."
            ),
        ),
    ),

    # ── 30. Misceláneos ──────────────────────────────────────────────────
    (
        [
            r"(?i)^(test|prueba|testing)\s*[!.?]*$",
        ],
        DirectResponse(
            name="test",
            answer="¡Funciona correctamente! Estoy listo para responder tus consultas. ¿En qué te puedo ayudar?",
        ),
    ),
    (
        [
            r"(?i)^(\.+|…+)\s*$",
            r"(?i)^(\?\?+|¿\?+)\s*$",
        ],
        DirectResponse(
            name="ellipsis",
            answer="¿En qué puedo ayudarte? Escribe tu pregunta y con gusto te respondo.",
        ),
    ),
    (
        [
            r"(?i)^(ja(ja)+|je(je)+|ji(ji)+|lol|lmao|xd+|haha(ha)*)\s*[!.?]*$",
        ],
        DirectResponse(
            name="laugh",
            answer="😄 ¿Hay algo en lo que pueda ayudarte?",
        ),
    ),
    (
        [
            r"(?i)(repite|rep[ií]teme)\s+(lo\s+)?(anterior|[uú]ltimo|que\s+dijiste)",
        ],
        DirectResponse(
            name="repeat",
            answer=(
                "Puedes desplazarte hacia arriba en el chat para ver mis respuestas anteriores. "
                "Si quieres que vuelva a ejecutar la misma consulta, escríbela de nuevo."
            ),
        ),
    ),
    (
        [
            r"(?i)^(nada|nope|nothing)\s*[!.?]*$",
            r"(?i)^(olvida(lo)?|olv[ií]dalo|forget\s*it)\s*[!.?]*$",
        ],
        DirectResponse(
            name="nothing",
            answer="Está bien. Si cambias de opinión, aquí estaré para ayudarte.",
        ),
    ),
    (
        [
            r"(?i)qui[eé]n\s+te\s+(hizo|cre[oó]|program[oó]|desarroll[oó])",
            r"(?i)qui[eé]n\s+es\s+tu\s+(creador|desarrollador|programador)",
        ],
        DirectResponse(
            name="creator",
            answer=(
                "Fui desarrollado por el equipo de tecnología para ayudarte con "
                "la inteligencia comercial del negocio. Mi objetivo es facilitarte "
                "el acceso a los datos y métricas del DWH."
            ),
        ),
    ),
    (
        [
            r"(?i)cu[aá]l\s+es\s+(tu\s+)?versi[oó]n",
            r"(?i)qu[eé]\s+versi[oó]n\s+eres",
        ],
        DirectResponse(
            name="version",
            answer="Soy **Nex IA** v1. Estoy en mejora continua para ofrecerte mejores respuestas.",
        ),
    ),
    (
        [
            r"(?i)puedes\s+(aprender|mejorar|entrenar)",
            r"(?i)(aprendes|mejoras)\s+con\s+(el\s+)?uso",
        ],
        DirectResponse(
            name="learning",
            answer=(
                "Mi equipo de desarrollo me actualiza constantemente para mejorar la precisión "
                "de las consultas y agregar nuevas funcionalidades. Si encuentras algo que deba mejorar, "
                "comparte tu retroalimentación con el equipo de soporte."
            ),
        ),
    ),
    (
        [
            r"(?i)(cu[aá]l\s+es\s+)?el\s+horario\s+de\s+(atenci[oó]n|servicio|soporte)",
            r"(?i)a\s+qu[eé]\s+hora\s+(abren|cierran|trabajan)",
        ],
        DirectResponse(
            name="business_hours",
            answer=(
                "Yo estoy disponible **24/7** mientras el servidor esté activo. "
                "Para horarios de atención de las agencias o servicio al cliente, "
                "puedo buscar esa información si está en el sistema. ¿Necesitas datos de alguna agencia?"
            ),
        ),
    ),
    (
        [
            r"(?i)(tienes|hay)\s+(alguna\s+)?(actualizaci[oó]n|novedad|cambio)\s+(reciente|nuev[oa])",
            r"(?i)qu[eé]\s+hay\s+de\s+nuevo",
        ],
        DirectResponse(
            name="whats_new",
            answer=(
                "Estoy en constante mejora. Algunas capacidades recientes:\n"
                "- Respuestas más inteligentes para preguntas de ventas y servicios.\n"
                "- Mejor manejo de filtros y comparativos.\n"
                "- KPIs determinísticos como tiempo de recompra.\n"
                "- Corrección automática de errores SQL.\n\n"
                "¿Hay algo específico que te gustaría que pudiera hacer?"
            ),
        ),
    ),

    # ── 31. Contexto de negocio automotriz ───────────────────────────────
    (
        [
            r"(?i)qu[eé]\s+(es|significa)\s+(un\s+)?concesionario",
            r"(?i)qu[eé]\s+(es|significa)\s+(un\s+)?dealer(ship)?",
        ],
        DirectResponse(
            name="what_is_dealer",
            answer=(
                "Un **concesionario (dealer)** es una empresa autorizada para vender vehículos "
                "nuevos de una marca específica. En el sistema, cada concesionario puede tener "
                "múltiples agencias/sucursales registradas en h_agencies."
            ),
        ),
    ),
    (
        [
            r"(?i)qu[eé]\s+(es|significa)\s+(un\s+)?etl\b",
        ],
        DirectResponse(
            name="what_is_etl",
            answer=(
                "**ETL** (Extract, Transform, Load) es el proceso que:\n"
                "1. **Extrae** datos de los sistemas fuente (DMS, CRM, etc.)\n"
                "2. **Transforma** los datos al formato homologado\n"
                "3. **Carga** los datos en el DWH\n\n"
                "Es lo que mantiene actualizada la información que consultamos."
            ),
        ),
    ),
    (
        [
            r"(?i)qu[eé]\s+(es|significa)\s+(el\s+)?crm\b",
        ],
        DirectResponse(
            name="what_is_crm",
            answer=(
                "**CRM** (Customer Relationship Management) es el sistema de gestión de relaciones "
                "con clientes. Registra interacciones, seguimientos y oportunidades de venta. "
                "Algunos datos del CRM se integran al DWH para enriquecer el análisis."
            ),
        ),
    ),
    (
        [
            r"(?i)qu[eé]\s+(es|significa)\s+(el\s+)?lead\b",
            r"(?i)qu[eé]\s+(son\s+)?(los\s+)?leads?\b",
        ],
        DirectResponse(
            name="what_is_lead",
            answer=(
                "Un **lead** es un prospecto o cliente potencial que ha mostrado interés en comprar. "
                "Es el primer paso del embudo de ventas: lead → oportunidad → orden → factura."
            ),
        ),
    ),
]


def match_common_response(question: str) -> DirectResponse | None:
    """Devuelve una respuesta directa si la pregunta coincide, o None para continuar el flujo normal."""
    q = question.strip()
    for patterns, response in _COMMON_RESPONSES:
        if any(re.search(p, q) for p in patterns):
            return response
    return None

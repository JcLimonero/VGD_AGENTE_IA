from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from .dwh import DwhClient
from .llm_local import OllamaClient
from .observability import StopWatch, record_query_event
from .sql_guard import clean_sql_output, validate_read_only_sql, validate_vgd_dwh_sql
from .sql_vehicle_context import apply_vehicle_focus_sql_rewrites


SYSTEM_PROMPT = """Eres un asistente experto en SQL para analytics.
Tu tarea es responder EXCLUSIVAMENTE con una consulta SQL de solo lectura.

OBLIGATORIO — dialecto: el bloque «Motor SQL objetivo» del mensaje de usuario define el motor.
Si indica PostgreSQL, genera SOLO sintaxis válida en PostgreSQL. NO uses funciones ni hábitos de MySQL
(YEAR/MONTH/DAY como función, IFNULL, LIMIT en medio de la sentencia como en otros motores), ni de
SQL Server (DATEADD, TOP, corchetes), ni de SQLite salvo que el mensaje pida SQLite explícitamente.

Las preguntas del usuario están en español: interpreta la intención en español (los nombres de tablas/columnas del esquema pueden estar en inglés).

Ejemplos de estilo (PostgreSQL; adapta tablas/columnas al esquema dado):
- Pregunta: "¿Cuántos clientes hay por estado?"
  SELECT state, COUNT(*) AS n FROM customers GROUP BY state ORDER BY n DESC;
- Pregunta: "Ventas totales por canal"
  SELECT channel, SUM(amount)::numeric AS total
  FROM sales
  WHERE status IN ('cerrada', 'facturada', 'entregada', 'completed')
  GROUP BY channel;
- Pregunta: "Citas completadas por taller"
  SELECT workshop, COUNT(*) AS n
  FROM service_appointments
  WHERE appointment_status = 'completada'
  GROUP BY workshop
  ORDER BY n DESC;

Reglas obligatorias:
1) Solo una consulta SQL.
2) No uses markdown, comentarios ni texto adicional.
3) Usa sentencias SELECT para analítica.
4) No uses UPDATE, INSERT, DELETE, DROP, ALTER, CREATE, TRUNCATE, MERGE, GRANT, REVOKE, CALL o EXEC.
5) Limita resultados a un máximo de 1000 filas cuando aplique.
6) Si la pregunta no se puede resolver con SQL, devuelve: SELECT 'No se puede resolver con SQL' AS mensaje;
7) Respeta SIEMPRE el dialecto del «Motor SQL objetivo» en el mensaje de usuario (en este producto suele ser PostgreSQL).
8) Si la pregunta pide datos de vehículos o cada fila identifica un vehículo (tabla vehicles, vehicle_id,
   ventas/servicios/citas/pólizas por unidad), incluye SIEMPRE la columna vin: haz JOIN a vehicles si no está
   y expón vehicles.vin (o alias v.vin). No aplica a agregados puramente globales sin desglose por unidad.
9) agency_id / idAgency: ÚSALO SOLO si el esquema de referencia lista explícitamente esa columna en esa tabla.
   En el dataset demo típico, sales, services, service_appointments e insurance_policies NO tienen agency_id;
   customers y vehicles tampoco. No inventes sales.agency_id. Para “por agencia” sin columna, agrupa por
   customers.state, sales.channel, customers.segment, sales.seller o usa mv_sales_monthly según el esquema.
10) Si preguntan si una unidad o VIN concreto tiene seguro o póliza, consulta insurance_policies unido a
    vehicles (por vehicle_id o vin); no mezcles con listados de oportunidades comerciales salvo que lo pidan explícito.
    En el dataset demo, policy_status usa valores en español: activa, vencida, cancelada (no uses 'active' ni
    inventes estados como 'vence_pronto' salvo que el esquema los liste explícitamente).
11) Si hay historial de conversación, úsalo para entender referencias como «esa unidad», «el mismo cliente»,
    «lo anterior», «y el dueño?», etc., sin repetir identificadores que ya aparecieron en turnos previos.
12) Si el prompt o el historial fija vehicle_id o vin para seguimiento («esta unidad»), filtra SOLO esa fila con
    literales (vehicles.id o vehicles.vin). Nunca sustituyas eso por subconsultas como
    (SELECT vin FROM services ORDER BY service_date DESC LIMIT 1).
    No escribas cadenas ficticias como 'ultimo_vin', 'last_vin' ni 'esta_unidad' como valor de VIN: usa el
    VIN o id numérico exactos del contexto.
13) DIFERENCIA CLAVE entre services y service_appointments:
    - services: servicios ya realizados. Tiene cost, service_date, status y notes.
    - service_appointments: agenda de citas. Tiene appointment_date, appointment_status, cancellation_reason, attended. NO tiene cost, notes ni service_date.
    - Para costos o montos de servicio usa siempre services.cost, NUNCA service_appointments.cost (no existe).
    - Para la fecha de un servicio realizado usa services.service_date; para la fecha de una cita usa service_appointments.appointment_date.
14) Usa COUNT(*) o COUNT(columna); nunca COUNT() vacío (inválido en PostgreSQL).
15) PostgreSQL y columnas DATE (p. ej. sales.sale_date): la resta fecha1 - fecha2 devuelve INTEGER (días),
    no INTERVAL. NO uses EXTRACT(EPOCH FROM (fecha1 - fecha2)) (falla). Opciones válidas:
    - Promedio en días: AVG(fecha1 - fecha2) o AVG((fecha1 - fecha2)::numeric).
    - Si necesitas EPOCH: EXTRACT(EPOCH FROM (fecha1::timestamp - fecha2::timestamp)).
16) PostgreSQL: NO uses funciones estilo MySQL YEAR(c), MONTH(c), DAY(c) (no existen). Usa
    EXTRACT(YEAR FROM c), EXTRACT(MONTH FROM c), EXTRACT(DAY FROM c).
17) PostgreSQL: la resta de dos DATE devuelve INTEGER (días). NO escribas (d2 - d1) :: interval 'day'
    ni casts similares; usa solo (d2 - d1) o castea a numeric si hace falta.
18) LAG, LEAD, ROW_NUMBER, etc. son funciones de ventana: van en el SELECT (o en una subconsulta/CTE),
    nunca como «JOIN LAG(...)» ni «JOIN ROW_NUMBER()». Para emparejar fila con la anterior venta,
    usa WITH/ subconsulta: SELECT ... LAG(sale_date) OVER (PARTITION BY customer_id ORDER BY sale_date) ...
    y luego filtra o une sobre ese resultado.
"""

SYSTEM_PROMPT_VGD = """Eres un asistente experto en SQL para analytics.
Tu tarea es responder EXCLUSIVAMENTE con una consulta SQL de solo lectura.

OBLIGATORIO — dialecto: el bloque «Motor SQL objetivo» del mensaje de usuario define el motor.
Si indica PostgreSQL, genera SOLO sintaxis válida en PostgreSQL. NO uses hábitos de MySQL (YEAR/MONTH/DAY como función,
IFNULL), ni SQL Server (DATEADD, TOP), ni SQLite salvo que el mensaje lo pida explícitamente.

Las preguntas del usuario están en español: interpreta la intención en español.

FUENTE DE VERDAD — Esquema de referencia: el mensaje de usuario incluye el listado actual de tablas y columnas.
Úsalo como única lista válida. No inventes tablas ni columnas que no aparezcan ahí.

Catálogo de agencias (sucursales / concesionarios): la tabla maestra es agencies (columnas como "idAgency", name).
Para «qué agencias hay», «cuántas agencias», «listado de agencias»: usa FROM agencies (y COUNT(*) o SELECT de "idAgency"/name).
No uses customers para listar el catálogo de agencias: customers pertenece a una agencia vía "idAgency", pero el listado oficial es agencies.
Solo tendría sentido DISTINCT "idAgency" FROM customers si el usuario pide explícitamente agencias que aparecen en clientes (subconjunto), no el catálogo completo.

Ejemplos de forma (adapta nombres reales al esquema de referencia):
- SELECT dim, COUNT(*)::bigint AS n FROM tabla_en_esquema GROUP BY dim ORDER BY n DESC;
- SELECT COUNT(*)::bigint AS n FROM tabla_en_esquema;

Reglas obligatorias:
1) Solo una consulta SQL; sin markdown ni comentarios.
2) Solo SELECT/WITH de lectura; sin INSERT/UPDATE/DELETE/DDL.
3) Si no se puede resolver con el esquema dado: SELECT 'No se puede resolver con SQL' AS mensaje;
4) FROM y GROUP BY coherentes: cada columna en GROUP BY debe salir del FROM o ser agregado válido.
5) Identificadores camelCase entre comillas dobles en PostgreSQL cuando aplique.
6) COUNT(*) o COUNT(col); nunca COUNT() vacío.
7) Resta DATE - DATE es entero (días); no uses EXTRACT(EPOCH FROM (d1-d2)) mezclando mal tipos.
8) EXTRACT(YEAR FROM col), no YEAR(col). COALESCE, no IFNULL.
9) LAG/LEAD/ROW_NUMBER en SELECT o CTE, no como JOIN directo a la función de ventana.
10) Si el historial fija un VIN u otro literal, úsalo tal cual; no inventes subconsultas sustitutas.
11) Preguntas de catálogo de agencias → tabla agencies, no customers (ver bloque «Catálogo de agencias» arriba).
"""

SQL_FIX_PROMPT = """Eres un asistente experto en corrección de SQL.
Debes corregir una consulta SQL que falló al ejecutarse.

El dialecto lo fija el bloque «Motor SQL objetivo» del mensaje de usuario (casi siempre PostgreSQL).
La salida debe ser SQL ejecutable en ESE motor, no en MySQL ni SQL Server.

Reglas obligatorias:
1) Responde SOLO con SQL (sin markdown ni texto adicional).
2) Mantén la intención original de la pregunta de negocio.
3) Usa únicamente SQL de lectura (SELECT/CTE), sin operaciones de escritura.
4) Corrige alias, columnas o joins inválidos según el error reportado.
5) Respeta SIEMPRE el dialecto del «Motor SQL objetivo» en el mensaje de usuario.
6) Si la consulta trata vehículos o filas con vehicle_id, asegura que el SELECT incluya vin (desde vehicles).
7) services y service_appointments son tablas DIFERENTES:
   - services tiene cost, service_date, status, notes.
   - service_appointments tiene appointment_date, appointment_status, cancellation_reason, attended. NO tiene cost, notes ni service_date.
   Si el error dice que una columna no existe en service_appointments, probablemente debes usar la tabla services en su lugar.
8) insurance_policies.policy_status en la demo usa: activa, vencida, cancelada. Corrige 'active', 'inactive', etc.
9) Si el contexto fija un VIN o vehicle_id, no lo reemplaces por subconsultas sobre services u otras tablas.
10) Si el SQL usó un literal ficticio de VIN ('ultimo_vin', 'last_vin', etc.) y el contexto trae el VIN real,
    sustituye por el valor correcto entre comillas simples (escapando apóstrofos si los hay).
11) Si el error es «column agency_id does not exist» (u otra columna inexistente) en sales u otra tabla de hechos,
    elimina agency_id: en el demo suele no existir; agrupa por customers.state, sales.channel, segment o usa mv_sales_monthly.
12) Corrige COUNT() sin argumento a COUNT(*).
13) Si el error es «extract(unknown, integer)» o EXTRACT(EPOCH FROM ...) con resta de fechas DATE,
    usa AVG(f1 - f2) en días o EXTRACT(EPOCH FROM (f1::timestamp - f2::timestamp)).
14) Si el error es «function year(date) does not exist» (o month/day): reemplaza YEAR(x) por
    EXTRACT(YEAR FROM x); MONTH(x) y DAY(x) igual con EXTRACT.
15) Si el error es «syntax error at or near interval» con :: interval 'day': quita ese cast;
    (fecha2 - fecha1) en DATE ya son días (entero).
16) Si hay JOIN con LAG/LEAD/ROW_NUMBER: reescribe con CTE o subconsulta donde la ventana esté en el SELECT.
"""

SQL_FIX_PROMPT_VGD = """Eres un asistente experto en corrección de SQL.
Debes corregir una consulta SQL que falló al ejecutarse.

El dialecto lo fija el bloque «Motor SQL objetivo» (PostgreSQL).
La salida debe ser SQL ejecutable en PostgreSQL, no en MySQL ni SQL Server.

Reglas obligatorias:
1) Responde SOLO con SQL (sin markdown ni texto adicional).
2) Mantén la intención original de la pregunta de negocio.
3) Solo SELECT/CTE de lectura.
4) Corrige usando únicamente tablas y columnas del «Esquema de referencia» del mensaje de usuario.
5) Si el error es tabla o columna inexistente, elimina referencias que no estén en ese esquema.
6) camelCase entre comillas dobles cuando el esquema lo muestre así.
7) Corrige COUNT() vacío a COUNT(*) o COUNT(col).
8) Fechas DATE: resta devuelve días enteros; EXTRACT(EPOCH ...) coherente con tipos.
9) YEAR/MONTH/DAY: usa EXTRACT(YEAR FROM x), etc.
10) Si la intención es listar o contar agencias (catálogo) y el SQL usó customers sin que el usuario pidiera «agencias con clientes» u operación similar, pasa a FROM agencies con "idAgency" y name según el esquema.
"""


def resolve_llm_profile(schema_hint_file: str = "", *, dwh_url: str | None = None) -> str:
    """
    Perfil de prompts. Por defecto «vgd» (DWH vgd_dwh_prod_migracion).
    Usa AGENTE_DWH_LLM_PROFILE=default solo en entornos excepcionales (p. ej. otro esquema con SKIP_DB_NAME_CHECK).
    """
    env = os.getenv("AGENTE_DWH_LLM_PROFILE", "").strip().lower()
    if env == "vgd":
        return "vgd"
    if env == "default":
        return "default"
    path = (schema_hint_file or "").lower()
    if (
        "schema_hint_dwh" in path
        or "vgd_dwh_migracion" in path
        or "schema_hint_vgd" in path
    ):
        return "vgd"
    url = (dwh_url if dwh_url is not None else os.getenv("DWH_URL", "")).lower()
    if "vgd_dwh" in url:
        return "vgd"
    return "vgd"


@dataclass
class QueryResult:
    question: str
    generated_sql: str
    rows: list[dict[str, Any]]


class DwhAgent:
    def __init__(
        self,
        dwh_client: DwhClient,
        llm_client: OllamaClient,
        schema_hint: str = "",
        *,
        llm_profile: str = "vgd",
    ) -> None:
        self._dwh = dwh_client
        self._llm = llm_client
        self._schema_hint = schema_hint.strip()
        self._llm_profile = llm_profile if llm_profile in ("default", "vgd") else "vgd"

    def _system_prompt(self) -> str:
        return SYSTEM_PROMPT_VGD if self._llm_profile == "vgd" else SYSTEM_PROMPT

    def _sql_fix_system_prompt(self) -> str:
        return SQL_FIX_PROMPT_VGD if self._llm_profile == "vgd" else SQL_FIX_PROMPT

    def _dialect_guidance(self) -> str:
        dialect = self._dwh.dialect_name
        if dialect == "sqlite":
            return (
                "Motor SQL objetivo: SQLite.\n"
                "Reglas de dialecto SQLite:\n"
                "- NO uses DATEADD, DATEDIFF ni funciones exclusivas de SQL Server.\n"
                "- Para fechas usa date()/datetime()/strftime() de SQLite.\n"
                "- Usa CURRENT_DATE, CURRENT_TIMESTAMP o date('now') según convenga.\n"
                "- Operadores válidos: <=, >=, != (evita símbolos unicode como ≤, ≥, ≠).\n"
            )
        if dialect == "postgresql":
            return (
                "Motor SQL objetivo: PostgreSQL.\n"
                "Genera SQL que ejecute en PostgreSQL sin errores de sintaxis de otros motores.\n"
                "Reglas de dialecto PostgreSQL:\n"
                "- Fechas: EXTRACT(YEAR FROM col), no YEAR(col); intervalos con INTERVAL '1 day' / '1 month'.\n"
                "- Resta DATE - DATE = días (entero); no uses (d2-d1)::interval 'day'.\n"
                "- Agregados: COUNT(*) o COUNT(col); nunca COUNT() vacío.\n"
                "- LIMIT va al final del SELECT (o subconsulta) según sintaxis PostgreSQL.\n"
                "- Casts habituales: expresion::numeric, expresion::date, expresion::timestamp.\n"
                "- Para redondear: ROUND((expresion)::numeric, n); evita ROUND sobre double sin cast.\n"
                "- No uses DATEADD/DATEDIFF (SQL Server) ni IFNULL (usa COALESCE).\n"
            )
        if dialect:
            return f"Motor SQL objetivo: {dialect}.\nRespeta estrictamente este dialecto.\n"
        return "Motor SQL objetivo no identificado. Usa SQL ANSI estándar cuando sea posible.\n"

    def _build_user_prompt(self, question: str) -> str:
        schema_context = self._schema_hint or "No se proporcionó esquema."
        return (
            f"{self._dialect_guidance()}\n"
            f"Esquema de referencia:\n{schema_context}\n\n"
            f"Pregunta de negocio:\n{question}\n\n"
            "Devuelve solamente SQL válido para el motor indicado arriba (mismo dialecto que el DWH)."
        )

    def _build_fix_prompt(self, question: str, previous_sql: str, execution_error: str) -> str:
        schema_context = self._schema_hint or "No se proporcionó esquema."
        return (
            f"{self._dialect_guidance()}\n"
            f"Esquema de referencia:\n{schema_context}\n\n"
            f"Pregunta original:\n{question}\n\n"
            f"SQL que falló:\n{previous_sql}\n\n"
            f"Error de ejecución:\n{execution_error}\n\n"
            "Devuelve SOLO una versión corregida del SQL para el motor indicado arriba."
        )

    def get_cache_stats(self) -> dict[str, Any]:
        return self._dwh.get_cache_stats()

    def answer(
        self,
        question: str,
        *,
        prompt_extra: str = "",
        conversation_transcript: str = "",
        vehicle_focus: dict[str, Any] | None = None,
    ) -> QueryResult:
        """
        Resuelve la pregunta. `question` es el texto que se guarda en el resultado (UI/JSON).
        `prompt_extra` (opcional) se antepone al prompt del LLM.
        `conversation_transcript` (opcional) resume turnos previos para seguimiento conversacional.
        `vehicle_focus` (opcional) vin / vehicle_id / placa para sustituir literales placeholder en el SQL.
        """
        stopwatch = StopWatch()
        display_question = question.strip()
        extra = (prompt_extra or "").strip()
        transcript = (conversation_transcript or "").strip()
        parts: list[str] = []
        if transcript:
            parts.append(transcript)
        if extra:
            parts.append(extra)
        parts.append(display_question)
        llm_question = "\n\n".join(parts)
        try:
            prompt = self._build_user_prompt(llm_question)
            raw_output = self._llm.generar_sql(prompt=prompt, system_prompt=self._system_prompt())
            generated_sql = apply_vehicle_focus_sql_rewrites(
                clean_sql_output(raw_output),
                vehicle_focus,
            )
            validate_read_only_sql(generated_sql)
            try:
                validate_vgd_dwh_sql(generated_sql)
                rows = self._dwh.execute_select(generated_sql)
                result = QueryResult(question=display_question, generated_sql=generated_sql, rows=rows)
                record_query_event(
                    source="agent",
                    success=True,
                    duration_ms=stopwatch.elapsed_ms(),
                    row_count=len(rows),
                    cached=False,
                    message="llm_sql",
                )
                return result
            except RuntimeError as first_exc:
                # Reintento único: pedir al LLM una corrección basada en el error SQL (o prevalidación VGD).
                fix_prompt = self._build_fix_prompt(
                    question=llm_question,
                    previous_sql=generated_sql,
                    execution_error=str(first_exc),
                )
                fixed_raw = self._llm.generar_sql(
                    prompt=fix_prompt, system_prompt=self._sql_fix_system_prompt()
                )
                fixed_sql = apply_vehicle_focus_sql_rewrites(
                    clean_sql_output(fixed_raw),
                    vehicle_focus,
                )
                validate_read_only_sql(fixed_sql)
                validate_vgd_dwh_sql(fixed_sql)
                rows = self._dwh.execute_select(fixed_sql)
                result = QueryResult(question=display_question, generated_sql=fixed_sql, rows=rows)
                record_query_event(
                    source="agent",
                    success=True,
                    duration_ms=stopwatch.elapsed_ms(),
                    row_count=len(rows),
                    cached=False,
                    message="llm_sql_fix",
                )
                return result
        except Exception as exc:
            record_query_event(
                source="agent",
                success=False,
                duration_ms=stopwatch.elapsed_ms(),
                row_count=0,
                cached=False,
                message=str(exc),
            )
            raise

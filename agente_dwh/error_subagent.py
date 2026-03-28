"""Registro de errores y subagente de corrección automática."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import argparse
import json
import os
from pathlib import Path
import re
import time
from typing import Any
from uuid import uuid4


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ERROR_LOG_DIR = _PROJECT_ROOT / "logerrores"
PROCESSED_DIR_NAME = "procesados"


def ensure_error_log_dir(log_dir: Path | None = None) -> Path:
    """Crea y devuelve el directorio donde se guardan errores."""
    target = log_dir or DEFAULT_ERROR_LOG_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target


def _keep_processed_files_enabled() -> bool:
    """
    Conserva evidencia de errores procesados por defecto.

    Desactiva con AGENTE_DWH_KEEP_ERROR_FILES=0.
    """
    raw = os.getenv("AGENTE_DWH_KEEP_ERROR_FILES", "1").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _json_safe(value: Any) -> Any:
    """Convierte valores no serializables a string."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return str(value)


def log_error_file(
    *,
    source: str,
    message: str,
    context: dict[str, Any] | None = None,
    log_dir: Path | None = None,
) -> Path:
    """
    Guarda un error en un archivo único dentro de `logerrores`.
    """
    directory = ensure_error_log_dir(log_dir)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    file_name = f"error_{timestamp}_{uuid4().hex[:8]}.json"
    file_path = directory / file_name
    payload = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "message": message,
        "context": _json_safe(context or {}),
    }
    file_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return file_path


@dataclass(frozen=True)
class ErrorFixResult:
    file_name: str
    source: str
    status: str
    fix_note: str
    fixed_sql: str | None = None


class ErrorFixSubagent:
    """
    Subagente simple que:
    1) lee archivos de `logerrores`,
    2) intenta corregir SQL comúnmente inválido,
    3) archiva el original en `procesados/` y guarda resultado de corrección.
    """

    def __init__(self, log_dir: Path | None = None) -> None:
        self.log_dir = ensure_error_log_dir(log_dir)
        self._processed_dir = ensure_error_log_dir(self.log_dir / PROCESSED_DIR_NAME)

    def process_pending_files(self) -> list[ErrorFixResult]:
        results: list[ErrorFixResult] = []
        for file_path in sorted(self.log_dir.glob("error_*.json")):
            results.append(self._process_file(file_path))
        return results

    def _process_file(self, file_path: Path) -> ErrorFixResult:
        payload: dict[str, Any] = {}
        source = "unknown"
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
            source = str(payload.get("source") or "unknown")
            parsed_result = self._attempt_fix(payload)
            fix_result = ErrorFixResult(
                file_name=file_path.name,
                source=parsed_result.source,
                status=parsed_result.status,
                fix_note=parsed_result.fix_note,
                fixed_sql=parsed_result.fixed_sql,
            )
        except Exception as exc:  # noqa: BLE001
            fix_result = ErrorFixResult(
                file_name=file_path.name,
                source=source,
                status="read_error",
                fix_note=f"No se pudo procesar el archivo de error: {exc}",
            )
        finally:
            try:
                self._finalize_file(file_path, fix_result)
            except OSError:
                # Si no se puede borrar, no detenemos el flujo.
                pass
        return fix_result

    def _finalize_file(self, file_path: Path, fix_result: ErrorFixResult) -> None:
        if not _keep_processed_files_enabled():
            file_path.unlink()
            return
        destination = self._processed_dir / file_path.name
        if destination.exists():
            destination = self._processed_dir / f"{file_path.stem}_{uuid4().hex[:6]}{file_path.suffix}"
        file_path.replace(destination)
        self._write_result_report(destination=destination, fix_result=fix_result)

    def _write_result_report(self, *, destination: Path, fix_result: ErrorFixResult) -> None:
        report_name = f"{destination.stem}_resultado.json"
        report_path = destination.with_name(report_name)
        payload = {
            "original_file": destination.name,
            "status": fix_result.status,
            "source": fix_result.source,
            "fix_note": fix_result.fix_note,
            "fixed_sql": fix_result.fixed_sql,
            "processed_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _attempt_fix(self, payload: dict[str, Any]) -> ErrorFixResult:
        context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
        source = str(payload.get("source") or "unknown")
        error_message = str(payload.get("message") or "")
        sql = str(context.get("sql") or "")
        if not sql:
            return ErrorFixResult(
                file_name="",
                source=source,
                status="no_sql",
                fix_note="El error no incluía SQL para corregir.",
                fixed_sql=None,
            )
        fixed_sql = self._apply_sql_heuristics(sql, error_message)
        if fixed_sql == sql:
            return ErrorFixResult(
                file_name="",
                source=source,
                status="no_changes",
                fix_note="No hubo cambios automáticos para este patrón.",
                fixed_sql=None,
            )
        return ErrorFixResult(
            file_name="",
            source=source,
            status="fixed_sql",
            fix_note="SQL corregido automáticamente por heurísticas.",
            fixed_sql=fixed_sql,
        )

    def _apply_sql_heuristics(self, sql: str, error_message: str) -> str:
        fixed = sql
        lower_error = error_message.lower()

        fixed = re.sub(r"\bCOUNT\s*\(\s*\)", "COUNT(*)", fixed, flags=re.IGNORECASE)

        if "function year(" in lower_error or re.search(r"\bYEAR\s*\(", fixed, flags=re.IGNORECASE):
            fixed = re.sub(
                r"\bYEAR\s*\(\s*([^)]+?)\s*\)",
                r"EXTRACT(YEAR FROM \1)",
                fixed,
                flags=re.IGNORECASE,
            )
        if "function month(" in lower_error or re.search(r"\bMONTH\s*\(", fixed, flags=re.IGNORECASE):
            fixed = re.sub(
                r"\bMONTH\s*\(\s*([^)]+?)\s*\)",
                r"EXTRACT(MONTH FROM \1)",
                fixed,
                flags=re.IGNORECASE,
            )
        if "function day(" in lower_error or re.search(r"\bDAY\s*\(", fixed, flags=re.IGNORECASE):
            fixed = re.sub(
                r"\bDAY\s*\(\s*([^)]+?)\s*\)",
                r"EXTRACT(DAY FROM \1)",
                fixed,
                flags=re.IGNORECASE,
            )

        # PostgreSQL: elimina cast inválido ":: interval 'day'" sobre resta de fechas.
        fixed = re.sub(
            r"\)\s*::\s*interval\s*'(?:day|days|month|months|year|years)'",
            ")",
            fixed,
            flags=re.IGNORECASE,
        )

        # Tablas homologadas h_* mal nombradas (siempre corregir, no solo cuando el error lo mencione).
        _table_fixes = {
            "h_clients": "h_customers",
            "h_client": "h_customers",
            "h_customer": "h_customers",
            "h_order": "h_orders",
            "h_invoice": "h_invoices",
            "h_service": "h_services",
            "h_agency": "h_agencies",
        }
        for wrong, correct in _table_fixes.items():
            fixed = re.sub(rf"(?i)\b{re.escape(wrong)}\b", correct, fixed)

        # Alias de cliente común incorrecto en vistas homologadas.
        fixed = re.sub(r"(?i)(\b[A-Za-z_][A-Za-z0-9_]*\s*\.\s*)id_client\b", r"\1nd_client_dms", fixed)
        fixed = re.sub(r'(?i)(?<!\.)\bid_client\b', "nd_client_dms", fixed)

        # h_services no tiene nd_client_dms: si el error menciona esa columna en h_services,
        # reemplazar el JOIN directo por el puente h_customer_vehicle.
        if "nd_client_dms" in lower_error and "h_services" in fixed.lower():
            # Detectar alias de h_services
            svc_aliases = re.findall(
                r'(?i)\b(?:FROM|JOIN)\s+h_services\s+(?:AS\s+)?([A-Za-z_][A-Za-z0-9_]*)',
                fixed,
            )
            for sa in svc_aliases:
                # Reemplazar: JOIN h_customers <ca> ON <sa>.nd_client_dms = ...
                # por el JOIN correcto a través de h_customer_vehicle
                fixed = re.sub(
                    rf'(?i)JOIN\s+h_customers\s+(?:AS\s+)?([A-Za-z_][A-Za-z0-9_]*)\s+ON\s+{re.escape(sa)}\."?nd_client_dms"?\s*=\s*CAST\(\1\.id\s+AS\s+TEXT\)',
                    r'JOIN h_customer_vehicle cv ON ' + sa + r'.vin = cv.vin JOIN h_customers \1 ON cv.nd_client_dms = \1.nd_client_dms',
                    fixed,
                )
                fixed = re.sub(
                    rf'(?i)JOIN\s+h_customers\s+(?:AS\s+)?([A-Za-z_][A-Za-z0-9_]*)\s+ON\s+{re.escape(sa)}\."?nd_client_dms"?\s*=\s*\1\."?nd_client_dms"?',
                    r'JOIN h_customer_vehicle cv ON ' + sa + r'.vin = cv.vin JOIN h_customers \1 ON cv.nd_client_dms = \1.nd_client_dms',
                    fixed,
                )

        # Columna inventada agency_id → id_agency (columna real en vistas h_*).
        fixed = re.sub(r'(?i)(\b[A-Za-z_][A-Za-z0-9_]*\s*\.\s*)agency_id\b', r'\1id_agency', fixed)
        fixed = re.sub(r'(?i)(?<!\.)\bagency_id\b', 'id_agency', fixed)

        # Join de agencias usando id (incorrecto) en lugar de id_agency.
        fixed = re.sub(
            r'(?i)(\bh_agencies\s+[A-Za-z_][A-Za-z0-9_]*\s+JOIN\s+[A-Za-z_][A-Za-z0-9_]*\s+[A-Za-z_][A-Za-z0-9_]*\s+ON\s+)([A-Za-z_][A-Za-z0-9_]*)\s*\.\s*id\s*=',
            r"\1\2.id_agency =",
            fixed,
        )

        # Fix complementario: alias.id = X.id_agency → alias.id_agency = X.id_agency
        aliases = re.findall(
            r'(?i)\b(?:FROM|JOIN)\s+h_agencies(?:\s+(?:AS\s+)?(?!(?:ON|WHERE|GROUP|ORDER|LIMIT|JOIN)\b))([A-Za-z_][A-Za-z0-9_]*)',
            fixed,
        )
        for alias in aliases:
            fixed = re.sub(
                rf'(?i)\b{re.escape(alias)}\s*\.\s*id\s*=\s*(\S+\.id_agency)\b',
                rf'{alias}.id_agency = \1',
                fixed,
            )
            fixed = re.sub(
                rf'(?i)(\S+\.id_agency)\s*=\s*{re.escape(alias)}\s*\.\s*id\b(?!_)',
                rf'\1 = {alias}.id_agency',
                fixed,
            )
        return fixed


def log_error_and_run_subagent(
    *,
    source: str,
    message: str,
    context: dict[str, Any] | None = None,
    log_dir: Path | None = None,
) -> list[ErrorFixResult]:
    """
    Registra el error en `logerrores` y ejecuta el subagente.

    Por defecto mueve archivos procesados a `logerrores/procesados` para auditoría.
    Si AGENTE_DWH_KEEP_ERROR_FILES=0, elimina archivos al terminar.
    """
    log_error_file(source=source, message=message, context=context, log_dir=log_dir)
    subagent = ErrorFixSubagent(log_dir=log_dir)
    return subagent.process_pending_files()


def run_subagent_loop(
    *,
    poll_interval_seconds: float = 2.0,
    log_dir: Path | None = None,
) -> None:
    """Mantiene el subagente corriendo y leyendo `logerrores` continuamente."""
    subagent = ErrorFixSubagent(log_dir=log_dir)
    while True:
        subagent.process_pending_files()
        time.sleep(max(0.2, poll_interval_seconds))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="agente-dwh-error-subagent",
        description="Subagente que monitorea logerrores y procesa archivos de error.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Procesa una sola vez y termina.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Intervalo de sondeo en segundos para modo continuo (default: 2).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    subagent = ErrorFixSubagent()
    if args.once:
        subagent.process_pending_files()
        return
    run_subagent_loop(poll_interval_seconds=args.interval)


if __name__ == "__main__":
    main()

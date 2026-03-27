from __future__ import annotations

import argparse
import json
import sys

from .agent import DwhAgent
from .app_services import build_agent_service
from .config import ConfigError, load_settings
from .error_subagent import log_error_and_run_subagent
from .observability import get_recent_alerts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="agente-dwh",
        description="Agente IA para consultas de solo lectura sobre un DWH.",
    )
    parser.add_argument(
        "pregunta",
        nargs="+",
        help="Pregunta en lenguaje natural para consultar el DWH.",
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=200,
        help="Límite máximo de filas por consulta (default: 200).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Imprime la respuesta en formato JSON.",
    )
    return parser.parse_args()


def _load_schema_hint(path: str) -> str:
    if not path:
        return ""
    try:
        with open(path, "r", encoding="utf-8") as file:
            return file.read().strip()
    except OSError as exc:
        raise RuntimeError(f"No se pudo leer SCHEMA_HINT_FILE={path}: {exc}") from exc


def main() -> None:
    from .bootstrap_env import load_dotenv_from_project_root

    load_dotenv_from_project_root()
    args = parse_args()
    question = " ".join(args.pregunta)

    try:
        settings = load_settings()
        if args.limite <= 0:
            raise ValueError("--limite debe ser mayor que 0.")
        schema_hint = _load_schema_hint(settings.schema_hint_file)
        agent = build_agent_service(
            dwh_url=settings.dwh_url,
            llm_endpoint=settings.llm_endpoint,
            llm_model=settings.llm_model,
            row_limit=min(args.limite, settings.max_rows),
            llm_timeout_seconds=settings.llm_timeout_seconds,
            schema_hint=schema_hint,
            cache_ttl_seconds=settings.cache_ttl_seconds,
            cache_max_entries=settings.cache_max_entries,
            llm_temperature=settings.llm_temperature,
            schema_hint_file=settings.schema_hint_file,
        )
        result = agent.answer(question=question)
    except ConfigError as exc:
        log_error_and_run_subagent(
            source="cli_config",
            message=str(exc),
            context={"question": question},
        )
        print(f"Error de configuración: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    except Exception as exc:  # noqa: BLE001
        log_error_and_run_subagent(
            source="cli_runtime",
            message=str(exc),
            context={"question": question},
        )
        print(f"Error ejecutando el agente: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    if args.json:
        payload: dict[str, object] = {
            "pregunta": result.question,
            "sql": result.generated_sql,
            "rows": result.rows,
            "cache": agent._dwh.get_cache_stats(),  # noqa: SLF001
        }
        alerts = get_recent_alerts(limit=5)
        if alerts:
            payload["alertas"] = alerts
        print(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    print("=== SQL generado ===")
    print(result.generated_sql)
    print()
    print("=== Resultado ===")
    rows = result.rows
    if not rows:
        print("Sin resultados.")
    else:
        for idx, row in enumerate(rows, start=1):
            print(f"{idx}. {row}")
    print()
    print("=== Cache ===")
    print(agent._dwh.get_cache_stats())  # noqa: SLF001


if __name__ == "__main__":
    main()

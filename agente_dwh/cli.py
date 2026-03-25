from __future__ import annotations

import argparse
import json
import sys

from .agent import DwhAgent, resolve_llm_profile
from .config import ConfigError, load_settings
from .dwh import DwhClient
from .llm_local import LocalOllamaClient
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
        dwh = DwhClient.from_url(
            settings.dwh_url,
            default_limit=min(args.limite, settings.max_rows),
            cache_ttl_seconds=settings.cache_ttl_seconds,
            cache_max_entries=settings.cache_max_entries,
        )
        llm = LocalOllamaClient(
            base_url=settings.llm_endpoint,
            model_name=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
            temperature=settings.llm_temperature,
        )
        schema_hint = _load_schema_hint(settings.schema_hint_file)
        agent = DwhAgent(
            dwh_client=dwh,
            llm_client=llm,
            schema_hint=schema_hint,
            llm_profile=resolve_llm_profile(
                settings.schema_hint_file, dwh_url=settings.dwh_url
            ),
        )
        result = agent.answer(question=question)
    except ConfigError as exc:
        print(f"Error de configuración: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    except Exception as exc:  # noqa: BLE001
        print(f"Error ejecutando el agente: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    if args.json:
        payload: dict[str, object] = {
            "pregunta": result.question,
            "sql": result.generated_sql,
            "rows": result.rows,
            "cache": dwh.get_cache_stats(),
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
    print(dwh.get_cache_stats())


if __name__ == "__main__":
    main()

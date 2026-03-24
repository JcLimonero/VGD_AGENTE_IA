from __future__ import annotations

import argparse
import concurrent.futures
import statistics
import time

from agente_dwh.demo_data import DEMO_DB_PATH, ensure_demo_db
from agente_dwh.dwh import DwhClient


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prueba de carga simple para consultas SQL de lectura.")
    parser.add_argument("--workers", type=int, default=12, help="Cantidad de hilos concurrentes.")
    parser.add_argument("--requests", type=int, default=240, help="Total de consultas a ejecutar.")
    parser.add_argument(
        "--dwh-url",
        default=f"sqlite+pysqlite:///{DEMO_DB_PATH}",
        help="URL SQLAlchemy del DWH objetivo.",
    )
    parser.add_argument(
        "--sql",
        default=(
            "SELECT year_month, SUM(total_sales) AS total_sales "
            "FROM mv_sales_monthly GROUP BY year_month ORDER BY year_month LIMIT 60;"
        ),
        help="Consulta SQL de lectura a ejecutar en bucle.",
    )
    return parser.parse_args()


def _run_once(dwh_url: str, sql: str) -> tuple[bool, float]:
    client = DwhClient.from_url(dwh_url, default_limit=200, cache_ttl_seconds=60, cache_max_entries=2000)
    start = time.perf_counter()
    try:
        client.execute_select(sql)
        return True, (time.perf_counter() - start) * 1000.0
    except Exception:  # noqa: BLE001
        return False, (time.perf_counter() - start) * 1000.0


def main() -> None:
    args = _parse_args()
    if args.workers <= 0:
        raise SystemExit("--workers debe ser > 0")
    if args.requests <= 0:
        raise SystemExit("--requests debe ser > 0")

    ensure_demo_db(str(DEMO_DB_PATH))
    start = time.perf_counter()
    latencies: list[float] = []
    ok = 0
    fail = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(_run_once, args.dwh_url, args.sql) for _ in range(args.requests)]
        for future in concurrent.futures.as_completed(futures):
            success, latency = future.result()
            latencies.append(latency)
            if success:
                ok += 1
            else:
                fail += 1

    elapsed = time.perf_counter() - start
    throughput = args.requests / elapsed if elapsed > 0 else 0.0
    avg_ms = statistics.mean(latencies) if latencies else 0.0
    p95_ms = sorted(latencies)[int(len(latencies) * 0.95) - 1] if latencies else 0.0

    print("=== Resultado load test ===")
    print(f"Requests: {args.requests}")
    print(f"Workers: {args.workers}")
    print(f"OK: {ok} | FAIL: {fail}")
    print(f"Duración total: {elapsed:.2f}s")
    print(f"Throughput: {throughput:.2f} req/s")
    print(f"Latencia promedio: {avg_ms:.2f} ms")
    print(f"Latencia p95: {p95_ms:.2f} ms")


if __name__ == "__main__":
    main()

"""Adaptador opcional para ejecutar llamadas LLM en worker dedicado."""

from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass
import queue
import threading
from typing import Any, Callable

from .llm_local import LocalOllamaClient


@dataclass
class _WorkerTask:
    func: Callable[..., Any]
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    future: Future[Any]


class WorkerLlmClient:
    """
    Ejecuta el cliente LLM en un hilo dedicado.

    Útil cuando la latencia de inferencia domina y se quiere aislar el bloqueo del hilo principal.
    """

    def __init__(self, llm_client: LocalOllamaClient) -> None:
        self._llm = llm_client
        self._queue: queue.Queue[_WorkerTask | None] = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True, name="llm-worker")
        self._thread.start()

    def _run(self) -> None:
        while True:
            task = self._queue.get()
            if task is None:
                return
            try:
                result = task.func(*task.args, **task.kwargs)
                task.future.set_result(result)
            except Exception as exc:  # noqa: BLE001
                task.future.set_exception(exc)

    def _submit(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        future: Future[Any] = Future()
        self._queue.put(_WorkerTask(func=func, args=args, kwargs=kwargs, future=future))
        return future.result()

    def generar_sql(self, prompt: str, system_prompt: str) -> str:
        return self._submit(self._llm.generar_sql, prompt, system_prompt)

    def generate_sql(self, system_prompt: str, user_prompt: str) -> str:
        return self._submit(self._llm.generate_sql, system_prompt, user_prompt)

    def generate_natural_language(self, *, system_prompt: str, user_prompt: str) -> str:
        return self._submit(
            self._llm.generate_natural_language,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

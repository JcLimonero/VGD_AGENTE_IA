"""Cliente para LLM local (Ollama)."""

from __future__ import annotations

import json
from urllib import error, request


class LLMError(RuntimeError):
    """Error al comunicarse con el LLM local."""


class LocalOllamaClient:
    """Cliente mínimo para la API /api/chat de Ollama."""

    def __init__(
        self,
        base_url: str,
        model_name: str,
        timeout_seconds: int = 60,
        *,
        temperature: float = 0.2,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds
        self._temperature = temperature

    def generate_sql(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self._model_name,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {"temperature": self._temperature},
        }
        endpoint = f"{self._base_url}/api/chat"
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self._timeout_seconds) as resp:
                body = resp.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8")
            except Exception:  # noqa: BLE001
                detail = ""
            raise LLMError(
                f"Ollama respondió HTTP {exc.code} en {endpoint}. "
                f"Detalle: {detail or str(exc)}"
            ) from exc
        except error.URLError as exc:
            raise LLMError(f"No se pudo contactar Ollama en {endpoint}: {exc}") from exc

        try:
            parsed = json.loads(body)
            content = parsed["message"]["content"]
        except (KeyError, json.JSONDecodeError) as exc:
            raise LLMError("Respuesta inválida del LLM local") from exc

        return content.strip()

    def generar_sql(self, prompt: str, system_prompt: str) -> str:
        """Alias en español para compatibilidad."""
        return self.generate_sql(system_prompt=system_prompt, user_prompt=prompt)


OllamaClient = LocalOllamaClient

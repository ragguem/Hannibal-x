"""Ollama local : rédaction (`/api/chat`, température nulle) et embeddings (`/api/embed`, bge-m3)."""

from typing import Any

import httpx

from hannibal_doctrine.application.ports import DependencyDown

DEPENDENCY = "ollama"


class OllamaChat:
    def __init__(
        self,
        base_url: str,
        *,
        model: str,
        context_window: int,
        timeout_s: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._model = model
        self._context_window = context_window
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout_s, transport=transport)

    @property
    def default_model(self) -> str:
        return self._model

    async def chat(
        self,
        system: str,
        user: str,
        *,
        model: str | None = None,
        output: str | dict[str, Any] | None = None,
        reasoning: bool | None = None,
    ) -> str:
        body: dict[str, Any] = {
            "model": model or self._model,
            "stream": False,
            "options": {"temperature": 0, "num_ctx": self._context_window},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if output is not None:
            body["format"] = output
        if reasoning is not None:
            body["think"] = reasoning
        try:
            response = await self._client.post("/api/chat", json=body)
            response.raise_for_status()
            return str((response.json().get("message") or {}).get("content") or "")
        except (httpx.HTTPError, ValueError) as error:
            raise DependencyDown(DEPENDENCY, f"rédaction : {error}") from error

    async def aclose(self) -> None:
        await self._client.aclose()


class OllamaEmbedder:
    def __init__(
        self,
        base_url: str,
        *,
        model: str,
        on_cpu: bool,
        timeout_s: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._model = model
        self._options = {"options": {"num_gpu": 0}} if on_cpu else {}
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout_s, transport=transport)

    @property
    def model_name(self) -> str:
        return self._model

    async def embed(self, text: str) -> list[float]:
        try:
            response = await self._client.post(
                "/api/embed", json={"model": self._model, "input": [text], **self._options}
            )
            response.raise_for_status()
            return [float(x) for x in response.json()["embeddings"][0]]
        except (httpx.HTTPError, ValueError, KeyError, IndexError) as error:
            raise DependencyDown(DEPENDENCY, f"embeddings : {error}") from error

    async def aclose(self) -> None:
        await self._client.aclose()

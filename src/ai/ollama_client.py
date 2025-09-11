from typing import Any, Dict, List, Optional

import httpx

from src.config import settings
from src.utils.logging import get_logger
from src.utils.observability import metrics, track_latency

logger = get_logger(__name__)


class OllamaClient:
    """CPU-friendly client for Ollama local models."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        # Reuse langextract local model name as a sensible default if no dedicated setting exists
        self.model = (
            model
            or getattr(settings, "ollama_model", None)
            or settings.langextract_local_model
        )
        self.timeout = timeout or settings.llm_timeout
        self._client: Optional[httpx.AsyncClient] = None

        self.temperature = settings.llm_temperature
        self.top_p = settings.llm_top_p
        self.max_tokens = settings.llm_max_tokens

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout))
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def health_check(self) -> bool:
        try:
            client = await self._get_client()
            # Ollama doesn't have a strict health endpoint; list local models as a proxy
            resp = await client.get(f"{self.base_url}/api/tags")
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False

    async def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
        **kwargs,
    ) -> str:
        gen_temperature = temperature if temperature is not None else self.temperature
        gen_top_p = top_p if top_p is not None else self.top_p
        gen_max_tokens = max_tokens if max_tokens is not None else self.max_tokens

        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "options": {
                "temperature": gen_temperature,
                "top_p": gen_top_p,
                "num_predict": gen_max_tokens,
            },
            "stream": False,
        }
        if stop:
            payload["stop"] = stop
        payload.update(kwargs)

        with track_latency("ollama_generation", {"model": self.model}):
            text = await self._make_request(payload)
            metrics.record_llm_usage(len(text.split()), f"ollama-{self.model}")
            return text

    async def _make_request(self, payload: Dict[str, Any]) -> str:
        client = await self._get_client()
        resp = await client.post(f"{self.base_url}/api/generate", json=payload)
        resp.raise_for_status()
        data = resp.json()
        text = data.get("response") or data.get("text") or ""
        if not text:
            raise ValueError("Empty response from Ollama")
        return text.strip()

    async def generate_with_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        # Convert chat to a simple prompt
        prompt_parts = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"Human: {content}")
            else:
                prompt_parts.append(f"Assistant: {content}")
        prompt_parts.append("Assistant:")
        prompt = "\n\n".join(prompt_parts)
        return await self.generate(
            prompt=prompt,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            **kwargs,
        )

import asyncio
from typing import Any, Dict, List, Optional

import httpx

from src.config import settings
from src.utils.logging import get_logger
from src.utils.observability import metrics, track_latency

logger = get_logger(__name__)


class GPTOSSClient:
    """Client for GPT-OSS 20B via vLLM server."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.base_url = (base_url or settings.vllm_base_url).rstrip("/")
        self.model = model or settings.gpt_oss_model
        self.timeout = timeout or settings.llm_timeout
        self._client: Optional[httpx.AsyncClient] = None

        # LLM parameters for medical responses
        self.temperature = settings.llm_temperature
        self.top_p = settings.llm_top_p
        self.max_tokens = settings.llm_max_tokens
        self.retry_attempts = settings.llm_retry_attempts
        self.retry_delay = settings.llm_retry_delay

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def health_check(self) -> bool:
        """Check if vLLM server is healthy."""
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/health")
            is_healthy = response.status_code == 200

            if is_healthy:
                logger.debug("LLM health check passed")
            else:
                logger.warning(f"LLM health check failed: {response.status_code}")

            return is_healthy
        except Exception as e:
            logger.error(f"LLM health check error: {e}")
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
        """Generate text using GPT-OSS 20B."""
        # Use instance defaults if not provided
        gen_temperature = temperature if temperature is not None else self.temperature
        gen_top_p = top_p if top_p is not None else self.top_p
        gen_max_tokens = max_tokens if max_tokens is not None else self.max_tokens

        request_payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": gen_temperature,
            "top_p": gen_top_p,
            "max_tokens": gen_max_tokens,
            "stream": False,
        }

        if stop:
            request_payload["stop"] = stop

        # Add any additional kwargs
        request_payload.update(kwargs)

        # Attempt generation with retries
        last_error = None
        for attempt in range(self.retry_attempts):
            try:
                with track_latency(
                    "llm_generation", {"model": self.model, "attempt": attempt + 1}
                ):
                    response_text = await self._make_request(request_payload)

                    # Record successful generation
                    estimated_tokens = len(response_text.split())
                    metrics.record_llm_usage(estimated_tokens, self.model)

                    logger.info(
                        "LLM generation successful",
                        extra_fields={
                            "model": self.model,
                            "prompt_length": len(prompt),
                            "response_length": len(response_text),
                            "attempt": attempt + 1,
                            "temperature": gen_temperature,
                            "top_p": gen_top_p,
                        },
                    )

                    return response_text

            except Exception as e:
                last_error = e
                logger.warning(f"LLM generation attempt {attempt + 1} failed: {e}")

                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(
                        self.retry_delay * (2**attempt)
                    )  # Exponential backoff

        # All attempts failed
        error_msg = (
            f"LLM generation failed after {self.retry_attempts} attempts: {last_error}"
        )
        logger.error(error_msg)
        metrics.record_error("llm_generation_failed", str(last_error))
        raise Exception(error_msg)

    async def _make_request(self, payload: Dict[str, Any]) -> str:
        """Make HTTP request to vLLM server."""
        client = await self._get_client()

        # Convert completions format to chat format for vLLM
        chat_payload = {
            "model": payload["model"],
            "messages": [{"role": "user", "content": payload["prompt"]}],
            "temperature": payload.get("temperature", 0.7),
            "top_p": payload.get("top_p", 1.0),
            "max_tokens": payload.get("max_tokens", 512),
            "stream": False,
        }
        
        if "stop" in payload:
            chat_payload["stop"] = payload["stop"]

        try:
            response = await client.post(
                f"{self.base_url}/completions",
                json=payload,  # Use original payload format
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

            result = response.json()

            # Extract generated text from completions format
            if "choices" in result and len(result["choices"]) > 0:
                choice = result["choices"][0]
                generated_text = choice.get("text", "").strip()
                    
                if not generated_text:
                    raise ValueError("Empty response from LLM")
                return generated_text
            else:
                raise ValueError("Invalid response format from LLM")

        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_json = e.response.json()
                error_detail = error_json.get("error", {}).get("message", str(e))
            except Exception:
                error_detail = str(e)

            raise Exception(f"HTTP {e.response.status_code}: {error_detail}")

        except httpx.RequestError as e:
            raise Exception(f"Request error: {e}")

    async def generate_with_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        """Generate using chat completion format (converts to prompt)."""
        # Convert chat messages to prompt format
        prompt = self._format_chat_prompt(messages)

        return await self.generate(
            prompt=prompt,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            **kwargs,
        )

    def _format_chat_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Convert chat messages to prompt format."""
        prompt_parts = []

        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")

            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"Human: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")

        # Add assistant prompt at the end
        prompt_parts.append("Assistant:")

        return "\n\n".join(prompt_parts)

    async def validate_response(self, response: str) -> Dict[str, Any]:
        """Validate LLM response for medical safety."""
        validation = {"is_valid": True, "warnings": [], "confidence": 1.0}

        # Basic validation checks
        if not response or len(response.strip()) < 10:
            validation["is_valid"] = False
            validation["warnings"].append("Response too short")
            validation["confidence"] = 0.0

        # Check for common problematic patterns
        concerning_phrases = [
            "i don't know",
            "i'm not sure",
            "consult a doctor",
            "seek immediate medical attention",
            "this is not medical advice",
        ]

        response_lower = response.lower()
        for phrase in concerning_phrases:
            if phrase in response_lower:
                validation["warnings"].append(f"Contains concerning phrase: {phrase}")
                validation["confidence"] *= 0.7

        # Check for medical disclaimers (good)
        if "based on medical protocols" in response_lower:
            validation["confidence"] *= 1.1

        if "source:" in response_lower or "citation:" in response_lower:
            validation["confidence"] *= 1.1

        return validation

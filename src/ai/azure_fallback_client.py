from typing import Any, Dict, List, Optional

import httpx

try:
    from ..config.enhanced_settings import get_settings
except ImportError:
    from src.config import settings
    get_settings = lambda: settings

from src.utils.logging import get_logger
from src.utils.observability import metrics, track_latency

logger = get_logger(__name__)


class AzureOpenAIClient:
    """Fallback client for Azure OpenAI (only when explicitly enabled)."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        deployment: Optional[str] = None,
        api_version: str = "2023-12-01-preview",
    ):
        # Get settings instance
        settings = get_settings()
        
        self.endpoint = (endpoint or settings.azure_openai_endpoint or "").rstrip("/")
        self.api_key = api_key or settings.azure_openai_api_key
        self.deployment = deployment or settings.azure_openai_deployment
        self.api_version = api_version
        self._client: Optional[httpx.AsyncClient] = None

        # Validate configuration
        if not all([self.endpoint, self.api_key, self.deployment]):
            self.enabled = False
            logger.warning("Azure OpenAI not configured - fallback disabled")
        else:
            self.enabled = True
            logger.info(f"Azure OpenAI client initialized: {self.deployment} at {self.endpoint}")

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                headers={"api-key": self.api_key, "Content-Type": "application/json"},
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def health_check(self) -> bool:
        """Check if Azure OpenAI is available."""
        if not self.enabled:
            return False

        # Check external calls policy
        settings = get_settings()
        if settings.disable_external_calls:
            logger.warning("Azure OpenAI blocked by DISABLE_EXTERNAL_CALLS policy")
            return False

        try:
            client = await self._get_client()
            # Test with a minimal chat completion request (GPT-4o-mini requires chat format)
            url = f"{self.endpoint}/openai/deployments/{self.deployment}/chat/completions"

            response = await client.post(
                url,
                json={
                    "messages": [{"role": "user", "content": "Hello"}],
                    "max_tokens": 1,
                    "temperature": 0
                },
                params={"api-version": self.api_version},
            )

            is_healthy = response.status_code in [
                200,
                429,
            ]  # 429 is rate limit but service is up

            if is_healthy:
                logger.debug("Azure OpenAI health check passed")
            else:
                logger.warning(
                    f"Azure OpenAI health check failed: {response.status_code} - {response.text}"
                )

            return is_healthy
        except Exception as e:
            logger.error(f"Azure OpenAI health check error: {e}")
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
        """Generate text using Azure OpenAI (fallback only)."""
        if not self.enabled:
            raise Exception("Azure OpenAI not configured")

        # Check external calls policy
        settings = get_settings()
        if settings.disable_external_calls:
            raise Exception("External calls disabled - cannot use Azure OpenAI")

        # Log PHI warning
        logger.warning(
            "Using Azure OpenAI fallback - ensure no PHI in prompt",
            extra_fields={"prompt_length": len(prompt)},
        )

        payload = {
            "prompt": prompt,
            "temperature": temperature or 0.0,
            "top_p": top_p or 0.1,
            "max_tokens": max_tokens or 1500,
            "stream": False,
        }

        if stop:
            payload["stop"] = stop

        try:
            with track_latency("azure_generation", {"deployment": self.deployment}):
                response_text = await self._make_request(payload)

                # Record usage
                estimated_tokens = len(response_text.split())
                metrics.record_llm_usage(estimated_tokens, f"azure-{self.deployment}")

                logger.info(
                    "Azure OpenAI generation successful",
                    extra_fields={
                        "deployment": self.deployment,
                        "prompt_length": len(prompt),
                        "response_length": len(response_text),
                    },
                )

                return response_text

        except Exception as e:
            logger.error(f"Azure OpenAI generation failed: {e}")
            metrics.record_error("azure_generation_failed", str(e))
            raise

    async def _make_request(self, payload: Dict[str, Any]) -> str:
        """Make request to Azure OpenAI."""
        client = await self._get_client()

        url = f"{self.endpoint}/openai/deployments/{self.deployment}/completions"

        try:
            response = await client.post(
                url, json=payload, params={"api-version": self.api_version}
            )
            response.raise_for_status()

            result = response.json()

            if "choices" in result and len(result["choices"]) > 0:
                generated_text = result["choices"][0].get("text", "").strip()
                if not generated_text:
                    raise ValueError("Empty response from Azure OpenAI")
                return generated_text
            else:
                raise ValueError("Invalid response format from Azure OpenAI")

        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_json = e.response.json()
                error_detail = error_json.get("error", {}).get("message", str(e))
            except Exception:
                error_detail = str(e)

            raise Exception(
                f"Azure OpenAI HTTP {e.response.status_code}: {error_detail}"
            )

        except httpx.RequestError as e:
            raise Exception(f"Azure OpenAI request error: {e}")

    async def generate_with_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        """Generate using chat completion (preferred for Azure)."""
        if not self.enabled:
            raise Exception("Azure OpenAI not configured")

        settings = get_settings()
        if settings.disable_external_calls:
            raise Exception("External calls disabled - cannot use Azure OpenAI")

        payload = {
            "messages": messages,
            "temperature": temperature or 0.0,
            "top_p": top_p or 0.1,
            "max_tokens": max_tokens or 1500,
            "stream": False,
        }

        try:
            with track_latency("azure_chat", {"deployment": self.deployment}):
                client = await self._get_client()
                url = f"{self.endpoint}/openai/deployments/{self.deployment}/chat/completions"

                response = await client.post(
                    url, json=payload, params={"api-version": self.api_version}
                )
                response.raise_for_status()

                result = response.json()

                if "choices" in result and len(result["choices"]) > 0:
                    message = result["choices"][0].get("message", {})
                    content = message.get("content", "").strip()
                    if not content:
                        raise ValueError("Empty response from Azure OpenAI chat")

                    # Record usage
                    if "usage" in result:
                        total_tokens = result["usage"].get("total_tokens", 0)
                        metrics.record_llm_usage(
                            total_tokens, f"azure-{self.deployment}"
                        )

                    return content
                else:
                    raise ValueError("Invalid chat response format from Azure OpenAI")

        except Exception as e:
            logger.error(f"Azure OpenAI chat generation failed: {e}")
            metrics.record_error("azure_chat_failed", str(e))
            raise
    
    async def validate_response(self, response: str) -> Dict[str, Any]:
        """
        Validate LLM response for medical safety.
        
        Args:
            response: Generated response text
            
        Returns:
            Validation result with 'is_valid', 'warnings', and 'confidence'
        """
        validation = {"is_valid": True, "warnings": [], "confidence": 1.0}
        
        if not response or len(response.strip()) < 10:
            validation["is_valid"] = False
            validation["warnings"].append("Response too short")
            validation["confidence"] = 0.0
            return validation
            
        # Check for medical safety indicators
        response_lower = response.lower()
        
        # Higher confidence for responses with sources/citations
        if "source:" in response_lower or "citation:" in response_lower or "ref:" in response_lower:
            validation["confidence"] *= 1.1
            
        # Check for medical disclaimers
        medical_disclaimers = [
            "consult", "doctor", "physician", "medical professional", 
            "emergency", "911", "not medical advice"
        ]
        if any(disclaimer in response_lower for disclaimer in medical_disclaimers):
            validation["confidence"] *= 1.05
        
        # Warn about potential medical advice without disclaimers
        medical_terms = [
            "dosage", "medication", "treatment", "diagnosis", "prescribe",
            "administer", "inject", "dose"
        ]
        if any(term in response_lower for term in medical_terms):
            if not any(disclaimer in response_lower for disclaimer in medical_disclaimers):
                validation["warnings"].append("Medical content without disclaimer")
                validation["confidence"] *= 0.9
                
        return validation

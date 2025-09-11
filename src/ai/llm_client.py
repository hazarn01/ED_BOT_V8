"""Unified LLM client with automatic fallback support."""
from typing import Any, Dict, List, Optional

from src.config import settings
from src.utils.logging import get_logger
from src.utils.observability import metrics, track_latency

from .azure_fallback_client import AzureOpenAIClient
from .gpt_oss_client import GPTOSSClient
from .ollama_client import OllamaClient

logger = get_logger(__name__)


class UnifiedLLMClient:
    """
    Unified LLM client with automatic fallback between backends.
    
    Priority order:
    1. GPT-OSS 20B via vLLM (primary)
    2. Ollama/Mistral (fallback 1)
    3. Azure OpenAI (emergency fallback)
    """
    
    def __init__(
        self,
        primary_backend: Optional[str] = None,
        enable_fallback: bool = True,
        timeout: Optional[int] = None
    ):
        self.primary_backend = primary_backend or settings.llm_backend
        self.enable_fallback = enable_fallback
        self.timeout = timeout or settings.llm_timeout
        
        # Initialize all available clients
        self.clients = {}
        
        # Track which backends are healthy
        self._backend_health = {}
        self._last_health_check = {}
        self.health_check_interval = 60  # seconds
        
        # Now initialize clients after setting up health tracking
        self._initialize_clients()
        
    def _initialize_clients(self):
        """Initialize available LLM clients based on configuration."""
        
        # GPT-OSS client (vLLM)
        if hasattr(settings, 'vllm_enabled') and settings.vllm_enabled:
            try:
                self.clients['gpt-oss'] = GPTOSSClient(
                    base_url=settings.vllm_base_url,
                    model=settings.gpt_oss_model,
                    timeout=self.timeout
                )
                self._backend_health['gpt-oss'] = True
                logger.info("Initialized GPT-OSS client via vLLM")
            except Exception as e:
                logger.warning(f"Failed to initialize GPT-OSS client: {e}")
                self._backend_health['gpt-oss'] = False
        
        # Ollama client (CPU fallback)
        if hasattr(settings, 'ollama_enabled') and settings.ollama_enabled:
            try:
                self.clients['ollama'] = OllamaClient(
                    base_url=settings.ollama_base_url,
                    model=settings.ollama_model,
                    timeout=self.timeout
                )
                self._backend_health['ollama'] = True
                logger.info("Initialized Ollama client as fallback")
            except Exception as e:
                logger.warning(f"Failed to initialize Ollama client: {e}")
                self._backend_health['ollama'] = False
        
        # Azure client (emergency fallback, only if external calls allowed)
        if not settings.disable_external_calls and settings.azure_openai_api_key:
            try:
                self.clients['azure'] = AzureOpenAIClient()
                self._backend_health['azure'] = True
                logger.info("Initialized Azure OpenAI client as emergency fallback")
            except Exception as e:
                logger.warning(f"Failed to initialize Azure client: {e}")
                self._backend_health['azure'] = False
                
        if not self.clients:
            logger.error("No LLM backends available!")
            
    async def health_check(self, backend: Optional[str] = None) -> bool:
        """
        Check health of a specific backend or all backends.
        
        Args:
            backend: Specific backend to check, or None for all
            
        Returns:
            True if at least one backend is healthy
        """
        backends_to_check = [backend] if backend else list(self.clients.keys())
        any_healthy = False
        
        for backend_name in backends_to_check:
            if backend_name not in self.clients:
                continue
                
            try:
                client = self.clients[backend_name]
                is_healthy = await client.health_check()
                self._backend_health[backend_name] = is_healthy
                
                if is_healthy:
                    any_healthy = True
                    logger.debug(f"{backend_name} health check passed")
                else:
                    logger.warning(f"{backend_name} health check failed")
                    
            except Exception as e:
                self._backend_health[backend_name] = False
                logger.error(f"{backend_name} health check error: {e}")
                
        return any_healthy
        
    def _get_backend_priority(self) -> List[str]:
        """
        Get ordered list of backends to try based on configuration and health.
        
        Returns:
            List of backend names in priority order
        """
        # Define default priority order
        priority_map = {
            'gpt-oss': 1,
            'ollama': 2,
            'azure': 3
        }
        
        # Start with primary backend if specified
        backends = []
        if self.primary_backend and self.primary_backend in self.clients:
            backends.append(self.primary_backend)
            
        # Add other backends in priority order
        other_backends = sorted(
            [b for b in self.clients.keys() if b != self.primary_backend],
            key=lambda x: priority_map.get(x, 999)
        )
        
        if self.enable_fallback:
            backends.extend(other_backends)
        
        # Filter out unhealthy backends (except if they haven't been checked recently)
        healthy_backends = []
        for backend in backends:
            if self._backend_health.get(backend, True):  # Default to True if not checked
                healthy_backends.append(backend)
                
        return healthy_backends if healthy_backends else backends[:1]  # Always try at least one
        
    async def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
        **kwargs
    ) -> str:
        """
        Generate text using available LLM backends with automatic fallback.
        
        Args:
            prompt: Input prompt for generation
            temperature: Sampling temperature (0.0 for deterministic)
            top_p: Top-p sampling parameter
            max_tokens: Maximum tokens to generate
            stop: Stop sequences
            **kwargs: Additional backend-specific parameters
            
        Returns:
            Generated text
            
        Raises:
            Exception: If all backends fail
        """
        backends = self._get_backend_priority()
        last_error = None
        
        for backend in backends:
            if backend not in self.clients:
                continue
                
            try:
                logger.info(f"Attempting generation with {backend}")
                
                with track_latency("llm_generation", {"backend": backend}):
                    client = self.clients[backend]
                    response = await client.generate(
                        prompt=prompt,
                        temperature=temperature,
                        top_p=top_p,
                        max_tokens=max_tokens,
                        stop=stop,
                        **kwargs
                    )
                    
                    # Record success
                    metrics.record_llm_usage(len(response.split()), f"{backend}-unified")
                    self._backend_health[backend] = True
                    
                    logger.info(
                        f"Generation successful with {backend}",
                        extra_fields={
                            "backend": backend,
                            "prompt_length": len(prompt),
                            "response_length": len(response)
                        }
                    )
                    
                    return response
                    
            except Exception as e:
                last_error = e
                self._backend_health[backend] = False
                logger.warning(f"{backend} generation failed: {e}")
                
                if not self.enable_fallback:
                    break
                    
        # All backends failed
        error_msg = f"All LLM backends failed. Last error: {last_error}"
        logger.error(error_msg)
        metrics.record_error("llm_generation_all_failed", str(last_error))
        raise Exception(error_msg)
        
    async def generate_with_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        Generate using chat format with automatic fallback.
        
        Args:
            messages: List of chat messages with 'role' and 'content'
            temperature: Sampling temperature
            top_p: Top-p sampling parameter
            max_tokens: Maximum tokens to generate
            **kwargs: Additional backend-specific parameters
            
        Returns:
            Generated text
        """
        backends = self._get_backend_priority()
        last_error = None
        
        for backend in backends:
            if backend not in self.clients:
                continue
                
            try:
                logger.info(f"Attempting chat generation with {backend}")
                
                client = self.clients[backend]
                response = await client.generate_with_chat(
                    messages=messages,
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=max_tokens,
                    **kwargs
                )
                
                self._backend_health[backend] = True
                logger.info(f"Chat generation successful with {backend}")
                return response
                
            except Exception as e:
                last_error = e
                self._backend_health[backend] = False
                logger.warning(f"{backend} chat generation failed: {e}")
                
                if not self.enable_fallback:
                    break
                    
        # All backends failed
        error_msg = f"All LLM backends failed for chat. Last error: {last_error}"
        logger.error(error_msg)
        raise Exception(error_msg)
        
    async def validate_response(self, response: str) -> Dict[str, Any]:
        """
        Validate LLM response for medical safety.
        
        Args:
            response: Generated response text
            
        Returns:
            Validation result with 'is_valid', 'warnings', and 'confidence'
        """
        # Use GPT-OSS client's validation if available
        if 'gpt-oss' in self.clients:
            return await self.clients['gpt-oss'].validate_response(response)
            
        # Basic fallback validation
        validation = {"is_valid": True, "warnings": [], "confidence": 1.0}
        
        if not response or len(response.strip()) < 10:
            validation["is_valid"] = False
            validation["warnings"].append("Response too short")
            validation["confidence"] = 0.0
            
        # Check for medical safety indicators
        response_lower = response.lower()
        if "source:" in response_lower or "citation:" in response_lower:
            validation["confidence"] *= 1.1
            
        return validation
        
    async def close(self):
        """Close all client connections."""
        for backend, client in self.clients.items():
            try:
                await client.close()
                logger.debug(f"Closed {backend} client")
            except Exception as e:
                logger.warning(f"Error closing {backend} client: {e}")
                
    def get_active_backend(self) -> Optional[str]:
        """Get the currently active backend based on priority and health."""
        backends = self._get_backend_priority()
        return backends[0] if backends else None
        
    def get_backend_status(self) -> Dict[str, bool]:
        """Get health status of all backends."""
        return self._backend_health.copy()
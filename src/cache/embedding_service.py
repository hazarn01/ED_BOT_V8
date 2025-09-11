"""Embedding service for semantic cache.

Provides a unified interface for generating embeddings for semantic similarity.
"""

import logging
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings."""
    
    def __init__(self, embedding_model: Optional[Any] = None):
        """Initialize embedding service.
        
        Args:
            embedding_model: Optional embedding model (sentence transformer or OpenAI client)
        """
        self.embedding_model = embedding_model
        
    async def embed(self, text: str) -> np.ndarray:
        """Generate embedding for text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as numpy array
        """
        try:
            # Use the configured embedding model
            if self.embedding_model:
                if hasattr(self.embedding_model, 'encode'):
                    # Sentence transformer style
                    embedding = self.embedding_model.encode(text)
                    if isinstance(embedding, np.ndarray):
                        return embedding
                    else:
                        return np.array(embedding)
                elif hasattr(self.embedding_model, 'embeddings'):
                    # OpenAI style
                    response = self.embedding_model.embeddings.create(
                        input=text,
                        model="text-embedding-ada-002"
                    )
                    return np.array(response.data[0].embedding)
                else:
                    logger.warning("Unknown embedding model type, using fallback")
            
            # Fallback to a simple hash-based embedding for development
            logger.warning("No embedding model available, using hash-based fallback")
            return self._hash_embedding(text)
                
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            # Return hash-based fallback embedding
            return self._hash_embedding(text)
    
    def _hash_embedding(self, text: str, dimension: int = 768) -> np.ndarray:
        """Generate a deterministic hash-based embedding for fallback.
        
        This is used when no proper embedding model is available.
        Note: This is not a real semantic embedding and should only be used
        for development/testing purposes.
        
        Args:
            text: Text to embed
            dimension: Embedding dimension
            
        Returns:
            Hash-based pseudo-embedding
        """
        import hashlib
        
        # Create multiple hash values to fill the dimension
        embeddings = []
        for i in range(0, dimension, 32):  # MD5 produces 32 hex chars
            hash_input = f"{text}_{i}"
            hash_value = hashlib.md5(hash_input.encode()).hexdigest()
            # Convert hex to floats between -1 and 1
            hash_floats = [
                (int(hash_value[j:j+2], 16) - 127.5) / 127.5
                for j in range(0, min(32, len(hash_value)), 2)
            ]
            embeddings.extend(hash_floats)
        
        # Truncate or pad to exact dimension
        if len(embeddings) > dimension:
            embeddings = embeddings[:dimension]
        elif len(embeddings) < dimension:
            embeddings.extend([0.0] * (dimension - len(embeddings)))
        
        # Normalize to unit vector
        embedding = np.array(embeddings)
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
            
        return embedding


def create_embedding_service(embedding_model: Optional[Any] = None) -> EmbeddingService:
    """Factory function to create embedding service.
    
    Args:
        embedding_model: Optional embedding model
        
    Returns:
        EmbeddingService instance
    """
    return EmbeddingService(embedding_model)
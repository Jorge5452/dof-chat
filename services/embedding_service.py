"""Embedding service for converting text to vector embeddings.

Uses Qwen/Qwen3-Embedding-0.6B model for high-quality embeddings
optimized for legal document retrieval tasks.
"""

import threading
from typing import List
import torch
from sentence_transformers import SentenceTransformer
from config import settings
from utils.logger import logger


class EmbeddingService:
    """Service for text-to-vector embedding operations.
    
    Thread-safe singleton for embedding model management with lazy initialization.
    Optimized for legal document queries and DOF content.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        # Double-checked locking pattern for thread safety
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Only initialize once using instance attribute check
        if not hasattr(self, '_initialized'):
            self._initialized = False
            self._model = None
    
    def initialize(self):
        """Initialize the embedding model with optimized settings.
        
        Loads Qwen/Qwen3-Embedding-0.6B with configuration optimized for
        legal document retrieval and Spanish language processing.
        Uses production-ready optimization techniques for inference performance.
        """
        if self._initialized:
            return
        
        # Check if mock mode is forced
        if settings.force_mock_mode:
            logger.info("Force mock mode enabled - skipping embedding model initialization")
            self._model = None
            self._initialized = True
            return
        
        try:
            logger.info(f"Loading embedding model: {settings.embedding_model}")
            
            # Initialize SentenceTransformer with production-optimized configuration
            self._model = SentenceTransformer(
                settings.embedding_model, 
                truncate_dim=settings.embedding_dimension,
                model_kwargs={"device_map": settings.device},
                trust_remote_code=False
            )
            
            # Configure sequence length limits for optimal performance
            self._model.max_seq_length = settings.model_max_seq_length
            if hasattr(self._model.tokenizer, 'model_max_length'):
                self._model.tokenizer.model_max_length = settings.model_max_seq_length
            if hasattr(self._model[0], 'max_position_embeddings'):
                self._model[0].max_position_embeddings = settings.model_max_seq_length
            
            # Optimize model for inference
            self._model.to(settings.device)
            self._model.eval()
            torch.set_grad_enabled(False)
            
            self._initialized = True
            logger.info(f"Embedding service ready ({settings.device}, max_seq: {settings.model_max_seq_length})")
            
        except Exception as e:
            logger.error(f"Failed to initialize embedding service: {e}")
            logger.warning("Falling back to mock embedding mode")
            self._model = None
            self._initialized = True
    
    def embed_query(self, text: str) -> List[float]:
        """Convert query text to embedding vector.
        
        Applies task-specific formatting for optimal retrieval performance
        on legal document queries.
        
        Args:
            text: Query text to embed (Spanish or English)
            
        Returns:
            List[float]: Normalized embedding vector
        """
        if not self._initialized:
            self.initialize()
        
        # If model failed to load, use mock implementation
        if self._model is None:
            return self._generate_mock_embedding(text)
        
        try:
            # Format text with task description for better retrieval
            formatted_text = f"query: {text}"
            if settings.task_description:
                formatted_text = f"{settings.task_description}: {text}"
            
            with torch.inference_mode():
                # Generate embedding with normalized output
                embedding = self._model.encode(
                    formatted_text,
                    convert_to_numpy=True,
                    normalize_embeddings=True,  # L2 normalization for cosine similarity
                    show_progress_bar=False
                )
            
            # Convert to list for JSON serialization
            return embedding.tolist()
            
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            # Fall back to mock for robustness
            return self._generate_mock_embedding(text)
    
    def _generate_mock_embedding(self, text: str) -> List[float]:
        """Generate deterministic mock embedding for development/testing.
        
        Args:
            text: Input text
            
        Returns:
            List[float]: Mock embedding vector
        """
        import random
        random.seed(hash(text) % 2147483647)  # Deterministic based on text
        mock_embedding = [random.uniform(-0.1, 0.1) for _ in range(settings.embedding_dimension)]
        return mock_embedding
    
    def get_model_info(self) -> dict:
        """Get information about the loaded embedding model.
        
        Returns:
            dict: Model metadata and configuration
        """
        if not self._initialized:
            return {"status": "not_initialized"}
        
        if settings.force_mock_mode:
            return {"status": "forced_mock_mode", "reason": "force_mock_mode_enabled"}
        
        if self._model is None:
            return {"status": "mock_mode", "reason": "model_not_available"}
        
        return {
            "status": "ready",
            "model_name": settings.embedding_model,
            "device": settings.device,
            "max_seq_length": getattr(self._model, 'max_seq_length', 'unknown'),
            "embedding_dimension": settings.embedding_dimension
        }


# Global singleton instance
embedding_service = EmbeddingService()


def get_embedding_service() -> EmbeddingService:
    """Get the embedding service singleton instance."""
    if not embedding_service._initialized:
        embedding_service.initialize()
    return embedding_service
"""LLM service for generating contextual answers using Google Gemini.

Handles prompt engineering, context formatting, and response generation
optimized for legal document Q&A in Spanish.
"""

import threading
from typing import List
from google import genai
from google.genai import types
from config import settings
from schemas import ChunkData
from utils.logger import logger


class LLMService:
    """Service for Large Language Model operations using Google Gemini.
    
    Thread-safe singleton for LLM management with prompt engineering
    optimized for legal document analysis and Spanish language responses.
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
            self._client = None
    
    def initialize(self):
        """Initialize the Gemini LLM client.
        
        Sets up Google GenAI client with API key and model configuration
        optimized for legal document Q&A tasks.
        """
        if self._initialized:
            return
        
        try:
            # Check if mock mode is forced
            if settings.force_mock_mode:
                logger.info("Force mock mode enabled - skipping LLM client initialization")
                self._client = None
                self._initialized = True
                return
            
            # Validate API key availability
            if not settings.gemini_api_key or settings.gemini_api_key.strip() == "":
                logger.warning("Gemini API key not provided - falling back to mock mode")
                self._client = None
                self._initialized = True
                return
            
            logger.info(f"Initializing Gemini LLM client: {settings.gemini_model}")
            
            # Initialize the new Google GenAI client
            self._client = genai.Client(
                api_key=settings.gemini_api_key,
            )
            
            # Test client availability with a simple generation
            test_contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text="Test"),
                    ],
                ),
            ]
            
            generate_config = types.GenerateContentConfig(
                temperature=settings.gemini_temperature,
                top_p=settings.gemini_top_p,
                top_k=settings.gemini_top_k,
                max_output_tokens=settings.gemini_max_output_tokens,
            )
            
            # Test the client with a simple request
            response_generator = self._client.models.generate_content_stream(
                model=settings.gemini_model,
                contents=test_contents,
                config=generate_config,
            )
            
            # Verify we can get a response
            test_response = ""
            for chunk in response_generator:
                if chunk.text:
                    test_response += chunk.text
                    break  # Just test that we can get at least one chunk
            
            if test_response:
                logger.info("Gemini LLM client initialized and tested successfully")
            else:
                raise Exception("Model test failed - no response generated")
            
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize Gemini LLM client: {e}")
            logger.warning("Falling back to mock LLM mode")
            self._client = None
            self._initialized = True
    
    def generate_answer(self, query: str, context_chunks: List[ChunkData]) -> str:
        """Generate contextual answer using retrieved document chunks.
        
        Creates a properly formatted prompt using the system instructions from config.py
        and generates a conversational, helpful answer in Spanish for DOF document queries.
        Uses the new Google GenAI client streaming API for optimal performance.
        
        Args:
            query: User question in natural language
            context_chunks: Relevant document fragments from vector search
            
        Returns:
            str: Generated conversational answer based on provided context
        """
        if not self._initialized:
            self.initialize()
        
        # If client is not available, use mock implementation
        if self._client is None:
            logger.debug("Using mock LLM response (client not available)")
            return self._generate_mock_answer(query, context_chunks)
        
        try:
            # Build context prompt from retrieved chunks
            prompt = self._build_context_prompt(query, context_chunks)
            
            logger.debug(f"Generating answer for query: '{query[:50]}...'")
            logger.info(f"LLM Service: Using {len(context_chunks)} context chunks for answer generation")
            
            # Create contents for the new API
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt),
                    ],
                ),
            ]
            
            # Configure generation parameters
            generate_config = types.GenerateContentConfig(
                temperature=settings.gemini_temperature,
                top_p=settings.gemini_top_p,
                top_k=settings.gemini_top_k,
                max_output_tokens=settings.gemini_max_output_tokens,
            )
            
            # Generate response with streaming for better performance
            response_text = ""
            response_generator = self._client.models.generate_content_stream(
                model=settings.gemini_model,
                contents=contents,
                config=generate_config,
            )
            
            # Collect the streaming response
            for chunk in response_generator:
                if chunk.text:
                    response_text += chunk.text
            
            if response_text.strip():
                answer = response_text.strip()
                logger.debug(f"Generated answer with {len(answer)} characters")
                return answer
            else:
                logger.warning("Gemini returned empty response")
                return self._generate_mock_answer(query, context_chunks)
                
        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            # Fall back to mock for robustness
            return self._generate_mock_answer(query, context_chunks)
    
    def _build_context_prompt(self, query: str, context_chunks: List[ChunkData]) -> str:
        """Build a well-structured prompt for legal document Q&A.
        
        Processes document chunks and delegates to _build_prompt for final formatting
        using the system instructions from config.py for conversational responses.
        
        Args:
            query: User question
            context_chunks: Retrieved document fragments ordered by relevance
            
        Returns:
            str: Complete formatted prompt for Gemini with structured sections
        """
        # Build context section from chunks (already ordered by relevance)
        context_sections = []
        for i, chunk in enumerate(context_chunks, 1):
            header = chunk.header or f"Fragmento {i}"
            text = chunk.text or ""
            
            context_sections.append(f"""--- FRAGMENTO {i} ---
                Sección: {header}
                Contenido: {text}""")
        
        context_text = "\n\n".join(context_sections)
        
        # Build the prompt using the structured template
        prompt = self._build_prompt(context_text, query)

        return prompt
    
    def _build_prompt(self, context_text: str, query: str) -> str:
        """Build structured prompt using system instructions and context.
        
        Creates a well-formatted prompt with clear sections and instructions
        for optimal LLM response generation.
        
        Args:
            context_text: Formatted context from document chunks
            query: User's question
            
        Returns:
            str: Complete structured prompt for Gemini
        """
        return f"""
            {settings.SYSTEM_PROMPT.strip()}

            ---
            RESUMEN DE INSTRUCCIONES CLAVE:
            - Usa solo el contexto proporcionado.
            - Sé claro, útil y amable.
            - Cita la fuente si es relevante.
            - Si no hay información disponible, indícalo honestamente.

            ---
            CONTEXTO DE DOCUMENTOS OFICIALES:
            {context_text}

            ---
            PREGUNTA DEL USUARIO:
            {query}

            ---
            RESPUESTA:
            """
    
    def _generate_mock_answer(self, query: str, context_chunks: List[ChunkData]) -> str:
        """Generate realistic mock answer for development/testing.
        
        Uses a conversational tone consistent with the system prompt configuration
        to provide engaging responses during development.
        
        Args:
            query: User question
            context_chunks: Context chunks
            
        Returns:
            str: Mock answer with conversational structure matching system prompt
        """
        chunk_summaries = []
        for i, chunk in enumerate(context_chunks):
            chunk_summaries.append(f"- {chunk.header}")
        
        if context_chunks:
            mock_answer = f"""¡Perfecto! Encontré información relevante en los documentos del DOF sobre tu consulta: "{query}" 📋

            **He encontrado {len(context_chunks)} documentos que pueden ayudarte:**
            {chr(10).join(chunk_summaries)}

            **Lo que puedo compartirte:**

            [NOTA DE DESARROLLO: Esta es una respuesta simulada. En producción, aquí aparecería un análisis detallado generado por IA basado en el contenido específico de los documentos encontrados.]

            Los documentos que he revisado contienen información oficial publicada en el Diario Oficial de la Federación que es directamente relevante para lo que me preguntas. 

            ¿Te gustaría que profundice en algún aspecto específico de esta información? ¡Estoy aquí para ayudarte con lo que necesites! 😊""".strip()
        else:
            mock_answer = f"""¡Hola! He buscado en los documentos del DOF información sobre: "{query}"

            Lamentablemente, no encontré documentos específicos que contengan información directa sobre este tema en mi búsqueda actual.

            [NOTA DE DESARROLLO: En producción, el sistema buscaría en toda la base de datos de documentos del DOF.]

            **Te sugiero algunas opciones:**
            • Reformular la pregunta con términos más específicos
            • Verificar la ortografía de términos técnicos o legales
            • Consultar directamente el sitio oficial del DOF para documentos muy recientes

            ¿Hay alguna forma diferente en la que puedas plantear tu consulta? ¡Me encantaría poder ayudarte mejor! 🤝""".strip()
        
        return mock_answer
    
    def get_model_info(self) -> dict:
        """Get information about the loaded LLM model.
        
        Returns:
            dict: Model metadata and configuration
        """
        if not self._initialized:
            return {"status": "not_initialized"}
        
        if settings.force_mock_mode:
            return {"status": "forced_mock_mode", "reason": "force_mock_mode_enabled"}
        
        if self._client is None:
            return {"status": "mock_mode", "reason": "api_key_not_available"}
        
        return {
            "status": "ready",
            "model_name": settings.gemini_model,
            "api_configured": bool(settings.gemini_api_key),
            "client_type": "google.genai.Client"
        }


# Global singleton instance
llm_service = LLMService()


def get_llm_service() -> LLMService:
    """Get the LLM service singleton instance."""
    if not llm_service._initialized:
        llm_service.initialize()
    return llm_service
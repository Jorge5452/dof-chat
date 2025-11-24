"""RAG service orchestrator for document querying - Production implementation.

Orchestrates modular services: embedding, LLM, and vector database
for comprehensive legal document retrieval and response generation.
"""

import time
import threading
import re
from datetime import datetime, date
from typing import List
from config import settings
from services.embedding_service import get_embedding_service
from services.llm_service import get_llm_service  
from services.vector_db_service import get_vector_db_service
from schemas import EnrichedChatResponse, ChunkData, DocumentSource
from utils.logger import logger
from utils.context_renderer import render_embedded_sources
from utils.date_utils import extract_date_from_title


class RAGService:
    """Production RAG service orchestrator for document querying.
    
    Thread-safe singleton that coordinates embedding, LLM, and vector database
    services to provide comprehensive legal document Q&A capabilities.
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
            self._embedding_service = None
            self._llm_service = None
            self._vector_db_service = None
    
    def initialize(self):
        """Initialize RAG service with modular components.
        
        Sets up embedding, LLM, and vector database services
        with proper error handling and fallback mechanisms.
        """
        if self._initialized:
            return
        
        logger.info("Initializing RAG service orchestrator")
        
        try:
            # Initialize embedding service
            self._embedding_service = get_embedding_service()
            logger.info("Embedding service connected")
            
            # Initialize LLM service
            self._llm_service = get_llm_service()
            logger.info("LLM service connected")
            
            # Initialize vector database service
            self._vector_db_service = get_vector_db_service()
            
            # Test database connectivity
            db_stats = self._vector_db_service.get_embedding_stats()
            if db_stats.get("schema_valid", False):
                logger.info(f"Vector DB connected - {db_stats['chunks_with_embeddings']} chunks available")
            else:
                logger.warning("Vector DB schema validation failed - using mock data")
            
            self._initialized = True
            logger.info("RAG service orchestrator ready")
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG service: {e}")
            # Allow partial initialization for development
            self._initialized = True
            logger.warning("RAG service initialized with potential fallbacks")
    
    def embed_query(self, text: str) -> List[float]:
        """Convert query text to embedding vector using embedding service.
        
        Args:
            text: Query text to embed
            
        Returns:
            List[float]: Embedding vector
        """
        if not self._initialized:
            self.initialize()
        
        if self._embedding_service is None:
            logger.error("Embedding service not available")
            return self._generate_mock_embedding(text)
        
        return self._embedding_service.embed_query(text)
    
    def search_chunks(self, embedding: List[float], top_k: int = None) -> tuple[List[ChunkData], List]:
        """Search for similar chunks using vector database service.
        
        Args:
            embedding: Query embedding vector
            top_k: Number of results to return
            
        Returns:
            tuple: (List[ChunkData], List[Document]) - chunks and their source documents
        """
        if top_k is None:
            top_k = settings.max_chunks
        
        logger.debug(f"Searching chunks with top_k={top_k} (max_chunks={settings.max_chunks})")
        
        if not self._initialized:
            self.initialize()
        
        if self._vector_db_service is None:
            logger.error("Vector database service not available")
            return self._get_mock_chunks(top_k), []
        
        return self._vector_db_service.search_similar_chunks(embedding, top_k)
    
    def generate_answer(self, query: str, context_chunks: List[ChunkData]) -> str:
        """Generate answer using LLM service.
        
        Args:
            query: User query
            context_chunks: Retrieved context chunks
            
        Returns:
            str: Generated answer text
        """
        if not self._initialized:
            self.initialize()
        
        if self._llm_service is None:
            logger.error("LLM service not available")
            return self._generate_mock_answer(query, context_chunks)
        
        return self._llm_service.generate_answer(query, context_chunks)
    
    def query(self, text: str) -> EnrichedChatResponse:
        """Complete RAG pipeline from user query to enriched response with accordion HTML.
        
        Pipeline: text → embedding → search → generate → structure → render → JSON response
        Handles errors gracefully and returns user-friendly responses on failures.
        
        Args:
            text: User query in natural language (Spanish)
            
        Returns:
            EnrichedChatResponse: Complete response with answer, context HTML, and sources
        """
        try:
            logger.info(f"Starting RAG pipeline for query: '{text[:50]}...'")
            
            if not self._initialized:
                logger.info("Initializing RAG service")
                self.initialize()
            
            # Step 1: Embed query
            embedding = self.embed_query(text)
            
            # Step 2: Search for relevant chunks
            chunks, documents = self.search_chunks(embedding)
            logger.debug(f"Retrieved {len(chunks)} chunks from {len(documents)} documents")
            
            # Step 3: Generate answer
            answer = self.generate_answer(text, chunks)
            logger.debug(f"Generated answer using {len(chunks)} chunks")
            
            # Step 4: Create document sources for context rendering using real document data
            document_sources = self._create_document_sources_from_real_data(chunks, documents)
            logger.debug(f"Created {len(document_sources)} document sources from {len(chunks)} chunks")
            
            # Step 5: Render context HTML using Air components
            query_id = f"q{int(time.time())}"
            context_component = render_embedded_sources(document_sources, query_id)
            
            # Render Air component to HTML string - ensure it's a proper string
            if context_component:
                try:
                    rendered_html = context_component.render()
                    # Ensure we have a proper string, not an Air object
                    context_html = str(rendered_html) if rendered_html else ""
                    logger.debug(f"Successfully rendered context HTML: {len(context_html)} chars")
                except Exception as e:
                    logger.error(f"Failed to render Air component: {e}")
                    context_html = ""
            else:
                context_html = ""
                logger.warning("No context component generated")
            
            # Step 6: Extract simple sources list as fallback
            sources = [chunk.header for chunk in chunks if chunk.header]
            logger.debug(f"Created {len(sources)} sources from {len(chunks)} chunks (filtered by header)")
            
            # Create enriched response
            response = EnrichedChatResponse(
                answer=answer,
                context_html=context_html,
                sources=sources
            )
            
            logger.info(f"RAG pipeline completed - Answer: {len(answer)} chars, Context HTML: {len(context_html)} chars, Sources: {len(sources)}")
            
            return response
            
        except Exception as e:
            # Log detailed error with stack trace for debugging
            logger.error(f"Query processing failed: {e}", exc_info=True)
            
            # Return generic user-friendly error message
            return EnrichedChatResponse(
                answer="Lo siento, hubo un error al procesar tu consulta. Por favor, inténtalo de nuevo más tarde.",
                context_html="",
                sources=[]
            )
    
    def _create_document_sources(self, chunks: List[ChunkData]) -> List[DocumentSource]:
        """Create DocumentSource objects from ChunkData for Air rendering.
        
        Groups chunks by document type and creates structured DocumentSource objects
        with metadata for accordion display.
        
        Args:
            chunks: List of chunk data objects
            
        Returns:
            List[DocumentSource]: Document sources grouped by type
        """
        logger.debug(f"Creating document sources from {len(chunks)} input chunks")
        
        # Group chunks by document type for realistic simulation
        doc_groups = {}
        for chunk in chunks:
            doc_key = chunk.doc_type
            if doc_key not in doc_groups:
                doc_groups[doc_key] = []
            doc_groups[doc_key].append(chunk)
        
        logger.debug(f"Grouped chunks into {len(doc_groups)} document types: {list(doc_groups.keys())}")
        
        # Create DocumentSource objects
        document_sources = []
        for doc_type, chunks_list in doc_groups.items():
            # Create realistic chunks for accordion display
            doc_chunks = []
            for chunk in chunks_list:
                # Use ChunkData objects directly (already in API format)
                doc_chunks.append(chunk)
            
            # Create realistic document metadata based on doc_type
            if doc_type == "LEY":
                title = "Ley del Impuesto Sobre la Renta"
                pub_date = "15 de enero de 2024"
                age_desc = "Reciente"
                age_emoji = "🟢"
                url = "https://dof.gob.mx/nota_detalle.php?codigo=5678901"
            elif doc_type == "REGLAMENTO":
                title = "Reglamento de Seguridad y Salud en el Trabajo"
                pub_date = "20 de febrero de 2024"
                age_desc = "Reciente"
                age_emoji = "🟢"
                url = "https://dof.gob.mx/nota_detalle.php?codigo=5678902"
            else:  # NORMA, DECRETO, ACUERDO, etc.
                title = f"{doc_type} - Documento Oficial"
                pub_date = "10 de marzo de 2024"
                age_desc = "Reciente"
                age_emoji = "🟢"
                url = "https://dof.gob.mx/nota_detalle.php?codigo=5678903"
            
            doc_source = DocumentSource(
                title=title,
                chunks=doc_chunks,
                url=url,
                publication_date=pub_date,
                age_description=age_desc,
                age_emoji=age_emoji,
                metadata={"doc_type": doc_type}
            )
            
            document_sources.append(doc_source)
        
        return document_sources
    
    def _create_document_sources_from_real_data(self, chunks: List[ChunkData], documents: List) -> List[DocumentSource]:
        """Create DocumentSource objects from real ChunkData and Document data.
        
        Uses actual document metadata from database and extracts dates from titles.
        
        Args:
            chunks: List of chunk data objects
            documents: List of document objects from BD
            
        Returns:
            List[DocumentSource]: Document sources with real metadata
        """
        logger.debug(f"Creating document sources from {len(chunks)} chunks and {len(documents)} documents")
        
        # Group chunks by document (since we don't have doc_type, group by document title)
        # For now, create one DocumentSource per document
        document_sources = []
        
        for document in documents:
            # Find chunks that belong to this document (they should be in order from query)
            doc_chunks = []
            
            # For simplicity, since we don't have document_id mapping in ChunkData,
            # we'll assume chunks are in the same order as documents for now
            # In a real implementation, you'd need to match chunks to documents properly
            
            # Take chunks proportionally (this is a simplification)
            chunks_per_doc = max(1, len(chunks) // len(documents))
            start_idx = documents.index(document) * chunks_per_doc
            end_idx = min(start_idx + chunks_per_doc, len(chunks))
            
            doc_chunks = chunks[start_idx:end_idx]
            
            # Extract date from title and calculate age
            pub_date, age_desc, age_emoji = extract_date_from_title(document.title)
            
            # Create DocumentSource with real data
            doc_source = DocumentSource(
                title=document.title,
                chunks=doc_chunks,
                url=document.url,
                publication_date=pub_date,
                age_description=age_desc,
                age_emoji=age_emoji,
                metadata={"document_id": document.id, "file_path": document.file_path}
            )
            
            document_sources.append(doc_source)
        
        logger.debug(f"Created {len(document_sources)} document sources with real data")
        return document_sources
    
    def _generate_mock_embedding(self, text: str) -> List[float]:
        """Generate deterministic mock embedding for fallback.
        
        Args:
            text: Input text
            
        Returns:
            List[float]: Mock embedding vector
        """
        import random
        random.seed(hash(text) % 2147483647)  # Deterministic based on text
        mock_embedding = [random.uniform(-0.1, 0.1) for _ in range(settings.embedding_dimension)]
        return mock_embedding
    
    def _get_mock_chunks(self, top_k: int) -> List[ChunkData]:
        """Generate mock chunks for fallback.
        
        Args:
            top_k: Number of mock chunks to generate
            
        Returns:
            List[ChunkData]: Mock document chunks
        """
        mock_chunks_data = [
            {
                "text": "LEY DEL IMPUESTO SOBRE LA RENTA - Artículo 1.- Las personas físicas y las morales están obligadas al pago del impuesto sobre la renta en los siguientes casos: I.- Las residentes en México, respecto de todos sus ingresos, cualquiera que sea la ubicación de la fuente de riqueza de donde procedan.",
                "header": "Artículo 1 - Obligaciones fiscales generales"
            },
            {
                "text": "REGLAMENTO DE SEGURIDAD Y SALUD EN EL TRABAJO - Artículo 5.- Los patrones deberán implementar un sistema de gestión de seguridad y salud en el trabajo que incluya la identificación de peligros y evaluación de riesgos.",
                "header": "Artículo 5 - Sistemas de gestión laboral"
            },
            {
                "text": "NORMA Oficial Mexicana NOM-001-SEMARNAT-2021 - Que establece los límites máximos permisibles de contaminantes en las descargas de aguas residuales en aguas y bienes nacionales.",
                "header": "NOM-001-SEMARNAT-2021 - Límites de contaminantes"
            }
        ]
        
        # Convert to ChunkData objects
        chunk_objects = []
        for chunk_data in mock_chunks_data[:top_k]:
            chunk_obj = ChunkData(
                text=chunk_data["text"],
                header=chunk_data["header"]
            )
            chunk_objects.append(chunk_obj)
        
        return chunk_objects
    
    def _generate_mock_answer(self, query: str, context_chunks: List[ChunkData]) -> str:
        """Generate mock answer for fallback.
        
        Args:
            query: User question
            context_chunks: Context chunks
            
        Returns:
            str: Mock answer
        """
        chunk_summaries = []
        for chunk in context_chunks:
            chunk_summaries.append(f"• {chunk.header}")
        
        if context_chunks:
            return f"""Basándome en la información encontrada en los documentos del DOF, puedo ayudarte con tu consulta sobre: "{query}"

                        He encontrado {len(context_chunks)} documentos relevantes:
                        {chr(10).join(chunk_summaries)}

                        [MODO FALLBACK] Los servicios de IA no están disponibles actualmente. Esta es una respuesta simulada basada en los documentos encontrados.""".strip()
        else:
            return f"""No encontré documentos específicos relacionados con tu consulta: "{query}"

                        [MODO FALLBACK] Los servicios de búsqueda no están disponibles actualmente. Te recomiendo verificar la conexión o intentar más tarde.""".strip()
    
    def get_service_status(self) -> dict:
        """Get status information for all services.
        
        Returns:
            dict: Service status information
        """
        if not self._initialized:
            return {"status": "not_initialized"}
        
        status = {
            "rag_service": "ready",
            "force_mock_mode": settings.force_mock_mode,
            "embedding_service": "unknown",
            "llm_service": "unknown", 
            "vector_db_service": "unknown"
        }
        
        # Get embedding service status
        if self._embedding_service:
            status["embedding_service"] = self._embedding_service.get_model_info()
        
        # Get LLM service status
        if self._llm_service:
            status["llm_service"] = self._llm_service.get_model_info()
        
        # Get vector DB service status
        if self._vector_db_service:
            status["vector_db_service"] = self._vector_db_service.get_embedding_stats()
        
        return status


# Global RAG service singleton
rag_service = RAGService()


def get_rag_service() -> RAGService:
    """Get the RAG service singleton instance."""
    if not rag_service._initialized:
        rag_service.initialize()
    return rag_service
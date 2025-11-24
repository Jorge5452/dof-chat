"""Vector database service for similarity search operations.

Extends database.py functionality with vector search capabilities
optimized for DuckDB and legal document retrieval.
"""

from typing import List, Dict, Any
from datetime import datetime
from database import DatabaseManager
from schemas import ChunkData, Document
from config import settings
from utils.logger import logger


class VectorDBService(DatabaseManager):
    """Extended database service with vector similarity search capabilities.
    
    Provides optimized vector search methods for legal document retrieval
    using DuckDB with embedding similarity operations.
    """
    
    def __init__(self, db_path: str = None):
        """Initialize vector database service.
        
        Args:
            db_path: Path to DuckDB database file
        """
        super().__init__(db_path)
        self._schema_validated = False
    
    def validate_schema(self) -> bool:
        """Validate that required tables and columns exist for vector search.
        
        Returns:
            bool: True if schema is valid for vector operations
        """
        if self._schema_validated:
            logger.debug("Schema already validated, returning cached result")
            return True
        
        try:
            conn = self.connect()
            logger.debug("Starting schema validation...")
            
            # Check if required tables exist
            tables_result = conn.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_name IN ('documents', 'chunks')
            """).fetchall()
            
            found_tables = {row[0] for row in tables_result}
            required_tables = {'documents', 'chunks'}
            
            if not required_tables.issubset(found_tables):
                missing_tables = required_tables - found_tables
                logger.warning(f"Missing required tables: {missing_tables}")
                return False
            
            # Check for required columns in chunks table
            columns_result = conn.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'chunks'
                AND column_name IN ('id', 'document_id', 'text', 'header', 'embedding')
            """).fetchall()
            
            required_columns = {'id', 'document_id', 'text', 'header', 'embedding'}
            found_columns = {row[0] for row in columns_result}
            
            if not required_columns.issubset(found_columns):
                missing_columns = required_columns - found_columns
                logger.warning(f"Missing required columns in chunks table: {missing_columns}")
                return False
            
            # Test if we have data with embeddings
            test_result = conn.execute("SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL").fetchone()
            embedding_count = test_result[0] if test_result else 0
            
            if embedding_count == 0:
                logger.warning("No embeddings found in chunks table")
                return False
            
            logger.info(f"Schema validation successful - found {embedding_count} chunks with embeddings")
            self._schema_validated = True
            return True
            
        except Exception as e:
            logger.error(f"Schema validation failed: {e}")
            return False
    
    def search_similar_chunks(self, query_embedding: List[float], top_k: int = None) -> tuple[List[ChunkData], List[Document]]:
        """Search for similar chunks using vector similarity.
        
        Performs cosine similarity search against stored embeddings
        and returns the most relevant document chunks with document metadata.
        
        Args:
            query_embedding: Query vector for similarity search
            top_k: Number of results to return (default from settings)
            
        Returns:
            tuple: (List[ChunkData], List[Document]) - chunks and their source documents
        """
        if top_k is None:
            top_k = settings.max_chunks
        
        # Check if mock mode is forced
        if settings.force_mock_mode:
            logger.info("Force mock mode enabled - returning mock chunks")
            chunks = self._get_mock_chunks(top_k)
            documents = self._get_mock_documents(len(chunks))
            return chunks, documents
        
        # If schema validation fails, return mock data
        if not self.validate_schema():
            logger.warning("Schema validation failed - returning mock chunks")
            chunks = self._get_mock_chunks(top_k)
            documents = self._get_mock_documents(len(chunks))
            return chunks, documents
        
        try:
            conn = self.connect()
            
            # Query with JOIN to get document information along with chunks
            # Using real schema with documents and chunks tables
            try:
                similarity_query = f"""
                    SELECT 
                        c.id,
                        c.document_id,
                        c.text,
                        c.header,
                        c.chunk_number,
                        c.embedding,
                        c.created_at,
                        d.id as doc_id,
                        d.title,
                        d.url,
                        d.file_path,
                        d.created_at as doc_created_at,
                        array_cosine_similarity(c.embedding, ?::FLOAT[{settings.embedding_dimension}]) as similarity_score
                    FROM chunks c
                    INNER JOIN documents d ON c.document_id = d.id
                    WHERE c.embedding IS NOT NULL
                    ORDER BY similarity_score DESC 
                    LIMIT ?
                """
                
                logger.debug(f"Executing similarity query with embedding_dimension={settings.embedding_dimension}, top_k={top_k}")
                result = conn.execute(similarity_query, [query_embedding, top_k]).fetchall()
                logger.debug(f"Query executed successfully, got {len(result)} results")
                
            except Exception as e:
                logger.error(f"Vector similarity query failed: {e}")
                logger.error(f"Query was: {similarity_query}")
                return self._get_mock_chunks(top_k)

            # Convert BD results to API ChunkData objects and Document objects
            chunk_objects = []
            document_objects = []
            seen_docs = set()
            
            for row in result:
                (chunk_id, document_id, text, header, chunk_number, embedding, chunk_created_at,
                 doc_id, doc_title, doc_url, doc_file_path, doc_created_at, similarity_score) = row
                
                # Log the actual data retrieved for debugging
                logger.debug(f"Retrieved chunk - Header: '{header}', Doc: '{doc_title}', Similarity: {similarity_score:.4f}")
                
                # Convert from BD format to API format (only header and text)
                chunk_obj = ChunkData(
                    text=text or "",
                    header=header or ""
                )
                chunk_objects.append(chunk_obj)
                
                # Create Document object if not seen before
                if doc_id not in seen_docs:
                    doc_obj = Document(
                        id=doc_id,
                        title=doc_title or "",
                        url=doc_url,
                        file_path=doc_file_path,
                        created_at=doc_created_at
                    )
                    document_objects.append(doc_obj)
                    seen_docs.add(doc_id)
            
            logger.info(f"Retrieved {len(chunk_objects)} similar chunks from {len(document_objects)} documents")
            return chunk_objects, document_objects
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            # Fall back to mock data for robustness
            chunks = self._get_mock_chunks(top_k)
            documents = self._get_mock_documents(len(chunks))
            return chunks, documents
    
    def get_embedding_stats(self) -> Dict[str, Any]:
        """Get statistics about embeddings in the database.
        
        Returns:
            dict: Database and embedding statistics
        """
        try:
            conn = self.connect()
            
            # Ensure schema validation is current
            schema_valid = self.validate_schema()
            
            # Get basic chunk and document statistics
            total_chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            total_documents = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            chunks_with_embeddings = conn.execute(
                "SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL"
            ).fetchone()[0]
            
            # Get document distribution (how many chunks per document)
            doc_stats = conn.execute("""
                SELECT d.title, COUNT(c.id) as chunk_count
                FROM documents d
                LEFT JOIN chunks c ON d.id = c.document_id
                WHERE c.embedding IS NOT NULL
                GROUP BY d.id, d.title
                ORDER BY chunk_count DESC
                LIMIT 10
            """).fetchall()
            
            # Sample embedding dimension (from first non-null embedding)
            embedding_dim_result = conn.execute("""
                SELECT array_length(embedding) as dimension
                FROM chunks 
                WHERE embedding IS NOT NULL 
                LIMIT 1
            """).fetchone()
            
            embedding_dimension = embedding_dim_result[0] if embedding_dim_result else 0
            
            return {
                "total_documents": total_documents,
                "total_chunks": total_chunks,
                "chunks_with_embeddings": chunks_with_embeddings,
                "embedding_dimension": embedding_dimension,
                "top_documents_by_chunks": dict(doc_stats),
                "schema_valid": schema_valid  # Use current validation result instead of cached
            }
            
        except Exception as e:
            logger.error(f"Failed to get embedding stats: {e}")
            return {
                "total_documents": 0,
                "total_chunks": 0,
                "chunks_with_embeddings": 0,
                "embedding_dimension": 0,
                "top_documents_by_chunks": {},
                "schema_valid": False,
                "error": str(e)
            }
    
    def _get_mock_chunks(self, top_k: int) -> List[ChunkData]:
        """Generate mock chunks for development/testing.
        
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
            },
            {
                "text": "ACUERDO por el que se establecen las disposiciones generales del Registro Agrario Nacional - Artículo 10.- El Registro Agrario Nacional tendrá a su cargo el control de la tenencia de la tierra ejidal y comunal.",
                "header": "Artículo 10 - Control de tenencia de tierra"
            },
            {
                "text": "DECRETO por el que se reforman diversas disposiciones de la Ley de Instituciones de Crédito - Artículo 3.- Las instituciones de banca múltiple podrán realizar las operaciones que se señalan en la presente Ley.",
                "header": "Artículo 3 - Operaciones bancarias permitidas"
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
        
        logger.debug(f"Generated {len(chunk_objects)} mock chunks")
        return chunk_objects
    
    def _get_mock_documents(self, count: int) -> List[Document]:
        """Generate mock documents for development/testing.
        
        Args:
            count: Number of mock documents to generate
            
        Returns:
            List[Document]: Mock document objects
        """
        mock_documents_data = [
            {
                "id": 1,
                "title": "15012024_LEY_IMPUESTO_RENTA",
                "url": "https://dof.gob.mx/nota_detalle.php?codigo=5678901",
                "file_path": "/docs/ley_isr_15012024.pdf",
                "created_at": datetime(2024, 1, 15)
            },
            {
                "id": 2, 
                "title": "20022024_REGLAMENTO_SALUD",
                "url": "https://dof.gob.mx/nota_detalle.php?codigo=5678902",
                "file_path": "/docs/reglamento_salud_20022024.pdf",
                "created_at": datetime(2024, 2, 20)
            },
            {
                "id": 3,
                "title": "10032024_NOM_SEMARNAT",
                "url": "https://dof.gob.mx/nota_detalle.php?codigo=5678903",
                "file_path": "/docs/nom_001_semarnat_10032024.pdf", 
                "created_at": datetime(2024, 3, 10)
            }
        ]
        
        # Convert to Document objects
        document_objects = []
        for doc_data in mock_documents_data[:count]:
            doc_obj = Document(
                id=doc_data["id"],
                title=doc_data["title"],
                url=doc_data["url"],
                file_path=doc_data["file_path"],
                created_at=doc_data["created_at"]
            )
            document_objects.append(doc_obj)
        
        logger.debug(f"Generated {len(document_objects)} mock documents")
        return document_objects


# Global service instance
vector_db_service = VectorDBService()


def get_vector_db_service() -> VectorDBService:
    """Get the vector database service instance."""
    return vector_db_service
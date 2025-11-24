"""Configuration module for dof-chat application."""

from pydantic import field_validator
try:
    from pydantic_settings import BaseSettings
except ImportError:
    # Fallback for older pydantic versions or missing pydantic-settings
    from pydantic import BaseModel as BaseSettings


class Settings(BaseSettings):
    """Application settings using Pydantic Settings."""
    
    # ═══════════════════════════════════════════════════════════════════
    # DATABASE CONFIGURATION
    # ═══════════════════════════════════════════════════════════════════
    database_path: str = "dof_db/db.duckdb"
    
    # ═══════════════════════════════════════════════════════════════════
    # LLM CONFIGURATION - Google Gemini
    # ═══════════════════════════════════════════════════════════════════
    # API Configuration
    gemini_api_key: str = ""  # Will use mock responses in development
    gemini_model: str = "gemini-2.5-flash-lite"  # Updated model compatible with new API
    
    # Generation Parameters
    gemini_temperature: float = 0.3  # Slightly higher temperature for more natural conversation
    gemini_top_p: float = 0.9  # Allow diverse vocabulary for friendly responses
    gemini_top_k: int = 40  # Reasonable diversity in word choice
    gemini_max_output_tokens: int = 1024  # Allow longer, more detailed responses
    
    # System Prompt - Conversational behavior for DOF documents
    SYSTEM_PROMPT: str = """
        Eres un asistente conversacional experto en documentos del Diario Oficial de la Federación (DOF).
        Tu objetivo es ayudar al usuario a comprender la información contenida en estos documentos
        de forma clara, útil y confiable.

        == COMPORTAMIENTO GENERAL ==
        - Sé conversacional, empático y profesional.
        - Usa un tono cercano y amable, pero evita ser excesivamente informal.
        - Prioriza siempre la precisión y la claridad sobre la extensión.
        - Si no existe información en el contexto que responda a la pregunta, dilo de forma honesta.

        == USO DEL CONTEXTO ==
        - Usa únicamente la información disponible en el contexto proporcionado.
        - Si el contexto incluye varios documentos, indica de cuál proviene la información relevante.
        - Puedes hacer inferencias simples o relaciones entre partes del contexto, pero sin inventar datos.
        - Si hay ambigüedad, explica tus supuestos brevemente.

        == ESTILO DE RESPUESTA ==
        - Explica con lenguaje natural, evitando tecnicismos innecesarios.
        - Menciona los nombres o títulos de documentos oficiales cuando sea relevante.
        - Usa viñetas o párrafos breves para mejorar la lectura.
        - No usar emojis.
        - Cierra invitando al usuario a solicitar más detalles o aclaraciones.

        == FORMATO ==
        Responde en formato markdown, con subtítulos o listas cuando ayuden a la comprensión.
        No repitas la pregunta del usuario, y evita hacer citas textuales extensas a menos que sean necesarias.
        """
    
    # ═══════════════════════════════════════════════════════════════════
    # EMBEDDING MODEL CONFIGURATION - Qwen Embedding
    # ═══════════════════════════════════════════════════════════════════
    embedding_model: str = "Qwen/Qwen3-Embedding-0.6B"
    embedding_dimension: int = 1024
    model_max_seq_length: int = 1024
    device: str = "cpu"  # Computing device for embedding model
    
    # Task description for Qwen model instruction
    task_description: str = "Retrieve relevant legal document fragments including text, image descriptions, and table content that match the query"
    
    # ═══════════════════════════════════════════════════════════════════
    # RAG SYSTEM CONFIGURATION
    # ═══════════════════════════════════════════════════════════════════
    max_chunks: int = 5  # Maximum number of document chunks to retrieve
    
    # ═══════════════════════════════════════════════════════════════════
    # APPLICATION CONFIGURATION
    # ═══════════════════════════════════════════════════════════════════
    app_name: str = "DOF Chat"
    debug: bool = True
    session_secret_key: str = "change-me-in-production"
    
    # Development and Testing Configuration
    force_mock_mode: bool = False  # Set to True to force all services to use mocks
    
    # ═══════════════════════════════════════════════════════════════════
    # VALIDATION RULES
    # ═══════════════════════════════════════════════════════════════════
    
    # NOTE: Commented for development - enable for production deployment
    # @field_validator('gemini_api_key')
    # @classmethod
    # def validate_gemini_api_key(cls, v):
    #     """Validate that Gemini API key is provided and not empty."""
    #     if not v or v.strip() == "":
    #         raise ValueError(
    #             "Gemini API key is required. Please set GEMINI_API_KEY environment variable "
    #             "or provide it in the .env file. Get your API key from: "
    #             "https://makersuite.google.com/app/apikey"
    #         )
    #     return v.strip()
    
    @field_validator('session_secret_key')
    @classmethod
    def validate_session_secret(cls, v):
        """Warn if using default session secret in production."""
        if v == "change-me-in-production" and not cls.model_config.get("debug", True):
            import warnings
            warnings.warn(
                "Using default session secret key in production. "
                "Please set SESSION_SECRET_KEY environment variable with a secure random value.",
                UserWarning
            )
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
"""Pydantic schemas for API data validation and serialization.

Defines all data models for the DOF Chat application:
- Database models: Document, Chunk for direct BD mapping
- API models: ChunkData, DocumentSource for API operations
- Response models: ChatResponse, EnrichedChatResponse for API outputs  
- Request models: ChatQuery for API inputs
- Utility models: HealthCheck for monitoring
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


# ================================
# DATABASE SCHEMAS - Direct mapping to BD tables  
# ================================

class Document(BaseModel):
    """Direct mapping to documents table in database.
    
    Represents document metadata as stored in BD with all fields
    matching the real table structure.
    """
    
    id: Optional[int] = Field(
        default=None,
        description="Primary key from documents table"
    )
    title: str = Field(
        ...,
        description="Document title as stored in BD"
    )
    url: Optional[str] = Field(
        default=None,
        description="Unique URL to original document"
    )
    file_path: Optional[str] = Field(
        default=None,
        description="Path to document file if locally stored"
    )
    created_at: Optional[datetime] = Field(
        default=None,
        description="Document creation timestamp in BD"
    )


# ================================
# API SCHEMAS - For user interface and operations
# ================================


class ChunkData(BaseModel):
    """Individual text fragment from retrieved documents.
    
    Represents a text chunk with metadata for display
    in accordion components.
    """
    
    text: str = Field(
        ...,
        description="Content text of the document fragment"
    )
    header: str = Field(
        default="",
        description="Section header or title for the fragment"
    )


class DocumentSource(BaseModel):
    """Complete document with multiple text chunks and metadata.
    
    Represents a source document for accordion display with title,
    chunks, publication info, and age indicators.
    """
    
    title: str = Field(
        ...,
        description="Document title or identifier"
    )
    chunks: List[ChunkData] = Field(
        default_factory=list,
        description="List of relevant fragments from this document"
    )
    url: Optional[str] = Field(
        default=None,
        description="URL to the original document"
    )
    publication_date: Optional[str] = Field(
        default=None,
        description="Publication date in DOF"
    )
    age_description: Optional[str] = Field(
        default=None,
        description="Human-readable age description"
    )
    age_emoji: Optional[str] = Field(
        default=None,
        description="Emoji indicator for document age"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional document metadata"
    )


class EnrichedChatResponse(BaseModel):
    """Complete API response with generated answer and accordion HTML context.
    
    Main response model for chat endpoint, includes both textual answer
    and rich HTML with interactive source accordions.
    """
    
    answer: str = Field(
        ...,
        description="Generated answer based on retrieved context"
    )
    context_html: Optional[str] = Field(
        default=None,
        description="Rendered HTML with interactive source accordions"
    )
    sources: List[str] = Field(
        default_factory=list,
        description="List of source document headers or references (fallback)"
    )


class ChatQuery(BaseModel):
    """User input validation for chat requests.
    
    Validates user text input with length constraints (1-1000 chars)
    for the chat API endpoint.
    """
    
    text: str = Field(
        ..., 
        min_length=1, 
        max_length=1000,
        description="User question or query text"
    )


class ChatResponse(BaseModel):
    """Basic chat response with answer and source list.
    
    Simpler response model without HTML context for lightweight usage.
    Maintained for backward compatibility.
    """
    
    answer: str = Field(
        ...,
        description="Generated answer based on retrieved context"
    )
    sources: List[str] = Field(
        default_factory=list,
        description="List of source document headers or references"
    )
    
    
class HealthCheck(BaseModel):
    """Service health check response for monitoring systems.
    
    Standard health status format for load balancers, deployment validation,
    and service discovery.
    """
    
    status: str = Field(default="ok")
    service: str = Field(default="dof-chat")
    version: str = Field(default="0.1.0")
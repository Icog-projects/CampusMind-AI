from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class ExtractedPage(BaseModel):
    """Represents text extracted from a specific page or section."""
    page_number: Optional[int] = None
    text: str

# Represents the raw extraction result from a document.
class ExtractedDocument(BaseModel):
    document_id: str
    document_name: str
    pages: List[ExtractedPage] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

# Traceability metadata for each generated chunk.
class ChunkMetadata(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    document_id: str = Field(..., alias="documentId")
    document_name: str = Field(..., alias="documentName")
    chunk_id: str = Field(..., alias="chunkId")
    chunk_index: int = Field(..., alias="chunkIndex")
    chunking_method: str = Field(..., alias="chunkingMethod")
    page_number: Optional[int] = Field(None, alias="pageNumber")
    token_count_approx: Optional[int] = Field(None, alias="tokenCountApprox")
    character_count: int = Field(..., alias="characterCount")

# A processed chunk of text with complete provenance metadata.
class Chunk(BaseModel):
    content: str
    metadata: ChunkMetadata

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "metadata": self.metadata.model_dump(by_alias=True)
        }

# A processed chunk paired with its 384-dimensional dense vector.
class EmbeddedChunk(BaseModel):
    chunk: Chunk
    embedding: List[float]

    @property
    def vector_dimension(self) -> int:
        return len(self.embedding)

# A chunk paired with its retrieval relevance score and retrieval method.
class ScoredChunk(BaseModel):
    chunk: Chunk
    score: float
    retrieval_method: str = "bm25"


# Structured citation metadata mapped to an evidence source.
class SourceCitation(BaseModel):
    citation_index: int
    document_id: str
    document_name: str
    page_number: Optional[int] = None
    chunk_id: str
    chunk_index: int
    content_snippet: str


# Grounded LLM response including generated text, sources, and metadata.
class GroundedAnswer(BaseModel):
    answer: str
    sources: List[SourceCitation] = Field(default_factory=list)
    has_sufficient_context: bool = True
    model_name: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None


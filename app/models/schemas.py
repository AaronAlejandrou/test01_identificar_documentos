from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class DocumentSplitResponse(BaseModel):
    document_id: str
    filename: str
    total_pages: int
    pages: List[str]  # URLs to access the rendered pages

class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float

class DetectedBlock(BaseModel):
    type: str  # "text", "radio", "signature"
    bbox: BoundingBox
    content: Optional[str] = None  # Text content if text block
    confidence: Optional[float] = None

class DetectionResponse(BaseModel):
    document_id: str
    page_index: int
    blocks: List[DetectedBlock]

class ExtractionSaveRequest(BaseModel):
    document_id: str
    profile_name: str
    data: Dict[str, Any]

class ExtractionSaveResponse(BaseModel):
    id: str
    status: str
    message: str

class ProfileSaveRequest(BaseModel):
    profile_name: str
    profile_data: Dict[str, Any]
    templates: Dict[str, Dict[str, Any]] # template_name -> template_data

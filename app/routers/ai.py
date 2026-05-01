import os
from fastapi import APIRouter, HTTPException
from app.models.schemas import DetectionResponse
from app.services.ai_service import detect_blocks_in_image
from app.core.config import settings

router = APIRouter()

@router.post("/detect/{document_id}/{page_index}", response_model=DetectionResponse)
async def detect_blocks(document_id: str, page_index: int):
    """
    Corre el motor de IA para detectar áreas de interés (textos, radios) en una página ya renderizada.
    (Paso 2 del Studio Flow)
    """
    image_path = os.path.join(settings.UPLOAD_DIR, document_id, f"page_{page_index}.png")
    
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Imagen no encontrada")
        
    try:
        blocks = detect_blocks_in_image(image_path)
        return DetectionResponse(
            document_id=document_id,
            page_index=page_index,
            blocks=blocks
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

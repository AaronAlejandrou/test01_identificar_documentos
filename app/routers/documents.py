import os
import shutil
import tempfile
from fastapi import APIRouter, File, UploadFile, HTTPException
from app.services.pdf_service import split_pdf_to_images
from app.models.schemas import DocumentSplitResponse

router = APIRouter()

@router.post("/split", response_model=DocumentSplitResponse)
async def split_document(file: UploadFile = File(...)):
    """
    Recibe un PDF, lo divide en imágenes y retorna la estructura del documento.
    (Paso 1 del Studio Flow)
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF")

    temp_dir = tempfile.mkdtemp()
    temp_pdf_path = os.path.join(temp_dir, file.filename)
    
    try:
        with open(temp_pdf_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        result = split_pdf_to_images(temp_pdf_path)
        
        return DocumentSplitResponse(
            document_id=result["document_id"],
            filename=file.filename,
            total_pages=result["total_pages"],
            pages=result["pages"]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
        os.rmdir(temp_dir)

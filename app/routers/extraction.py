import os
import shutil
import tempfile
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from app.services.storage_service import save_extraction, get_extraction
from app.services.extract_pack import process_pack, process_single_page
from app.core.config import settings

router = APIRouter()

@router.post("/run")
async def run_extraction(
    file: UploadFile = File(...),
    profile: str = Form("document_profile_solicitud_digital.json")
):
    """
    Ejecuta la extracción de datos sobre un documento PDF usando un perfil específico.
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF")

    temp_dir = tempfile.mkdtemp()
    temp_pdf_path = os.path.join(temp_dir, file.filename)
    
    try:
        with open(temp_pdf_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        profile_path = os.path.join(settings.CONFIG_DIR, profile)
        
        if not os.path.exists(profile_path):
            raise HTTPException(status_code=404, detail=f"Perfil {profile} no encontrado")
            
        result = process_pack(pdf_path=temp_pdf_path, profile_path=profile_path)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
        os.rmdir(temp_dir)

@router.post("/run_page")
async def run_page_extraction(
    file: UploadFile = File(...),
    profile: str = Form(...),
    page_index: int = Form(...)
):
    """
    Ejecuta la extracción de datos sobre una única página del PDF.
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF")

    temp_dir = tempfile.mkdtemp()
    temp_pdf_path = os.path.join(temp_dir, file.filename)
    
    try:
        with open(temp_pdf_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        profile_path = os.path.join(settings.CONFIG_DIR, profile)
        
        if not os.path.exists(profile_path):
            raise HTTPException(status_code=404, detail=f"Perfil {profile} no encontrado")
            
        result = process_single_page(pdf_path=temp_pdf_path, profile_path=profile_path, page_index=page_index)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
        os.rmdir(temp_dir)

@router.post("/save")
async def save_extraction_result(data: dict):
    """
    Guarda el resultado verificado/editado por el usuario en el sistema.
    """
    try:
        doc_id = data.get("document_id", "unknown")
        profile = data.get("profile", "unknown")
        extraction_data = data.get("data", {})
        
        ext_id = save_extraction(doc_id, profile, extraction_data)
        return {"status": "success", "extraction_id": ext_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{extraction_id}")
async def get_extraction_result(extraction_id: str):
    """Consulta una extracción previa por su ID."""
    result = get_extraction(extraction_id)
    if not result:
        raise HTTPException(status_code=404, detail="Extracción no encontrada")
    return result

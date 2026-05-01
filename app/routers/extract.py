import os
import shutil
import tempfile
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from pydantic import BaseModel
from typing import Optional

from extract_pack import process_pack

router = APIRouter()

@router.post("/")
async def extract_document(
    file: UploadFile = File(...),
    profile: str = Form("document_profile_solicitud_digital.json")
):
    """
    Sube un archivo PDF, lo procesa con el perfil seleccionado y devuelve la información extraída (JSON).
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF")

    # Guardar archivo temporal
    temp_dir = tempfile.mkdtemp()
    temp_pdf_path = os.path.join(temp_dir, file.filename)
    
    try:
        with open(temp_pdf_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Determinar el profile path
        # Asumiendo que config está en el directorio superior
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        profile_path = os.path.join(base_dir, "config", profile)
        
        if not os.path.exists(profile_path):
            raise HTTPException(status_code=404, detail=f"Perfil de configuración {profile} no encontrado")
            
        # Procesar
        # process_pack retorna el final_json
        result = process_pack(pdf_path=temp_pdf_path, profile_path=profile_path)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Limpiar
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
        os.rmdir(temp_dir)

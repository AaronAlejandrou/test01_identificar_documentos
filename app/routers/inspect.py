import os
import tempfile
import shutil
import cv2
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from fastapi.responses import Response

from app.services.inspect_blocks import load_config, render_page, draw_overlay

router = APIRouter()

@router.post("/")
async def inspect_document(
    file: UploadFile = File(...),
    config_file: str = Form("page_01_solicitud_principal.json"),
    page: int = Form(1),
    dpi: int = Form(200)
):
    """
    Sube un PDF, y renderiza una página con los bounding boxes dibujados según la configuración.
    Ideal para inspección visual y para conectar con la UI de calibración.
    """
    if not file.filename.lower().endswith('.pdf') and not file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF o Imagen")

    temp_dir = tempfile.mkdtemp()
    temp_file_path = os.path.join(temp_dir, file.filename)
    
    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(base_dir, "config", config_file)
        
        if not os.path.exists(config_path):
            raise HTTPException(status_code=404, detail=f"Configuración {config_file} no encontrada")
            
        cfg = load_config(config_path)
        can_w = int(cfg["canonical"]["width"])
        can_h = int(cfg["canonical"]["height"])

        # Renderizar pagina (0-indexed en inspect_blocks.py pero page param es 1-indexed)
        img = render_page(temp_file_path, page - 1, dpi, can_w, can_h)
        overlay = draw_overlay(img, cfg)
        
        # Convertir a bytes para respuesta HTTP
        is_success, buffer = cv2.imencode(".png", overlay)
        if not is_success:
            raise HTTPException(status_code=500, detail="Error al codificar imagen")
            
        return Response(content=buffer.tobytes(), media_type="image/png")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        os.rmdir(temp_dir)

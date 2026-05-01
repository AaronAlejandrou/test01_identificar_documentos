import os
import json
from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any, List
from app.models.schemas import ProfileSaveRequest
from app.services.storage_service import save_profile_and_templates
from app.core.config import settings

router = APIRouter()

@router.get("/")
def list_configs():
    """Lista todos los archivos de configuración disponibles en la carpeta config."""
    if not os.path.exists(settings.CONFIG_DIR):
        return []
    files = [f for f in os.listdir(settings.CONFIG_DIR) if f.endswith(".json")]
    return files

@router.get("/{filename}")
def get_config(filename: str):
    """Obtiene el contenido de un archivo de configuración específico."""
    if not filename.endswith(".json"):
        filename += ".json"
        
    filepath = os.path.join(settings.CONFIG_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Configuración no encontrada")
        
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/profile")
def save_profile(request: ProfileSaveRequest):
    """Guarda un perfil maestro junto con todas sus plantillas de página desde el Studio."""
    try:
        save_profile_and_templates(request.profile_name, request.profile_data, request.templates)
        return {"status": "success", "message": "Perfil y plantillas guardadas correctamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{filename}")
def update_config(filename: str, config_data: Dict[str, Any] = Body(...)):
    """Actualiza o crea un archivo de configuración individual."""
    if not filename.endswith(".json"):
        filename += ".json"
        
    filepath = os.path.join(settings.CONFIG_DIR, filename)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        return {"status": "success", "message": f"Configuración {filename} actualizada"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

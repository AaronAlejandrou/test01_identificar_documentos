import os
import json
import uuid
from app.core.config import settings
from typing import Dict, Any

def save_extraction(document_id: str, profile_name: str, data: Dict[str, Any]) -> str:
    """Guarda un resultado de extracción en el disco como JSON."""
    extraction_id = f"ext_{uuid.uuid4().hex[:8]}"
    filepath = os.path.join(settings.EXTRACTION_DIR, f"{extraction_id}.json")
    
    payload = {
        "extraction_id": extraction_id,
        "document_id": document_id,
        "profile": profile_name,
        "data": data
    }
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        
    return extraction_id

def get_extraction(extraction_id: str) -> Dict[str, Any]:
    """Obtiene una extracción guardada por su ID."""
    filepath = os.path.join(settings.EXTRACTION_DIR, f"{extraction_id}.json")
    if not os.path.exists(filepath):
        return None
        
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def save_profile_and_templates(profile_name: str, profile_data: Dict[str, Any], templates: Dict[str, Dict[str, Any]]):
    """Guarda un documento master profile y todas sus plantillas hijas."""
    # Guardar profile
    profile_path = os.path.join(settings.CONFIG_DIR, f"{profile_name}.json")
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(profile_data, f, ensure_ascii=False, indent=2)
        
    # Guardar templates
    for tmpl_name, tmpl_data in templates.items():
        tmpl_path = os.path.join(settings.CONFIG_DIR, f"{tmpl_name}.json")
        with open(tmpl_path, "w", encoding="utf-8") as f:
            json.dump(tmpl_data, f, ensure_ascii=False, indent=2)

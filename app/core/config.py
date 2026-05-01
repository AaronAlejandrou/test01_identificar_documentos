import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "API Extracción de Datos PRO"
    VERSION: str = "1.0.0"
    
    # Directorios Base
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DATA_DIR: str = os.path.join(BASE_DIR, "data")
    UPLOAD_DIR: str = os.path.join(DATA_DIR, "uploads")
    EXTRACTION_DIR: str = os.path.join(DATA_DIR, "extractions")
    CONFIG_DIR: str = os.path.join(BASE_DIR, "config")
    
    # Configuración de renderizado
    DEFAULT_DPI: int = 200
    CANONICAL_WIDTH: int = 1654
    CANONICAL_HEIGHT: int = 2339

settings = Settings()

# Crear directorios si no existen
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.EXTRACTION_DIR, exist_ok=True)
os.makedirs(settings.CONFIG_DIR, exist_ok=True)

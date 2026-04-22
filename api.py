import os
import shutil
from typing import Dict, Any

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from extract_local import create_ocr_engine
from extract_pack import process_pack

# Motor de OCR global para reusarlo en todas las peticiones
ocr_engine_global = None

async def lifespan(app: FastAPI):
    # Setup al inicializar el servidor
    global ocr_engine_global
    print("Iniciando servicio... Cargando modelo PaddleOCR en memoria compartida. Esto tomará unos segundos...")
    ocr_engine_global = create_ocr_engine()
    print("Modelo cargado correctamente. Listo para recibir peticiones.")
    yield
    # Cleanup al apagar (si fuera necesario)
    print("Deteniendo servicio...")
    
app = FastAPI(
    title="Interseguro OCR API",
    description="Endpoint de extracción PDF usando PaddleOCR y reglas de form blocks.",
    version="1.0.0",
    lifespan=lifespan
)

@app.post("/api/v1/extract", summary="Sube un archivo PDF de Interseguro y extrae su información")
async def extract_document(file: UploadFile = File(...)) -> Dict[str, Any]:
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="El archivo provisto no es un PDF")
        
    temp_pdf_path = f"temp_{file.filename}"
    
    try:
        # 1. Guardar temporalmente en el sistema de archivos del servidor
        with open(temp_pdf_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        profile_path = "config/document_profile_solicitud_digital.json"
        
        # 2. Iniciar extracción
        # Le pasamos el ocr_engine instanciado globalmente para mucha mayor rapidez
        result_json = process_pack(
            pdf_path=temp_pdf_path,
            profile_path=profile_path,
            output_path=None,  # No escribimos el json en el disco del contenedor
            ocr_engine=ocr_engine_global
        )
        
        # 3. Retornar los JSON directamente
        return JSONResponse(status_code=200, content=result_json)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        # 4. Cleanup: desechar el PDF temporal pase lo que pase para ahorrar espacio
        if os.path.exists(temp_pdf_path):
            try:
                os.remove(temp_pdf_path)
            except Exception:
                pass

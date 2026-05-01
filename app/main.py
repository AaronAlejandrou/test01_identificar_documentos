from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from app.core.config import settings

from app.routers import extraction, inspect, config, documents, ai

app = FastAPI(
    title=settings.PROJECT_NAME, 
    version=settings.VERSION,
    description="Plataforma de procesamiento y extracción documental con soporte IA."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir imágenes subidas estáticamente (Para que el frontend pueda mostrarlas en el Canvas)
app.mount("/static/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

app.include_router(documents.router, prefix="/api/documents", tags=["Documentos (Studio)"])
app.include_router(ai.router, prefix="/api/ai", tags=["Inteligencia Artificial (Studio)"])
app.include_router(inspect.router, prefix="/api/inspect", tags=["Inspección (Studio)"])
app.include_router(config.router, prefix="/api/config", tags=["Configuración (Perfiles)"])
app.include_router(extraction.router, prefix="/api/extractions", tags=["Extracción (Runner)"])

@app.get("/")
def root():
    return {"message": "Bienvenido a la API de Extracción de Datos. Visite /docs para ver la documentación (Swagger)."}

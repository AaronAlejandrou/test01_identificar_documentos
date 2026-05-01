# API de Extracción y Calibración de Documentos

Backend moderno construido con **FastAPI** para la extracción estructurada de datos de PDFs y el soporte asistido por IA para calibrar y crear plantillas de documentos desde un frontend ("Studio").

## Arquitectura del Proyecto

```text
test01_identificar_documentos/
├── app/               # Lógica de la API (Modelos, Rutas y Servicios de IA/Extracción)
├── config/            # JSONs maestros y plantillas hijas de los documentos
├── data/              # Directorio autogenerado para uploads temporales y JSON extraídos
├── samples/           # PDFs de prueba
└── venv/              # Entorno Virtual de Python
```

## Requisitos y Dependencias
Asegúrate de que las dependencias estén instaladas en tu entorno virtual:
```powershell
.\venv\Scripts\activate
pip install -r requirements.txt
```

## Comandos para Iniciar la API

Para levantar el servidor de la API, debes ejecutar estos comandos en tu terminal de **PowerShell**. 
*(Asegúrate de estar ubicado en la carpeta `test01_identificar_documentos`)*:

```powershell
# 1. Activar el entorno virtual
.\venv\Scripts\activate

# 2. Levantar el servidor FastAPI
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Una vez que el servidor inicie, abre tu navegador y visita:
👉 **[http://localhost:8000/docs](http://localhost:8000/docs)**

Allí encontrarás la interfaz interactiva de Swagger UI donde puedes probar cada endpoint.

## Resumen de Endpoints

### 1. Documentos y Studio (Calibración)
- **`POST /api/documents/split`**: Recibe un PDF y genera imágenes PNG de alta resolución por cada página. Devuelve URLs estáticas para usar en tu Frontend Canvas.
- **`POST /api/ai/detect/{document_id}/{page_index}`**: Escanea una imagen específica mediante OCR (PaddleOCR) y heurísticas, retornando una lista de "bounding boxes" sugeridos para textos y posibles checkboxes.

### 2. Configuración y Perfiles
- **`GET /api/config`**: Lista todos los perfiles disponibles.
- **`GET /api/config/{filename}`**: Obtiene el JSON específico para renderizarlo o editarlo en el Frontend.
- **`POST /api/config/profile`**: Guarda un "Perfil Maestro" junto con todas sus plantillas de página. Ideal para cuando el usuario finaliza la calibración en el Studio.
- **`PUT /api/config/{filename}`**: Sobrescribe un archivo de configuración específico.

### 3. Runner y Extracción Operativa
- **`POST /api/extractions/run`**: Toma un PDF y un Perfil, invoca al motor de extracción, valida las reglas cruzadas y retorna la data extraída en memoria temporal.
- **`POST /api/extractions/save`**: Toma la data final (incluso si fue modificada manualmente por el usuario en el UI) y la guarda como un archivo histórico en el sistema.
- **`GET /api/extractions/{id}`**: Consulta un resultado de extracción previo.

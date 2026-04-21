# Sistema de Extracción Multipágina y Multiplantilla

Versión local, diseñada para extraer información de paquetes documentales en PDF (ej. Solicitud Digital de Vida, Anexos, Privacidad, etc.).

## Arquitectura

El sistema ha sido adaptado para soportar PDFs de múltiples páginas con diferentes formatos:

1. **Perfil de Documento**: (`config/document_profile_*.json`) Define la "familia" del PDF, sus plantillas y palabras clave globales.
2. **Plantilla por Página**: (ej. `config/page_01_solicitud_principal.json`) Archivos JSON independientes con los campos, firmas y radios a extraer para esa página específica.
3. **Orquestador (`extract_pack.py`)**: Recorre todas las páginas, detecta automáticamente la plantilla aplicable mediante extracción de texto y consolida los resultados (con validaciones cruzadas).
4. **Worker (`extract_local.py`)**: Encargado de la extracción física sobre una sola página renderizada.

## Instalación simple
```bash
pip install -r requirements.txt
```

## Flujo de Trabajo (Para Nuevos Documentos)

### 1. Generar la Plantilla (Ya provista)
Si agregas un nuevo documento, crea el perfil y los JSON de sus páginas en `config/`. (Actualmente ya existen las configuraciones en `[0,0,0.1,0.1]` para Solicitud Digital).

### 2. Inspeccionar Página
Usa `inspect_blocks.py` indicando qué página y qué JSON de plantilla quieres revisar:
```bash
python inspect_blocks.py "tu_paquete.pdf" --config config/page_01_solicitud_principal.json --page 1 --output overlay_p1.png
```

### 3. Calibrar por Página (Importante)
Ajusta las coordenadas de los campos para que coincidan con tu PDF real. Tienes que hacerlo por cada página.
```bash
python calibrate_blocks.py "tu_paquete.pdf" --config config/page_01_solicitud_principal.json --mode text --page 1
python calibrate_blocks.py "tu_paquete.pdf" --config config/page_01_solicitud_principal.json --mode radio --page 1
python calibrate_blocks.py "tu_paquete.pdf" --config config/page_01_solicitud_principal.json --mode sign --page 1
```
*(Repite el proceso para `--page 2` con `page_02_producto_beneficiarios.json`, etc.)*

### 4. Extraer Paquete Completo
Una vez que todas las plantillas están calibradas, ejecuta el orquestador general:
```bash
python extract_pack.py "tu_paquete.pdf" --profile config/document_profile_solicitud_digital.json --output resultado_consolidado.json
```
Esto procesará las páginas, aplicará las validaciones (ver `validations` en el JSON final) y entregará todos los datos organizados.

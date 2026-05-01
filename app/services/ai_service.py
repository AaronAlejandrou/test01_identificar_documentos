import cv2
import numpy as np
from paddleocr import PaddleOCR
from typing import List, Dict, Any

# Singleton para evitar recargar el modelo en memoria en cada llamada
class OCREngineSingleton:
    _instance = None
    
    @classmethod
    def get_engine(cls):
        if cls._instance is None:
            cls._instance = PaddleOCR(
                lang="es",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                enable_mkldnn=False,
                show_log=False
            )
        return cls._instance

def detect_blocks_in_image(image_path: str) -> List[Dict[str, Any]]:
    """
    Escanea ciegamente una imagen para encontrar posibles áreas de interés.
    Devuelve listas de bounding boxes normalizados.
    """
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"No se pudo leer la imagen {image_path}")
        
    h, w = img.shape[:2]
    engine = OCREngineSingleton.get_engine()
    
    # 1. Detectar Textos con OCR
    result = engine.ocr(img)
    blocks = []
    
    if result and result[0]:
        for line in result[0]:
            # line_format: [[[x1,y1], [x2,y2], [x3,y3], [x4,y4]], ('text', confidence)]
            box = line[0]
            text = line[1][0]
            conf = float(line[1][1])
            
            # Convert polygon to bounding box
            x_coords = [p[0] for p in box]
            y_coords = [p[1] for p in box]
            x1, x2 = min(x_coords), max(x_coords)
            y1, y2 = min(y_coords), max(y_coords)
            
            blocks.append({
                "type": "text",
                "bbox": {
                    "x1": round(x1 / w, 4),
                    "y1": round(y1 / h, 4),
                    "x2": round(x2 / w, 4),
                    "y2": round(y2 / h, 4)
                },
                "content": text,
                "confidence": conf
            })
            
    # 2. Detección heurística de checkboxes/radios (Lógica básica de Canny + Contornos)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    for cnt in contours:
        # Aproximar polígono
        approx = cv2.approxPolyDP(cnt, 0.04 * cv2.arcLength(cnt, True), True)
        area = cv2.contourArea(cnt)
        
        # Filtrar por tamaño (checkboxes suelen ser pequeños)
        if 100 < area < 2000:
            x, y, cw, ch = cv2.boundingRect(approx)
            aspect_ratio = float(cw) / ch
            
            # Cuadrados o círculos perfectos
            if 0.85 <= aspect_ratio <= 1.15:
                blocks.append({
                    "type": "radio",
                    "bbox": {
                        "x1": round(x / w, 4),
                        "y1": round(y / h, 4),
                        "x2": round((x + cw) / w, 4),
                        "y2": round((y + ch) / h, 4)
                    },
                    "content": None,
                    "confidence": 0.8
                })

    return blocks

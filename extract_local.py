# extract_local.py
# ------------------------------------------------------------
# Lee el PDF "sac-formulario-de-ingreso-de-solicitudes.pdf"
# usando coordenadas definidas en:
#   config/form_blocks_interseguro.json
#
# Flujo:
# 1) Abre la primera página del PDF
# 2) La renderiza a tamaño canónico
# 3) Para campos de texto:
#       - intenta extraer texto nativo del PDF por coordenadas
#       - si no encuentra nada, usa PaddleOCR sobre la ROI
# 4) Para radios/checks:
#       - detecta la opción marcada por densidad de píxeles
# 5) Para firmas:
#       - detecta si hay tinta/presencia gráfica
# 6) Devuelve resultado.json
#
# Requisitos:
#   pip install paddlepaddle paddleocr pymupdf opencv-python pillow numpy
# ------------------------------------------------------------

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Tuple, Optional

import cv2
import fitz  # PyMuPDF
import numpy as np
from paddleocr import PaddleOCR


# ============================================================
# CONFIG
# ============================================================

DEFAULT_INPUT = "sac-formulario-de-ingreso-de-solicitudes.pdf"
DEFAULT_CONFIG = "config/form_blocks_interseguro.json"
DEFAULT_OUTPUT = "resultado.json"


# ============================================================
# UTILIDADES
# ============================================================

def load_json(path: str) -> Dict[str, Any]:
    """Carga un JSON desde disco."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(path: str, data: Dict[str, Any]) -> None:
    """Guarda un JSON con formato legible."""
    Path(path).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def clean_text(text: str) -> str:
    """Limpia espacios, saltos de línea y basura simple."""
    if not text:
        return ""
    text = text.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def bbox_norm_to_px(bbox, width: int, height: int) -> Tuple[int, int, int, int]:
    """
    Convierte un bbox normalizado [x1, y1, x2, y2]
    a coordenadas en píxeles.
    """
    x1, y1, x2, y2 = bbox
    return (
        int(round(x1 * width)),
        int(round(y1 * height)),
        int(round(x2 * width)),
        int(round(y2 * height)),
    )


def bbox_norm_to_pdf_rect(bbox, page_width: float, page_height: float) -> fitz.Rect:
    """
    Convierte un bbox normalizado [x1, y1, x2, y2]
    a un rectángulo PDF real.
    """
    x1, y1, x2, y2 = bbox
    return fitz.Rect(
        x1 * page_width,
        y1 * page_height,
        x2 * page_width,
        y2 * page_height
    )


def crop_image(image: np.ndarray, bbox) -> np.ndarray:
    """Recorta una ROI desde una imagen usando bbox normalizado."""
    h, w = image.shape[:2]
    x1, y1, x2, y2 = bbox_norm_to_px(bbox, w, h)
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(w, x2)
    y2 = min(h, y2)
    return image[y1:y2, x1:x2].copy()


# ============================================================
# PDF
# ============================================================

def render_pdf_page(doc: fitz.Document, page_num: int, target_width: int, target_height: int) -> Tuple[np.ndarray, fitz.Page]:
    """
    Renderiza una página específica del PDF y la devuelve como imagen BGR
    ajustada exactamente al tamaño canónico.
    También devuelve el objeto Page para extracción de texto nativo.
    """
    page = doc[page_num]

    # Render inicial usando una escala razonable
    pix = page.get_pixmap(alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)

    # Convertir a BGR si viene en RGB
    if pix.n == 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    elif pix.n == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)

    # Ajustar al tamaño canónico definido en el JSON
    img = cv2.resize(img, (target_width, target_height), interpolation=cv2.INTER_CUBIC)
    return img, page

def render_pdf_first_page(pdf_path: str, target_width: int, target_height: int) -> Tuple[np.ndarray, fitz.Page]:
    """Legacy wrapper for single page scripts."""
    doc = fitz.open(pdf_path)
    return render_pdf_page(doc, 0, target_width, target_height)


def extract_pdf_native_text(page: fitz.Page, bbox_norm) -> str:
    """
    Intenta leer texto nativo del PDF dentro de un rectángulo.
    Si el PDF está aplanado o sin texto, puede devolver vacío.
    """
    rect = bbox_norm_to_pdf_rect(bbox_norm, page.rect.width, page.rect.height)
    text = page.get_text("text", clip=rect)
    return clean_text(text)


# ============================================================
# OCR
# ============================================================

def preprocess_roi_for_ocr(roi: np.ndarray) -> np.ndarray:
    """
    Preprocesamiento simple para mejorar OCR en ROIs.
    """
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    # Binarización adaptativa
    th = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        12
    )
    
    # PaddleOCR espera imagen de 3 canales
    th_bgr = cv2.cvtColor(th, cv2.COLOR_GRAY2BGR)
    return th_bgr


def create_ocr_engine() -> PaddleOCR:
    """
    Crea el motor PaddleOCR.
    use_doc_orientation_classify=False porque no queremos complejidad extra.
    use_doc_unwarping=False porque el PDF renderizado es estable.
    use_textline_orientation=False para mantenerlo simple.
    """
    return PaddleOCR(
        lang="es",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        enable_mkldnn=False
    )


def extract_text_with_ocr(ocr_engine: PaddleOCR, roi: np.ndarray) -> Tuple[str, float]:
    """
    Ejecuta OCR sobre una ROI y devuelve:
    - texto unido
    - confianza promedio
    """
    proc = preprocess_roi_for_ocr(roi)

    result = ocr_engine.ocr(proc)

    if not result or not result[0]:
        return "", 0.0

    texts = []
    confs = []

    for line in result[0]:
        # line esperado: [box, [text, confidence]]
        if len(line) >= 2 and isinstance(line[1], (list, tuple)) and len(line[1]) >= 2:
            txt = clean_text(str(line[1][0]))
            conf = float(line[1][1])
            if txt:
                texts.append(txt)
                confs.append(conf)

    final_text = clean_text(" ".join(texts))
    avg_conf = float(np.mean(confs)) if confs else 0.0
    return final_text, round(avg_conf, 4)


# ============================================================
# DETECCIÓN DE RADIOS / CHECKS
# ============================================================

def detect_marked_option(image: np.ndarray, group_cfg: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, float]]:
    """
    Detecta qué opción está marcada en un grupo de radios/checks.
    Usa la densidad de píxeles oscuros en el círculo interior.
    """
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    radius = max(3, int(round(group_cfg["radius_norm"] * w)))
    inner_radius = max(2, int(round(group_cfg["inner_radius_norm"] * w)))
    threshold = float(group_cfg.get("mark_threshold", 0.12))

    yy, xx = np.ogrid[:h, :w]
    scores: Dict[str, float] = {}

    for label, (nx, ny) in group_cfg["options"].items():
        cx = int(round(nx * w))
        cy = int(round(ny * h))

        # Solo medimos el círculo interior para evitar el borde negro del radio
        dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        inner_mask = dist <= inner_radius

        vals = gray[inner_mask]
        score = float(np.mean(vals < 170)) if vals.size else 0.0
        scores[label] = round(score, 4)

    best_label = None
    if scores:
        ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if ordered[0][1] >= threshold:
            best_label = ordered[0][0]

    return best_label, scores


# ============================================================
# DETECCIÓN DE FIRMA / TINTA
# ============================================================

def detect_ink_presence(roi: np.ndarray) -> bool:
    """
    Detecta si hay tinta o contenido gráfico dentro de la ROI.
    Para formulario vacío debería devolver False.
    """
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

    ink_ratio = float(np.mean(th > 0))
    return ink_ratio > 0.01


# ============================================================
# EXTRACCIÓN
# ============================================================

def build_empty_output() -> Dict[str, Any]:
    """Plantilla base de salida."""
    return {
        "source_file": DEFAULT_INPUT,
        "fields": {},
        "checks": {},
        "signatures": {}
    }


def extract_page_fields(page_image: np.ndarray, page: fitz.Page, cfg: Dict[str, Any], ocr_engine: PaddleOCR) -> Dict[str, Any]:
    """Extrae los campos de una sola página (Worker)"""
    result = {
        "fields": {},
        "checks": {},
        "signatures": {}
    }

    cleanup_cfg = cfg.get("cleanup_rules", {})

    # --------------------------------------------------------
    # 1) CAMPOS DE TEXTO
    # --------------------------------------------------------
    for field_name, bbox in cfg.get("text_fields", {}).items():
        native_text = extract_pdf_native_text(page, bbox)

        if native_text:
            raw_text = native_text
            source = "pdf_native"
            confidence = 1.0
        else:
            roi = crop_image(page_image, bbox)
            ocr_text, ocr_conf = extract_text_with_ocr(ocr_engine, roi)
            raw_text = ocr_text
            source = "ocr"
            confidence = ocr_conf

        # Aplicar reglas de limpieza (remover labels estáticos)
        clean_val = raw_text
        if field_name in cleanup_cfg:
            for rule in cleanup_cfg[field_name]:
                clean_val = clean_val.replace(rule, "")
        
        clean_val = clean_val.strip(" :-\t\n\r")
        clean_val = clean_text(clean_val)

        if not clean_val:
            clean_val = ""
            source = "empty"
            confidence = 0.0

        result["fields"][field_name] = {
            "value": clean_val,
            "raw_value": raw_text,
            "source": source,
            "confidence": confidence
        }

    # --------------------------------------------------------
    # 2) RADIOS / CHECKS
    # --------------------------------------------------------
    for group_name, group_cfg in cfg.get("checkbox_groups", {}).items():
        selected, scores = detect_marked_option(page_image, group_cfg)

        result["checks"][group_name] = {
            "selected": selected,
            "scores": scores
        }

    # --------------------------------------------------------
    # 3) FIRMAS / TINTA
    # --------------------------------------------------------
    for sign_name, bbox in cfg.get("signature_fields", {}).items():
        roi = crop_image(page_image, bbox)
        present = detect_ink_presence(roi)

        result["signatures"][sign_name] = {
            "present": present
        }

    return result


def extract_document(pdf_path: str, config_path: str, output_path: str, page_num: int = 0) -> Dict[str, Any]:
    """
    Wrapper legacy para compatibilidad con el flujo original:
    - abre PDF
    - renderiza la página especificada
    - extrae texto, radios y firmas
    - guarda resultado.json
    """
    cfg = load_json(config_path)

    canonical_w = int(cfg["canonical"]["width"])
    canonical_h = int(cfg["canonical"]["height"])

    doc = fitz.open(pdf_path)
    page_image, page = render_pdf_page(doc, page_num, canonical_w, canonical_h)
    ocr_engine = create_ocr_engine()

    result = build_empty_output()
    result["source_file"] = pdf_path

    page_result = extract_page_fields(page_image, page, cfg, ocr_engine)
    result.update(page_result)

    # Guardar JSON final
    save_json(output_path, result)
    return result


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Extrae información del formulario Interseguro y devuelve JSON.")
    parser.add_argument("pdf", nargs="?", default=DEFAULT_INPUT, help="Ruta al PDF de entrada")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="Ruta al JSON de coordenadas")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Ruta del JSON de salida")
    parser.add_argument("--page", type=int, default=1, help="Número de página (1-indexed)")
    args = parser.parse_args()

    result = extract_document(
        pdf_path=args.pdf,
        config_path=args.config,
        output_path=args.output,
        page_num=args.page - 1
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Tuple

import cv2
import fitz  # PyMuPDF
import numpy as np


# ============================================================
# UTILIDADES BÁSICAS
# ============================================================

def load_config(path: str) -> Dict[str, Any]:
    """Carga el archivo JSON de configuración."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def render_first_page(file_path: str, dpi: int, canonical_w: int, canonical_h: int) -> np.ndarray:
    """
    Abre un PDF o imagen y lo devuelve como imagen BGR normalizada al tamaño canónico.

    - Si es PDF: renderiza la primera página con PyMuPDF.
    - Si es imagen: la abre y la redimensiona.
    """
    p = Path(file_path)

    if p.suffix.lower() == ".pdf":
        doc = fitz.open(file_path)
        page = doc.load_page(0)
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    else:
        img = cv2.imread(file_path)
        if img is None:
            raise RuntimeError(f"No se pudo abrir la imagen: {file_path}")

    img = cv2.resize(img, (canonical_w, canonical_h), interpolation=cv2.INTER_CUBIC)
    return img


def bbox_to_px(bbox, width: int, height: int) -> Tuple[int, int, int, int]:
    """Convierte coordenadas normalizadas [x1, y1, x2, y2] a píxeles."""
    x1, y1, x2, y2 = bbox
    return (
        int(round(max(0.0, min(1.0, x1)) * width)),
        int(round(max(0.0, min(1.0, y1)) * height)),
        int(round(max(0.0, min(1.0, x2)) * width)),
        int(round(max(0.0, min(1.0, y2)) * height)),
    )


# ============================================================
# DIBUJO DE BLOQUES
# ============================================================

def draw_overlay(image: np.ndarray, cfg: Dict[str, Any]) -> np.ndarray:
    """
    Dibuja todos los bloques del JSON sobre la imagen.

    Colores:
    - rojo: campos de texto
    - azul: firmas
    - verde: radios/checkboxes
    """
    out = image.copy()
    h, w = out.shape[:2]

    # Campos de texto
    for name, bbox in cfg.get("text_fields", {}).items():
        x1, y1, x2, y2 = bbox_to_px(bbox, w, h)
        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 0, 255), 2)
        cv2.putText(out, name, (x1 + 2, max(14, y1 + 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1, cv2.LINE_AA)

    # Firmas
    for name, bbox in cfg.get("signature_fields", {}).items():
        x1, y1, x2, y2 = bbox_to_px(bbox, w, h)
        cv2.rectangle(out, (x1, y1), (x2, y2), (255, 0, 0), 2)
        cv2.putText(out, name, (x1 + 2, max(14, y1 + 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 0, 0), 1, cv2.LINE_AA)

    # Radios
    for group_name, group_cfg in cfg.get("checkbox_groups", {}).items():
        radius = max(4, int(round(group_cfg.get("radius_norm", 0.008) * w)))
        for option_name, (nx, ny) in group_cfg.get("options", {}).items():
            cx, cy = int(round(nx * w)), int(round(ny * h))
            cv2.circle(out, (cx, cy), radius, (0, 180, 0), 2)
            cv2.putText(out, f"{group_name}:{option_name}", (cx + radius + 2, cy - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 180, 0), 1, cv2.LINE_AA)

    return out


def save_ranges_txt(path: str, cfg: Dict[str, Any], width: int, height: int) -> None:
    """Guarda un TXT con todos los rangos reales en píxeles."""
    lines = []
    lines.append(f"CANONICAL_SIZE = {width}x{height}\n")

    lines.append("[TEXT_FIELDS]")
    for name, bbox in cfg.get("text_fields", {}).items():
        lines.append(f"{name}: norm={bbox} px={bbox_to_px(bbox, width, height)}")

    lines.append("\n[SIGNATURE_FIELDS]")
    for name, bbox in cfg.get("signature_fields", {}).items():
        lines.append(f"{name}: norm={bbox} px={bbox_to_px(bbox, width, height)}")

    lines.append("\n[CHECKBOX_GROUPS]")
    for group_name, group_cfg in cfg.get("checkbox_groups", {}).items():
        lines.append(f"{group_name}: radius_norm={group_cfg.get('radius_norm')} inner_radius_norm={group_cfg.get('inner_radius_norm')}")
        for option_name, (nx, ny) in group_cfg.get("options", {}).items():
            cx, cy = int(round(nx * width)), int(round(ny * height))
            lines.append(f"  {option_name}: norm=({nx}, {ny}) px=({cx}, {cy})")

    Path(path).write_text("\n".join(lines), encoding="utf-8")


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    ap = argparse.ArgumentParser(description="Dibuja los bloques configurados sobre el PDF/imagen.")
    ap.add_argument("input", help="Ruta al PDF o imagen")
    ap.add_argument("--config", default="config/form_blocks_interseguro.json", help="Ruta al JSON de bloques")
    ap.add_argument("--dpi", type=int, default=200, help="DPI al renderizar PDF")
    ap.add_argument("--output", default="overlay_debug.png", help="Nombre de la imagen overlay de salida")
    ap.add_argument("--ranges", default="ranges_debug.txt", help="Nombre del TXT de rangos")
    args = ap.parse_args()

    cfg = load_config(args.config)
    can_w = int(cfg["canonical"]["width"])
    can_h = int(cfg["canonical"]["height"])

    img = render_first_page(args.input, args.dpi, can_w, can_h)
    overlay = draw_overlay(img, cfg)

    cv2.imwrite(args.output, overlay)
    save_ranges_txt(args.ranges, cfg, can_w, can_h)

    print(f"Overlay guardado en: {args.output}")
    print(f"Rangos guardados en: {args.ranges}")


if __name__ == "__main__":
    main()

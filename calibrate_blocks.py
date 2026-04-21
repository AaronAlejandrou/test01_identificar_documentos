from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import fitz
import numpy as np


# ============================================================
# UTILIDADES
# ============================================================

def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(path: str, cfg: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def render_first_page(file_path: str, dpi: int, canonical_w: int, canonical_h: int) -> np.ndarray:
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
            raise RuntimeError(f"No se pudo abrir: {file_path}")

    return cv2.resize(img, (canonical_w, canonical_h), interpolation=cv2.INTER_CUBIC)


def bbox_to_px(bbox, width: int, height: int):
    x1, y1, x2, y2 = bbox
    return (
        int(round(max(0.0, min(1.0, x1)) * width)),
        int(round(max(0.0, min(1.0, y1)) * height)),
        int(round(max(0.0, min(1.0, x2)) * width)),
        int(round(max(0.0, min(1.0, y2)) * height)),
    )


def px_to_bbox(x1: int, y1: int, x2: int, y2: int, width: int, height: int):
    x1, x2 = sorted([x1, x2])
    y1, y2 = sorted([y1, y2])
    return [round(x1 / width, 6), round(y1 / height, 6), round(x2 / width, 6), round(y2 / height, 6)]


# ============================================================
# CALIBRADOR DE CAJAS
# ============================================================

class BoxCalibrator:
    def __init__(self, image: np.ndarray, cfg: Dict[str, Any], section_name: str):
        self.image = image
        self.cfg = cfg
        self.section_name = section_name  # text_fields o signature_fields
        self.items: List[str] = list(cfg[section_name].keys())
        self.index = 0
        self.start_pt = None
        self.end_pt = None
        self.dragging = False
        self.window = f"Calibrador cajas - {section_name}"
        self.h, self.w = image.shape[:2]

    def current_name(self) -> str:
        return self.items[self.index]

    def draw(self):
        canvas = self.image.copy()

        # Dibujar todas las cajas actuales tenuemente
        for name, bbox in self.cfg[self.section_name].items():
            x1, y1, x2, y2 = bbox_to_px(bbox, self.w, self.h)
            color = (0, 0, 255) if self.section_name == "text_fields" else (255, 0, 0)
            thickness = 3 if name == self.current_name() else 1
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, thickness)
            cv2.putText(canvas, name, (x1 + 2, max(18, y1 + 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)

        # Si el usuario está arrastrando, mostrar la caja temporal
        if self.start_pt and self.end_pt:
            cv2.rectangle(canvas, self.start_pt, self.end_pt, (0, 255, 255), 2)

        help_text_1 = f"Campo actual: {self.current_name()}  ({self.index + 1}/{len(self.items)})"
        help_text_2 = "Arrastra con mouse. Teclas: N siguiente | P anterior | S guardar JSON | Q salir"
        cv2.putText(canvas, help_text_1, (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (30, 30, 30), 2, cv2.LINE_AA)
        cv2.putText(canvas, help_text_2, (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (30, 30, 30), 2, cv2.LINE_AA)

        cv2.imshow(self.window, canvas)

    def mouse_cb(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.start_pt = (x, y)
            self.end_pt = (x, y)
            self.dragging = True
        elif event == cv2.EVENT_MOUSEMOVE and self.dragging:
            self.end_pt = (x, y)
        elif event == cv2.EVENT_LBUTTONUP:
            self.end_pt = (x, y)
            self.dragging = False
            bbox = px_to_bbox(self.start_pt[0], self.start_pt[1], self.end_pt[0], self.end_pt[1], self.w, self.h)
            self.cfg[self.section_name][self.current_name()] = bbox
            self.draw()

    def run(self):
        cv2.namedWindow(self.window, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(self.window, self.mouse_cb)
        self.draw()

        while True:
            key = cv2.waitKey(20) & 0xFF
            if key == ord('n'):
                self.index = min(len(self.items) - 1, self.index + 1)
                self.start_pt = self.end_pt = None
                self.draw()
            elif key == ord('p'):
                self.index = max(0, self.index - 1)
                self.start_pt = self.end_pt = None
                self.draw()
            elif key == ord('q'):
                break
            elif key == ord('s'):
                print("Configuración lista para guardar desde main.")

        cv2.destroyWindow(self.window)


# ============================================================
# CALIBRADOR DE RADIOS
# ============================================================

class RadioCalibrator:
    def __init__(self, image: np.ndarray, cfg: Dict[str, Any]):
        self.image = image
        self.cfg = cfg
        self.groups = list(cfg["checkbox_groups"].keys())
        self.group_index = 0
        self.option_index = 0
        self.window = "Calibrador radios"
        self.h, self.w = image.shape[:2]

    def current_group(self) -> str:
        return self.groups[self.group_index]

    def current_options(self) -> List[str]:
        return list(self.cfg["checkbox_groups"][self.current_group()]["options"].keys())

    def current_option(self) -> str:
        return self.current_options()[self.option_index]

    def click_cb(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            group = self.current_group()
            option = self.current_option()
            self.cfg["checkbox_groups"][group]["options"][option] = [round(x / self.w, 6), round(y / self.h, 6)]

            # Avanzar automáticamente a la siguiente opción
            if self.option_index < len(self.current_options()) - 1:
                self.option_index += 1
            else:
                if self.group_index < len(self.groups) - 1:
                    self.group_index += 1
                    self.option_index = 0
            self.draw()

    def draw(self):
        canvas = self.image.copy()
        for group_name, group_cfg in self.cfg["checkbox_groups"].items():
            radius = max(4, int(round(group_cfg.get("radius_norm", 0.008) * self.w)))
            for option_name, (nx, ny) in group_cfg["options"].items():
                cx, cy = int(round(nx * self.w)), int(round(ny * self.h))
                color = (0, 180, 0)
                thickness = 2
                if group_name == self.current_group() and option_name == self.current_option():
                    color = (0, 255, 255)
                    thickness = 3
                cv2.circle(canvas, (cx, cy), radius, color, thickness)
                cv2.putText(canvas, f"{group_name}:{option_name}", (cx + radius + 2, cy - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1, cv2.LINE_AA)

        help_text_1 = f"Grupo actual: {self.current_group()} | Opcion actual: {self.current_option()}"
        help_text_2 = "Haz click en el centro exacto del radio. Teclas: Q salir | S guardar JSON"
        cv2.putText(canvas, help_text_1, (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (30, 30, 30), 2, cv2.LINE_AA)
        cv2.putText(canvas, help_text_2, (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (30, 30, 30), 2, cv2.LINE_AA)
        cv2.imshow(self.window, canvas)

    def run(self):
        cv2.namedWindow(self.window, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(self.window, self.click_cb)
        self.draw()

        while True:
            key = cv2.waitKey(20) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s'):
                print("Configuración lista para guardar desde main.")

        cv2.destroyWindow(self.window)


# ============================================================
# MAIN
# ============================================================

def main():
    ap = argparse.ArgumentParser(description="Calibrador local de bloques para el formulario Interseguro")
    ap.add_argument("input", help="Ruta al PDF o imagen")
    ap.add_argument("--config", default="config/form_blocks_interseguro.json", help="Ruta al JSON a editar")
    ap.add_argument("--mode", choices=["text", "sign", "radio"], required=True, help="Modo de calibración")
    ap.add_argument("--dpi", type=int, default=200, help="DPI de render si es PDF")
    args = ap.parse_args()

    cfg = load_config(args.config)
    can_w = int(cfg["canonical"]["width"])
    can_h = int(cfg["canonical"]["height"])
    image = render_first_page(args.input, args.dpi, can_w, can_h)

    if args.mode == "text":
        editor = BoxCalibrator(image, cfg, "text_fields")
        editor.run()
    elif args.mode == "sign":
        editor = BoxCalibrator(image, cfg, "signature_fields")
        editor.run()
    elif args.mode == "radio":
        editor = RadioCalibrator(image, cfg)
        editor.run()

    save_config(args.config, cfg)
    print(f"JSON actualizado y guardado en: {args.config}")


if __name__ == "__main__":
    main()

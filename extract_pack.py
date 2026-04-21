import argparse
import json
import os
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import fitz
import numpy as np

# Reutilizamos las funciones de extract_local
from extract_local import (
    create_ocr_engine,
    extract_page_fields,
    load_json,
    render_pdf_page,
    save_json,
    clean_text
)

# ============================================================
# ORQUESTADOR
# ============================================================

def detect_page_template(page: fitz.Page, templates: Dict[str, Any]) -> Optional[str]:
    """
    Extrae el texto de la página y cuenta cuántos 'identifiers'
    de cada plantilla están presentes. Retorna el nombre de la plantilla
    con mayor coincidencia (score).
    """
    page_text = page.get_text("text").lower()
    page_text = clean_text(page_text)
    
    best_template = None
    best_score = 0
    
    for tmpl_name, tmpl_data in templates.items():
        identifiers = tmpl_data.get("identifiers", [])
        score = 0
        for ident in identifiers:
            if ident.lower() in page_text:
                score += 1
                
        if score > best_score:
            best_score = score
            best_template = tmpl_name
            
    return best_template


def consolidate_results(pages_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Consolida los resultados de todas las páginas en un solo objeto
    y aplica las reglas de negocio/validaciones.
    """
    consolidated = {
        "fields": {},
        "checks": {},
        "signatures": {},
        "validations": []
    }
    
    # 1. Unir todos los campos
    # Guardamos de qué página vino cada campo para validaciones cruzadas
    field_sources = defaultdict(list)
    
    for page_res in pages_results:
        page_num = page_res["page_index"] + 1
        
        # Merge fields
        for k, v in page_res["data"].get("fields", {}).items():
            val = v.get("value")
            if val:
                consolidated["fields"][k] = v
                field_sources[k].append({"page": page_num, "value": val})
                
        # Merge checks
        for k, v in page_res["data"].get("checks", {}).items():
            sel = v.get("selected")
            if sel:
                consolidated["checks"][k] = v
                field_sources[k].append({"page": page_num, "value": sel})
                
        # Merge signatures
        for k, v in page_res["data"].get("signatures", {}).items():
            if v.get("present"):
                consolidated["signatures"][k] = v
                field_sources[k].append({"page": page_num, "value": v.get("present")})
                
    # 2. Aplicar reglas de negocio
    
    # Regla 2: Validaciones cruzadas
    # propuesta_numero
    if "propuesta_numero" in field_sources and len(field_sources["propuesta_numero"]) > 1:
        first_val = field_sources["propuesta_numero"][0]["value"]
        for entry in field_sources["propuesta_numero"][1:]:
            if entry["value"] != first_val:
                consolidated["validations"].append(
                    f"Discrepancia en propuesta_numero: pág {field_sources['propuesta_numero'][0]['page']} ({first_val}) "
                    f"vs pág {entry['page']} ({entry['value']})"
                )
                
    # Regla 1: Campos condicionales
    # Datos del contratante solo si es distinto al asegurado
    aseg_nom = consolidated["fields"].get("asegurado_nombres", {}).get("value", "").strip().lower()
    cont_nom = consolidated["fields"].get("contratante_nombre", {}).get("value", "").strip().lower()
    
    if aseg_nom and cont_nom and aseg_nom == cont_nom:
        consolidated["validations"].append("Contratante es igual al asegurado. Ignorando campos de contratante repetidos.")
        # Podríamos limpiar los campos del contratante aquí si se requiere
        
    # Regla 4: Sumatoria de beneficiarios
    total_pct = 0.0
    for i in range(1, 4):
        pct_str = consolidated["fields"].get(f"beneficiario_{i}_porcentaje", {}).get("value", "")
        if pct_str:
            try:
                # Quitar '%' si lo hay y sumar
                val = float(pct_str.replace("%", "").strip())
                total_pct += val
            except ValueError:
                pass
                
    if total_pct > 0 and total_pct != 100.0:
        consolidated["validations"].append(f"La sumatoria de porcentajes de beneficiarios es {total_pct}%, debería ser 100%.")

    return consolidated


def process_pack(pdf_path: str, profile_path: str, output_path: str):
    """
    Orquestador principal que procesa un paquete PDF multipágina.
    """
    profile = load_json(profile_path)
    base_dir = os.path.dirname(profile_path)
    
    # Cargar las plantillas definidas en el perfil
    templates = {}
    for tmpl_name in profile.get("page_templates", []):
        tmpl_path = os.path.join(base_dir, f"{tmpl_name}.json")
        if os.path.exists(tmpl_path):
            templates[tmpl_name] = load_json(tmpl_path)
        else:
            print(f"Advertencia: No se encontró la plantilla {tmpl_path}")
            
    doc = fitz.open(pdf_path)
    ocr_engine = create_ocr_engine()
    
    pages_results = []
    
    print(f"Procesando documento: {pdf_path} ({doc.page_count} páginas)")
    
    for i in range(doc.page_count):
        page = doc[i]
        
        # Detectar qué plantilla corresponde
        template_name = detect_page_template(page, templates)
        
        if not template_name:
            print(f" - Pág {i+1}: Sin plantilla asignada (Omitiendo)")
            continue
            
        print(f" - Pág {i+1}: Plantilla detectada -> {template_name}")
        
        # Cargar config de la plantilla
        cfg = templates[template_name]
        canonical_w = int(cfg["canonical"]["width"])
        canonical_h = int(cfg["canonical"]["height"])
        
        # Renderizar y extraer
        page_image, _ = render_pdf_page(doc, i, canonical_w, canonical_h)
        page_res = extract_page_fields(page_image, page, cfg, ocr_engine)
        
        pages_results.append({
            "page_index": i,
            "template": template_name,
            "data": page_res
        })
        
    print("\nConsolidando resultados y aplicando validaciones...")
    final_json = {
        "document_type": profile.get("document_type", "unknown"),
        "source_file": pdf_path,
        "pages_processed": len(pages_results),
        "consolidated": consolidate_results(pages_results),
        "pages_raw": pages_results
    }
    
    save_json(output_path, final_json)
    print(f"Listo. Resultados guardados en {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Extrae información de un paquete documental PDF.")
    parser.add_argument("pdf", help="Ruta al PDF de entrada")
    parser.add_argument("--profile", default="config/document_profile_solicitud_digital.json", help="Ruta al JSON del perfil de documento")
    parser.add_argument("--output", default="resultado_pack.json", help="Ruta del JSON de salida")
    
    args = parser.parse_args()
    process_pack(args.pdf, args.profile, args.output)

if __name__ == "__main__":
    main()

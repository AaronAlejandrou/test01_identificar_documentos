import argparse
import json
import os
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import fitz
import numpy as np

# Reutilizamos las funciones de extract_local
from app.services.extract_local import (
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
    Extrae el texto de la página y cuenta cuántos 'page_identifiers'
    de cada plantilla están presentes. Retorna el nombre de la plantilla
    con mayor coincidencia (score).
    """
    page_text = page.get_text("text").lower()
    page_text = clean_text(page_text)
    
    best_template = None
    best_score = 0
    
    for tmpl_name, tmpl_data in templates.items():
        identifiers = tmpl_data.get("page_identifiers", [])
        score = 0
        for ident in identifiers:
            if ident.lower() in page_text:
                score += 1
                
        if score > best_score and score > 0:
            best_score = score
            best_template = tmpl_name
            
    return best_template


def consolidate_results(pages_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Consolida los resultados de todas las páginas en un solo objeto
    y aplica las reglas de negocio/validaciones solicitadas.
    """
    consolidated = {
        "fields": {},
        "checks": {},
        "signatures": {},
        "tables": {},
        "validations": []
    }
    
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
                
        # Merge tables
        for k, v in page_res["data"].get("tables", {}).items():
            if v:
                consolidated["tables"][k] = v
                
    # ==========================================
    # APLICACIÓN DE REGLAS DE NEGOCIO
    # ==========================================
    
    # 1. Validación cruzada de propuesta_numero
    if "propuesta_numero" in field_sources and len(field_sources["propuesta_numero"]) > 1:
        first_val = field_sources["propuesta_numero"][0]["value"]
        for entry in field_sources["propuesta_numero"][1:]:
            if entry["value"] != first_val:
                consolidated["validations"].append(
                    f"CRUZADA: Discrepancia en propuesta_numero: pág {field_sources['propuesta_numero'][0]['page']} ({first_val}) "
                    f"vs pág {entry['page']} ({entry['value']})"
                )

    # 2. Validación cruzada de nombre/documento asegurado
    aseg_nom = consolidated["fields"].get("asegurado_nombres", {}).get("value", "")
    aseg_doc = consolidated["fields"].get("asegurado_numero_documento", {}).get("value", "")
    nota_aseg_nom = consolidated["fields"].get("asegurado_nombre_nota", {}).get("value", "")
    nota_aseg_doc = consolidated["fields"].get("asegurado_doc_nota", {}).get("value", "")
    
    if aseg_nom and nota_aseg_nom and aseg_nom.lower() not in nota_aseg_nom.lower() and nota_aseg_nom.lower() not in aseg_nom.lower():
        consolidated["validations"].append(f"CRUZADA: Nombre de asegurado difiere entre Solicitud ({aseg_nom}) y Nota ({nota_aseg_nom})")
    if aseg_doc and nota_aseg_doc and aseg_doc != nota_aseg_doc:
        consolidated["validations"].append(f"CRUZADA: Documento de asegurado difiere entre Solicitud ({aseg_doc}) y Nota ({nota_aseg_doc})")

    # 3. Datos fantasmas del contratante
    cont_nom = consolidated["fields"].get("contratante_nombre", {}).get("value", "")
    
    # Si contratante_nombre no vino, o es exactamente igual al asegurado, limpiamos sus campos
    if not cont_nom or (aseg_nom and aseg_nom.lower() == cont_nom.lower()):
        keys_to_remove = [k for k in consolidated["fields"] if k.startswith("contratante_")]
        for k in keys_to_remove:
            del consolidated["fields"][k]
            
        keys_to_remove_checks = [k for k in consolidated["checks"] if k.startswith("contratante_")]
        for k in keys_to_remove_checks:
            del consolidated["checks"][k]
            
        consolidated["validations"].append("NEGOCIO: Contratante vacío o igual a asegurado. Datos del contratante omitidos.")

    # 4. Suma de beneficiarios = 100%
    total_pct = 0.0
    for i in range(1, 4):
        pct_str = consolidated["fields"].get(f"beneficiario_{i}_porcentaje", {}).get("value", "")
        if pct_str:
            try:
                val = float(pct_str.replace("%", "").strip())
                total_pct += val
            except ValueError:
                pass
                
    if total_pct > 0 and total_pct != 100.0:
        consolidated["validations"].append(f"NEGOCIO: La sumatoria de porcentajes de beneficiarios es {total_pct}%, debería ser 100%.")

    # 5. Consistencia de monto a pagar (pag 8) vs prima_total (pag 2)
    monto_pagar = consolidated["fields"].get("monto_pagar", {}).get("value", "")
    prima_total = consolidated["fields"].get("prima_total", {}).get("value", "")
    if monto_pagar and prima_total and monto_pagar != prima_total:
        consolidated["validations"].append(f"CRUZADA: Monto a pagar final ({monto_pagar}) difiere de prima_total ({prima_total})")

    # 6 y 7. Tablas vacías y dependencias (Ej: fuma_detalle depende de fuma)
    fuma_val = consolidated["checks"].get("fuma", {}).get("selected", "")
    if fuma_val != "Si" and "fuma_detalle" in consolidated["fields"]:
        del consolidated["fields"]["fuma_detalle"]
        consolidated["validations"].append("NEGOCIO: Fuma es No/Vacío, se omitió fuma_detalle.")
        
    alcohol_val = consolidated["checks"].get("alcohol", {}).get("selected", "")
    if alcohol_val != "Si" and "alcohol_detalle" in consolidated["fields"]:
        del consolidated["fields"]["alcohol_detalle"]
        
    drogas_val = consolidated["checks"].get("drogas", {}).get("selected", "")
    if drogas_val != "Si" and "drogas_fecha" in consolidated["fields"]:
        del consolidated["fields"]["drogas_fecha"]

    return consolidated


def process_pack(pdf_path: str, profile_path: str, output_path: Optional[str] = None):
    profile = load_json(profile_path)
    base_dir = os.path.dirname(profile_path)
    
    templates = {}
    for tmpl_name in profile.get("page_templates", []):
        clean_tmpl_name = tmpl_name.replace('.json', '')
        tmpl_path = os.path.join(base_dir, f"{clean_tmpl_name}.json")
        if os.path.exists(tmpl_path):
            templates[clean_tmpl_name] = load_json(tmpl_path)
        else:
            print(f"Advertencia: No se encontró la plantilla {tmpl_path}")
            
    doc = fitz.open(pdf_path)
    ocr_engine = create_ocr_engine()
    
    pages_results = []
    
    print(f"Procesando documento: {pdf_path} ({doc.page_count} páginas)")
    
    for i in range(doc.page_count):
        page = doc[i]
        
        template_name = detect_page_template(page, templates)
        
        if not template_name:
            # Fallback a índice directo si la IA no detecta 'page_identifiers'
            page_templates_list = profile.get("page_templates", [])
            if i < len(page_templates_list):
                tmpl_name_fallback = page_templates_list[i].replace('.json', '')
                if tmpl_name_fallback in templates:
                    template_name = tmpl_name_fallback
                    print(f" - Pág {i+1}: MATCH FALLBACK - Usando plantilla por orden '{template_name}'")

        if not template_name:
            print(f" - Pág {i+1}: WARNING - Ninguna plantilla hizo match con el texto de la página. (Omitiendo)")
            continue
            
        print(f" - Pág {i+1}: Plantilla detectada -> {template_name}")
        
        cfg = templates[template_name]
        canonical = cfg.get("canonical", {"width": 2480, "height": 3508})
        canonical_w = int(canonical["width"])
        canonical_h = int(canonical["height"])
        
        page_image, _ = render_pdf_page(doc, i, canonical_w, canonical_h)
        page_res = extract_page_fields(page_image, page, cfg, ocr_engine)
        
        pages_results.append({
            "page_index": i,
            "template": template_name,
            "data": page_res
        })
        
    print("\nConsolidando resultados y aplicando validaciones...")
    consol = consolidate_results(pages_results)
    final_json = {
        "document_type": profile.get("document_type", "unknown"),
        "source_file": pdf_path,
        "pages_processed": len(pages_results),
        "consolidated": consol,
        "pages_raw": pages_results
    }
    
    if output_path:
        save_json(output_path, final_json)
        print(f"Listo. Resultados guardados en {output_path}")

    doc.close()
    return final_json

def process_single_page(pdf_path: str, profile_path: str, page_index: int):
    profile = load_json(profile_path)
    base_dir = os.path.dirname(profile_path)
    
    templates = {}
    for tmpl_name in profile.get("page_templates", []):
        clean_tmpl_name = tmpl_name.replace('.json', '')
        tmpl_path = os.path.join(base_dir, f"{clean_tmpl_name}.json")
        if os.path.exists(tmpl_path):
            templates[clean_tmpl_name] = load_json(tmpl_path)
            
    doc = fitz.open(pdf_path)
    ocr_engine = create_ocr_engine()
    
    if page_index < 0 or page_index >= doc.page_count:
        doc.close()
        raise ValueError(f"Índice de página {page_index} fuera de rango")
        
    page = doc[page_index]
    template_name = detect_page_template(page, templates)
    
    if not template_name:
        page_templates_list = profile.get("page_templates", [])
        if page_index < len(page_templates_list):
            tmpl_name_fallback = page_templates_list[page_index].replace('.json', '')
            if tmpl_name_fallback in templates:
                template_name = tmpl_name_fallback
                
    if not template_name:
        doc.close()
        raise ValueError(f"No se pudo detectar plantilla para la página {page_index}")
        
    cfg = templates[template_name]
    canonical = cfg.get("canonical", {"width": 2480, "height": 3508})
    canonical_w = int(canonical["width"])
    canonical_h = int(canonical["height"])
    
    page_image, _ = render_pdf_page(doc, page_index, canonical_w, canonical_h)
    page_res = extract_page_fields(page_image, page, cfg, ocr_engine)
    
    doc.close()
    
    return {
        "page_index": page_index,
        "template": template_name,
        "data": page_res
    }

def main():
    parser = argparse.ArgumentParser(description="Extrae información de un paquete documental PDF.")
    parser.add_argument("pdf", help="Ruta al PDF de entrada")
    parser.add_argument("--profile", default="config/document_profile_solicitud_digital.json", help="Ruta al JSON del perfil de documento")
    parser.add_argument("--output", default="resultado_pack.json", help="Ruta del JSON de salida")
    
    args = parser.parse_args()
    process_pack(args.pdf, args.profile, args.output)

if __name__ == "__main__":
    main()

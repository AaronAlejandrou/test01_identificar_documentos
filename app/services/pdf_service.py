import os
import uuid
import fitz
import cv2
import numpy as np
from app.core.config import settings

def split_pdf_to_images(pdf_path: str) -> dict:
    """
    Toma un PDF, divide cada página en una imagen, la guarda en uploads y retorna sus rutas.
    """
    doc_id = str(uuid.uuid4())
    doc_dir = os.path.join(settings.UPLOAD_DIR, doc_id)
    os.makedirs(doc_dir, exist_ok=True)
    
    doc = fitz.open(pdf_path)
    total_pages = doc.page_count
    saved_pages = []
    
    for i in range(total_pages):
        page = doc[i]
        zoom = settings.DEFAULT_DPI / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        # Convert to numpy array for resizing to canonical size
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        
        # Resize to canonical
        img_resized = cv2.resize(img, (settings.CANONICAL_WIDTH, settings.CANONICAL_HEIGHT), interpolation=cv2.INTER_CUBIC)
        
        filename = f"page_{i}.png"
        filepath = os.path.join(doc_dir, filename)
        cv2.imwrite(filepath, img_resized)
        
        # Return a relative path to be served statically
        saved_pages.append(f"{doc_id}/{filename}")
        
    return {
        "document_id": doc_id,
        "total_pages": total_pages,
        "pages": saved_pages,
        "local_dir": doc_dir
    }

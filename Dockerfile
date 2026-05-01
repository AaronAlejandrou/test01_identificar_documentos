# Dockerfile para la API OCR de Interseguro

# Usamos una imagen ligera de Python 3.10
FROM python:3.10-slim

# Evitar que python escriba *.pyc y se salte prompts interactivos
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instalar dependencias del sistema necesarias para OpenCV y PyMuPDF en linux
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Crear y fijar directorio de trabajo
WORKDIR /app

# Copiar requirements y hacer los ajustes para modo Headless
# Nota: Quitamos PySide6 para no inflar la imagen inútilmente ya que es solo para la UI de calibración local.
COPY requirements.txt .
RUN sed -i 's/opencv-python/opencv-python-headless/g' requirements.txt && \
    sed -i '/PySide6/d' requirements.txt

# Instalar los paquetes
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos todo el código y assets (config/, etc.)
COPY . .

# Exponemos el puerto
EXPOSE 8000

# Arrancamos Uvicorn
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]

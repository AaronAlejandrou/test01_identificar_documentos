# Interseguro Local Simple

Versión local, simple y fácil de manipular.

## Qué hace
- Lee **PDF o imagen**.
- Si el archivo es PDF, intenta primero **extraer texto nativo** dentro de cada bloque.
- Si un bloque no tiene texto nativo, usa **PaddleOCR** solo en ese bloque.
- Detecta radios como **Carta, Fax, Teléfono** por píxeles.
- Permite **calibrar cajas y radios** localmente y guardar el JSON.

## Archivos
- `extract_local.py`: extrae la información.
- `inspect_blocks.py`: dibuja bloques y genera overlay.
- `calibrate_blocks.py`: te deja ajustar bloques y radios con el mouse.
- `config/form_blocks_interseguro.json`: configuración editable.

## Instalación simple
```bash
pip install -r requirements.txt
```

## Ver los bloques
```bash
python inspect_blocks.py "tu_archivo.pdf" --config config/form_blocks_interseguro.json --output overlay.png --ranges rangos.txt
```

## Calibrar bloques de texto
```bash
python calibrate_blocks.py "tu_archivo.pdf" --config config/form_blocks_interseguro.json --mode text
```

## Calibrar bloques de firma
```bash
python calibrate_blocks.py "tu_archivo.pdf" --config config/form_blocks_interseguro.json --mode sign
```

## Calibrar radios
```bash
python calibrate_blocks.py "tu_archivo.pdf" --config config/form_blocks_interseguro.json --mode radio
```

## Extraer información
```bash
python extract_local.py "tu_archivo.pdf" --config config/form_blocks_interseguro.json --output resultado.json --save-debug
```

## Recomendación práctica
1. Corre `inspect_blocks.py`
2. Ajusta con `calibrate_blocks.py`
3. Repite `inspect_blocks.py` hasta que quede perfecto
4. Recién corre `extract_local.py`

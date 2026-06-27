<div align="center">

# LT

### Herramientas de automatizacion en Python

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-00FF00?style=for-the-badge)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=for-the-badge)](https://github.com/TAKATOx5/LeoTools)

---

</div>

## Instalacion

```bash
# Clonar el repositorio
git clone https://github.com/TAKATOx5/LeoTools.git
cd leotools

# Crear entorno virtual
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Instalar dependencias
pip install -e .
```

## Uso

```bash
lt [comando] [opciones]
```

---

## Comandos

### `lt img2pdf`

Convierte imagenes a PDF con opciones de mejora.

| Opcion | Descripcion |
|--------|-------------|
| `--output, -o` | Nombre del PDF |
| `--sort, -s` | Ordenar por `name` o `date` |
| `--quality, -q` | Calidad: `original`, `media`, `baja` |
| `--enhance, -e` | Mejorar imagen (ver abajo) |
| `--open, -a` | Abrir PDF al terminar |

#### Modos de mejora (`--enhance`)

| Modo | Efecto |
|------|--------|
| `doc` | Brillo +30%, Contraste +50%, Nitidez +20% |
| `shadows` | Ecualiza histograma, reduce sombras oscuras |
| `binarize` | Blanco y negro puro (maxima legibilidad) |
| `all` | Todas las mejoras combinadas |

#### Ejemplos

```bash
# Modo interactivo
lt img2pdf

# Crear PDF con opciones
lt img2pdf -o asistencia.pdf -s date -q media

# Mejorar fotos con sombras
lt img2pdf -o lista.pdf -e shadows

# Blanco y negro para documentos
lt img2pdf -o reporte.pdf -e binarize

# Todo junto + abrir al terminar
lt img2pdf -o final.pdf -e all -s date --open
```

#### Orden manual (modo interactivo)

```
2,1,4,3       Orden especifico
5-8,1,3       Rangos
3,2,1,5-8     Mezcla
Enter          Mismo orden
```

---

### `lt update`

Actualiza LeoTools desde GitHub.

```bash
lt update           # Descargar ultima version
lt update --check   # Solo verificar si hay actualizaciones
```

---

## Estructura del proyecto

```
LeoTools/
├── leotools/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── commands/
│   │   ├── img2pdf.py
│   │   └── update.py
│   └── utils/
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## Agregar un nuevo comando

1. Crear archivo en `leotools/commands/nuevo_comando.py`:

```python
import typer

app = typer.Typer(help="Descripcion del comando", invoke_without_command=True)

@app.callback(invoke_without_command=True)
def main():
    print("Hola desde nuevo comando")
```

2. Registrar en `leotools/cli.py`:

```python
from leotools.commands import nuevo_comando

app.add_typer(nuevo_comando.app, name="nuevo-comando")
```

3. Listo. Ejecuta con `lt nuevo-comando`

---

## Roadmap

- [x] `lt img2pdf` - Convertir imagenes a PDF
- [ ] `lt pdf2img` - Extraer imagenes de PDF
- [ ] `lt rename` - Renombrar archivos en lote
- [ ] `lt resize` - Redimensionar imagenes
- [ ] `lt mergepdf` - Unir multiples PDFs
- [ ] `lt splitpdf` - Separar paginas de un PDF
- [ ] `lt excel` - Herramientas para Excel
- [ ] `lt clean` - Limpiar archivos temporales
- [ ] `lt zip` - Comprimir/descomprimir archivos
- [ ] `lt hash` - Generar hashes de archivos

---

## Licencia

MIT License - Ver [LICENSE](LICENSE) para detalles.

---

<div align="center">

Hecho con Python

</div>

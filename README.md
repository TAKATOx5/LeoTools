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

Convierte imagenes a PDF con interfaz interactiva, progreso en vivo y opciones de mejora.

| Opcion | Descripcion |
|--------|-------------|
| `--output, -o` | Nombre del PDF |
| `--sort, -s` | Ordenar por `name` o `date` |
| `--quality, -q` | Calidad: `original`, `media`, `baja` |
| `--enhance, -e` | Mejorar imagen (ver abajo) |
| `--open, -a` | Abrir PDF al terminar |
| `??` | Mostrar ayuda detallada |

#### Caracteristicas dinamicas

- **Tabla con dimensiones**: Muestra ancho x alto de cada imagen, tamano y fecha
- **Barra de progreso**: Indicador visual mientras se procesan las imagenes
- **Panel de resumen**: Muestra calidad, mejora aplicada y destino antes de generar
- **Confirmacion final**: Tamano del PDF generado y ubicacion exacta
- **Prompts con validacion**: Entrada de datos con valores por defecto y opciones guiadas

#### Modos de mejora (`--enhance`)

| Modo | Efecto |
|------|--------|
| `doc` | Brillo +30%, Contraste +50%, Nitidez +20% |
| `shadows` | Ecualiza histograma, reduce sombras oscuras |
| `binarize` | Blanco y negro puro (maxima legibilidad) |
| `all` | Todas las mejoras combinadas |

#### Ejemplos

```bash
# Modo interactivo (guiado paso a paso)
lt img2pdf

# Modo automatico (sin preguntas)
lt img2pdf -o asistencia.pdf

# Ordenado por fecha, calidad media
lt img2pdf -o tarea.pdf -s date -q media

# Mejorar fotos con sombras
lt img2pdf -o lista.pdf -e shadows

# Blanco y negro para documentos escaneados
lt img2pdf -o reporte.pdf -e binarize

# Todo junto + abrir al terminar
lt img2pdf -o final.pdf -e all -s date --open
```

#### Orden manual (solo interactivo)

```
2,1,4,3       Orden especifico
5-8,1,3       Rangos
3,2,1,5-8     Mezcla
Enter          Mismo orden (default)
```

---

### `lt jsoncmp`

Compara dos archivos JSON (por ejemplo, dos exportaciones de IDs/descripciones) y muestra que claves faltan y que valores cambiaron.

| Opcion | Descripcion |
|--------|-------------|
| `ARCHIVO_A` | Primer archivo JSON |
| `ARCHIVO_B` | Segundo archivo JSON |
| `--output, -o` | Guarda el reporte de diferencias en un JSON |
| `--limit, -l` | Maximo de diferencias a mostrar (0 = todas) |

#### Que detecta

- **Solo en A / Solo en B**: claves (IDs) que existen en un archivo y no en el otro
- **Valor distinto**: claves presentes en ambos con contenido diferente (incluye cambios anidados)
- **Sin cambios**: claves identicas

#### Ejemplos

```bash
# Comparar los archivos por defecto
lt jsoncmp

# Comparar dos archivos concretos
lt jsoncmp a.json b.json

# Exportar el reporte completo a un archivo
lt jsoncmp a.json b.json -o diferencias.json

# Mostrar todas las diferencias en pantalla
lt jsoncmp a.json b.json -l 0
```

---

### `lt update`

Actualiza LeoTools desde GitHub.

```bash
lt update           # Descargar ultima version
lt update --check   # Solo verificar si hay actualizaciones
```

---

### `lt git`

Automatiza `git add` + `git commit` + `git push` en el proyecto actual (la carpeta donde estes parado).

| Opcion | Descripcion |
|--------|-------------|
| `MENSAJE` | Mensaje del commit (posicional o `-m`) |
| `DESCRIPCION` | Cuerpo del commit, opcional (posicional o `-d`) |

#### Ejemplos

```bash
# Guardar y subir con un mensaje
lt git push "Init rework paselista"

# Con descripcion (cuerpo del commit)
lt git push "Init rework paselista" "Se agregan docs de RRHH"

# Con banderas
lt git push -m "Fix login" -d "Corrige validacion de token"

# Sin argumentos: pregunta el mensaje
lt git push
```

Si el remoto no tiene upstream, lo configura automaticamente (`git push -u origin <rama>`).

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
- [x] `lt jsoncmp` - Comparar dos archivos JSON
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

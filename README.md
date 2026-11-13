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
cd LeoTools

# Crear entorno virtual
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Instalar el paquete (comando `lt`)
pip install -e .

# Instalar dependencias de imagenes y consola
pip install -r requirements.txt
```

> **Tip:** agrega `C:\ruta\a\LeoTools\.venv\Scripts` al `PATH` de Windows y podras
> usar `lt` desde cualquier carpeta.

## Configuracion (`.env`)

Algunos comandos leen un archivo `.env` en la raiz del proyecto (esta en `.gitignore`):

```env
# MySQL / XAMPP (lt db, lt drop)
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=

# Rutas de los binarios (opcional, si no estan en C:\xampp)
MYSQL_BIN=C:\xampp\mysql\bin\mysql.exe
MYSQLDUMP_BIN=C:\xampp\mysql\bin\mysqldump.exe

# WiFi (lt hills)
WIFI_HILLS_PASSWORD=tu_password
```

## Uso

```bash
lt [comando] [opciones]
```

- `lt ??` muestra la guia general con todos los comandos.
- `lt <comando> ??` muestra la ayuda detallada de cada comando.

| Comando | Descripcion |
|---------|-------------|
| `lt img2pdf` | Convierte imagenes de la carpeta actual a un PDF |
| `lt jsoncmp` | Compara dos archivos JSON y muestra sus diferencias |
| `lt db` | Bases de datos MySQL (import, export, drop, reset) |
| `lt drop` | Borra los datos de las tablas e importa un `.sql` en un paso |
| `lt code` | Abre VS Code con los proyectos (local + SSH) |
| `lt hills` | Conecta a la red WiFi `SL_Hills` sin pedir contrasena |
| `lt domicilios` | Abre los paneles de Domicilios Fiscales en Opera |
| `lt mei` | Abre los paneles de Novedades MeiMei en Opera |
| `lt git` | Automatiza `git add` + `git commit` + `git push` |
| `lt update` | Actualiza LeoTools o sube cambios con Git/GitHub |

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

### `lt db`

Gestiona bases de datos MySQL de XAMPP (import, export, drop de datos y reset de estructura).

Sin argumentos abre un flujo interactivo que pregunta la base, la accion y el archivo.

| Subcomando | Descripcion |
|------------|-------------|
| `lt db` | Flujo interactivo (elegir base, importar/exportar) |
| `lt db list` | Lista las bases de datos del servidor |
| `lt db tables [BASE]` | Lista las tablas de una base |
| `lt db import ARCHIVO.sql -d BASE` | Importa un dump (FK desactivadas, respaldo previo) |
| `lt db export [BASE] --path=out.sql` | Exporta la base completa |
| `lt db drop [BASE] [--path=dump.sql]` | Borra los DATOS de las tablas (no la estructura) |
| `lt db reset ARCHIVO.sql -d BASE` | Borra la ESTRUCTURA y la recrea desde el dump |

#### Opciones comunes

| Opcion | Descripcion |
|--------|-------------|
| `-d, --db` | Nombre de la base de datos (default: `baseproject`) |
| `-p, --path` | Ruta del archivo `.sql` |
| `-y, --yes` | No pedir confirmacion |
| `-c, --create` | Crear la base de datos si no existe |
| `--data-only` | Exportar solo datos (sin estructura) |
| `--truncate, -t` | Vaciar las tablas antes de importar |
| `--no-truncate` | En `db drop`, solo importar sin borrar datos |

#### Seguridad

Antes de borrar o importar se crea un **respaldo automatico**. Si la operacion falla,
se hace **rollback** y se avisa si la base quedo intacta.

#### Ejemplos

```bash
# Ver bases y tablas
lt db list
lt db tables baseproject

# Importar un dump (pide confirmacion solo si usas --truncate)
lt db import dump.sql -d baseproject
lt db import dump.sql -d baseproject --truncate -y

# Exportar
lt db export baseproject --path=respaldo.sql
lt db export baseproject --path=datos.sql --data-only

# Borrar datos e importar en un solo paso
lt db drop baseproject --path=dump.sql

# Recrear la base desde cero
lt db reset dump.sql -d baseproject
```

---

### `lt drop`

Borra los **datos** de las tablas (no la estructura) e importa un `.sql` en un paso.
Crea un respaldo antes de empezar y hace rollback si algo falla.

| Opcion | Descripcion |
|--------|-------------|
| `--path, -p` | Ruta del archivo `.sql` a importar (obligatorio) |
| `--db, -d` | Nombre de la base de datos (default: `baseproject`) |
| `--yes, -y` | No pedir confirmacion |
| `??` | Mostrar ayuda detallada |

#### Ejemplos

```bash
lt drop tables -d baseproject --path=C:\ruta\dump.sql
lt drop tables --path="C:\ruta con espacios\dump.sql" -y
```

---

### `lt code`

Abre **VS Code** con los proyectos, en local y por SSH al mismo tiempo.

| Subcomando | Proyecto |
|------------|----------|
| `lt code ligero` | `catorcePlatform` (local + servidor) |
| `lt code scopio` | `scopioPlatform` (local + servidor) |

| Opcion | Descripcion |
|--------|-------------|
| `--local, -l` | Solo abrir la carpeta local |
| `--ssh, -s` | Solo abrir la conexion SSH |
| `??` | Mostrar ayuda detallada |

#### Ejemplos

```bash
lt code ligero            # Abre local + SSH
lt code ligero -l         # Solo local
lt code scopio -s         # Solo SSH
```

> Las rutas locales y los hosts SSH estan configurados en
> `leotools/commands/code.py` (`LIGERO_*` y `SCOPIO_*`). Ajustalos a tu equipo.

---

### `lt hills`

Conecta o reconecta a la red WiFi `SL_Hills` sin pedir la contrasena.
La contrasena se lee de `WIFI_HILLS_PASSWORD` en el `.env`.

| Opcion | Descripcion |
|--------|-------------|
| `--check, -c` | Solo verifica si estas conectado |
| `??` | Mostrar ayuda detallada |

#### Ejemplos

```bash
lt hills            # Conectar / reconectar
lt hills --check    # Ver estado
```

> Usa `netsh wlan` (solo Windows). Si falla, olvida la red en Windows y vuelve a ejecutar.

---

### `lt domicilios`

Abre en **Opera** la pagina principal de Domicilios Fiscales y los paneles de
Marketing (Analytics, Search Console, AdSense) y/o Dev (Vercel, Supabase).

| Opcion | Descripcion |
|--------|-------------|
| `--mkt, -m` | Marketing (pagina principal + marketing) |
| `--dev, -d` | Dev (pagina principal + dev) |
| `--all, -a` | Todo |
| `??` | Mostrar ayuda detallada |

Sin opciones muestra un menu para elegir que abrir.

#### Ejemplos

```bash
lt domicilios             # Menu interactivo
lt domicilios -m          # Solo marketing
lt domicilios -d          # Solo dev
lt domicilios -m -d       # Marketing + dev
lt domicilios -a          # Todo
```

---

### `lt mei`

Abre en **Opera** los paneles de desarrollo de Novedades MeiMei (Vercel + Supabase).

| Opcion | Descripcion |
|--------|-------------|
| `--dev, -d` | Abrir dev |
| `--all, -a` | Abrir todo |
| `??` | Mostrar ayuda detallada |

#### Ejemplos

```bash
lt mei            # Menu interactivo
lt mei -d         # Solo dev
lt mei -a         # Todo
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

### `lt update`

Actualiza LeoTools desde GitHub o sube tus cambios locales.

| Opcion | Descripcion |
|--------|-------------|
| `--check, -c` | Solo verificar si hay actualizaciones |
| `--push, -p` | Subir cambios (commit + push) sin preguntar |
| `--message, -m` | Mensaje del commit al subir |
| `??` | Mostrar ayuda detallada |

#### Ejemplos

```bash
lt update                 # Verifica y pregunta que hacer (pull / push)
lt update --check         # Solo verificar
lt update --push -m "Agrega comando mei"
```

Si hay actualizaciones en GitHub pregunta si hacer `pull`; si detecta cambios
locales sin subir, pregunta si hacer `commit` + `push`.

---

## Estructura del proyecto

```
LeoTools/
├── leotools/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── commands/
│   │   ├── code.py
│   │   ├── db.py
│   │   ├── domicilios.py
│   │   ├── drop.py
│   │   ├── git.py
│   │   ├── hills.py
│   │   ├── img2pdf.py
│   │   ├── jsoncmp.py
│   │   ├── mei.py
│   │   └── update.py
│   └── utils/
│       ├── browser.py
│       └── files.py
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

3. Agregar el comando a la tabla de `show_guide()` en `cli.py` para que aparezca en `lt ??`.

4. Listo. Ejecuta con `lt nuevo-comando`.

---

## Roadmap

- [x] `lt img2pdf` - Convertir imagenes a PDF
- [x] `lt jsoncmp` - Comparar dos archivos JSON
- [x] `lt db` - Import/export/drop/reset de MySQL (XAMPP)
- [x] `lt drop` - Borrar datos e importar un dump en un paso
- [x] `lt code` - Abrir proyectos en VS Code (local + SSH)
- [x] `lt hills` - Conectar a la red WiFi `SL_Hills`
- [x] `lt domicilios` - Paneles de Domicilios Fiscales en Opera
- [x] `lt mei` - Paneles de Novedades MeiMei en Opera
- [x] `lt git` - add + commit + push del proyecto actual
- [x] `lt update` - Actualizar LeoTools desde GitHub
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

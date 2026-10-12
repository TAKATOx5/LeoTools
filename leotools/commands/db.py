import glob
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pymysql
import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

app = typer.Typer(
    help="Gestiona bases de datos MySQL de XAMPP (import, export, drop de datos).",
    invoke_without_command=True,
)

console = Console()

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

COLOR_ACCENT = "bright_blue"

PROJECT_ROOT = Path(__file__).parent.parent.parent

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 3306
DEFAULT_USER = "root"
DEFAULT_PASSWORD = ""
DEFAULT_DB = "baseproject"

SYSTEM_DBS = {"information_schema", "performance_schema", "mysql", "sys"}

MYSQL_CANDIDATES = [
    r"C:\xampp\mysql\bin\mysql.exe",
    r"C:\xampp\mysql\bin\mysql",
    "/usr/bin/mysql",
]

MYSQLDUMP_CANDIDATES = [
    r"C:\xampp\mysql\bin\mysqldump.exe",
    r"C:\xampp\mysql\bin\mysqldump",
    "/usr/bin/mysqldump",
]


class DbError(Exception):
    pass


HELP_TEXT = f"""
[bold {COLOR_ACCENT}]lt db[/bold {COLOR_ACCENT}] - Bases de datos MySQL (XAMPP)

[bold]Sin argumentos (interactivo):[/bold]
  [green]lt db[/green]                     Pregunta que base, si importar/exportar y demas

[bold]Uso directo:[/bold]
  [green]lt db list[/green]                              Lista las bases de datos
  [green]lt db tables baseproject[/green]                Lista las tablas
  [green]lt db drop baseproject[/green]                  Borra los DATOS de las tablas (no las tablas)
  [green]lt db drop baseproject --path=dump.sql[/green]  Borra datos e importa el .sql
  [green]lt db import dump.sql -d baseproject[/green]    Importa un .sql (FK desactivadas)
  [green]lt db import dump.sql -d baseproject --truncate[/green]  Vacia tablas antes de importar
  [green]lt db export baseproject --path=out.sql[/green] Exportacion completa
  [green]lt db export baseproject --path=out.sql --data-only[/green]  Solo datos

[bold]Opciones comunes:[/bold]
  -d, --db          Nombre de la base de datos (default: {DEFAULT_DB})
  -p, --path        Ruta del archivo .sql
  -y, --yes         No pedir confirmacion
  -c, --create      Crear la base de datos si no existe

[bold]Seguridad:[/bold]
  [dim]Antes de borrar/importar se crea un respaldo. Si algo falla se hace
  rollback automatico y se avisa si la base quedo intacta.[/dim]
"""


def load_env() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key.startswith(("DB_", "MYSQL_")):
            os.environ.setdefault(key, value)


def db_config() -> dict:
    load_env()
    return {
        "host": os.environ.get("DB_HOST", DEFAULT_HOST),
        "port": int(os.environ.get("DB_PORT", DEFAULT_PORT)),
        "user": os.environ.get("DB_USER", DEFAULT_USER),
        "password": os.environ.get("DB_PASSWORD", DEFAULT_PASSWORD),
    }


def connect(database: str | None = None):
    cfg = db_config()
    try:
        return pymysql.connect(
            database=database,
            charset="utf8mb4",
            autocommit=True,
            **cfg,
        )
    except pymysql.MySQLError as exc:
        console.print(
            Panel(
                f"[red]No se pudo conectar a MySQL[/red]\n"
                f"[dim]{cfg['host']}:{cfg['port']} como {cfg['user']}[/dim]\n\n"
                f"{exc}\n\n"
                "[yellow]Verifica que MySQL este corriendo en XAMPP.[/yellow]",
                title="[red]Error de conexion[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(1)


def find_mysql() -> str | None:
    env_bin = os.environ.get("MYSQL_BIN")
    if env_bin and Path(env_bin).exists():
        return env_bin
    which = shutil.which("mysql")
    if which:
        return which
    for candidate in MYSQL_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return None


def find_mysqldump() -> str | None:
    env_bin = os.environ.get("MYSQLDUMP_BIN")
    if env_bin and Path(env_bin).exists():
        return env_bin
    which = shutil.which("mysqldump")
    if which:
        return which
    for candidate in MYSQLDUMP_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return None


def _client_env() -> tuple[dict, dict]:
    cfg = db_config()
    env = os.environ.copy()
    if cfg["password"]:
        env["MYSQL_PWD"] = cfg["password"]
    return cfg, env


def user_databases() -> list[str]:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW DATABASES")
            rows = [row[0] for row in cur.fetchall()]
    finally:
        conn.close()
    return [name for name in rows if name not in SYSTEM_DBS]


def table_names(db: str) -> list[str]:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema=%s AND table_type='BASE TABLE'",
                (db,),
            )
            return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def _quiet_query(sql: str, args=None) -> list[str]:
    try:
        cfg = db_config()
        conn = pymysql.connect(charset="utf8mb4", **cfg)
        try:
            with conn.cursor() as cur:
                cur.execute(sql, args)
                return [row[0] for row in cur.fetchall()]
        finally:
            conn.close()
    except BaseException:
        return []


def complete_databases(incomplete: str) -> list[str]:
    names = [n for n in _quiet_query("SHOW DATABASES") if n not in SYSTEM_DBS]
    return [n for n in names if n.lower().startswith(incomplete.lower())]


def complete_tables(ctx: typer.Context, incomplete: str) -> list[str]:
    database = ctx.params.get("db_arg") or ctx.params.get("db") or DEFAULT_DB
    names = _quiet_query(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema=%s AND table_type='BASE TABLE'",
        (database,),
    )
    return [n for n in names if n.lower().startswith(incomplete.lower())]


def complete_path(incomplete: str) -> list[str]:
    matches = glob.glob(incomplete + "*") if incomplete else glob.glob("*")
    return [m + os.sep if os.path.isdir(m) else m for m in matches]


def ensure_database(db: str) -> None:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"
            )
    finally:
        conn.close()


def truncate_all(db: str) -> int:
    tables = table_names(db)
    if not tables:
        return 0
    conn = connect(db)
    try:
        with conn.cursor() as cur:
            cur.execute("SET FOREIGN_KEY_CHECKS=0")
            try:
                for name in tables:
                    cur.execute(f"TRUNCATE TABLE `{db}`.`{name}`")
            finally:
                cur.execute("SET FOREIGN_KEY_CHECKS=1")
    except pymysql.MySQLError as exc:
        raise DbError(str(exc))
    finally:
        conn.close()
    return len(tables)


def drop_all(db: str) -> int:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema=%s AND table_type='BASE TABLE'",
                (db,),
            )
            tables = [row[0] for row in cur.fetchall()]
            cur.execute(
                "SELECT table_name FROM information_schema.views WHERE table_schema=%s",
                (db,),
            )
            views = [row[0] for row in cur.fetchall()]

            if not tables and not views:
                return 0

            cur.execute("SET FOREIGN_KEY_CHECKS=0")
            try:
                for name in views:
                    cur.execute(f"DROP VIEW IF EXISTS `{db}`.`{name}`")
                for name in tables:
                    cur.execute(f"DROP TABLE IF EXISTS `{db}`.`{name}`")
            finally:
                cur.execute("SET FOREIGN_KEY_CHECKS=1")
    finally:
        conn.close()
    return len(tables) + len(views)


def import_database(sql_path: Path, db: str) -> None:
    mysql_bin = find_mysql()
    if not mysql_bin:
        raise DbError(
            "No se encontro el cliente mysql. Instala XAMPP o define MYSQL_BIN en el .env"
        )

    cfg, env = _client_env()
    args = [mysql_bin, "-h", cfg["host"], "-P", str(cfg["port"]), "-u", cfg["user"], db]

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile("wb", suffix=".sql", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(b"SET FOREIGN_KEY_CHECKS=0;\n")
            with sql_path.open("rb") as src:
                head = src.read(3)
                if head != b"\xef\xbb\xbf":
                    tmp.write(head)
                shutil.copyfileobj(src, tmp)
            tmp.write(b"\nSET FOREIGN_KEY_CHECKS=1;\n")
        with tmp_path.open("rb") as fh:
            result = subprocess.run(args, stdin=fh, capture_output=True, env=env)
    finally:
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass

    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip().replace("\ufeff", "")
        raise DbError(detail or "mysql devolvio un error")


def backup_database(db: str, dest: Path) -> None:
    dump_bin = find_mysqldump()
    if not dump_bin:
        raise DbError(
            "No se encontro mysqldump. Instala XAMPP o define MYSQLDUMP_BIN en el .env"
        )
    cfg, env = _client_env()
    args = [
        dump_bin,
        "-h",
        cfg["host"],
        "-P",
        str(cfg["port"]),
        "-u",
        cfg["user"],
        "--routines",
        "--triggers",
        "--events",
        "--single-transaction",
        "--add-drop-table",
        db,
    ]
    with dest.open("wb") as fh:
        result = subprocess.run(args, stdout=fh, stderr=subprocess.PIPE, env=env)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise DbError(detail or "mysqldump devolvio un error")


def export_database(db: str, dest: Path, data_only: bool) -> None:
    dump_bin = find_mysqldump()
    if not dump_bin:
        raise DbError(
            "No se encontro mysqldump. Instala XAMPP o define MYSQLDUMP_BIN en el .env"
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    cfg, env = _client_env()
    args = [dump_bin, "-h", cfg["host"], "-P", str(cfg["port"]), "-u", cfg["user"]]
    if data_only:
        args += ["--no-create-info", "--skip-triggers"]
    else:
        args += ["--routines", "--triggers", "--events"]
    args += ["--single-transaction", db]
    with dest.open("wb") as fh:
        result = subprocess.run(args, stdout=fh, stderr=subprocess.PIPE, env=env)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise DbError(detail or "mysqldump devolvio un error")


def human_size(num: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} GB"


def print_summary(summary: dict) -> None:
    table = Table(show_header=False, box=None)
    table.add_column("Campo", style="cyan")
    table.add_column("Valor", style="green")
    table.add_row("Base de datos", summary["db"])
    if summary.get("file"):
        table.add_row("Archivo", summary["file"])
    if summary.get("truncated") is not None:
        table.add_row("Tablas vaciadas", str(summary["truncated"]))
    table.add_row("Importacion", "OK" if summary["imported"] else "Falló")
    rollback = summary.get("rolled_back")
    if rollback is None:
        table.add_row("Rollback", "No hizo falta")
    else:
        table.add_row("Rollback", "OK (base intacta)" if rollback else "Falló")
    console.print(Panel(table, title="Resumen", border_style=COLOR_ACCENT, expand=False))


def perform_import(db: str, sql_path: Path, do_truncate: bool) -> dict:
    summary = {
        "db": db,
        "file": sql_path.name,
        "truncated": None,
        "imported": False,
        "rolled_back": None,
    }

    backup_path = Path(tempfile.gettempdir()) / f"lt_backup_{db}.sql"
    console.print("[cyan]Creando respaldo de seguridad...[/cyan]")
    try:
        backup_database(db, backup_path)
    except DbError as exc:
        console.print(
            Panel(
                f"[red]No se pudo crear el respaldo, se cancela por seguridad[/red]\n{exc}",
                title="[red]Error[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(1)

    keep_backup = False
    try:
        if do_truncate:
            summary["truncated"] = truncate_all(db)
            console.print(f"[cyan]Datos borrados en {summary['truncated']} tabla(s).[/cyan]")
        console.print(f"[cyan]Importando[/cyan] [green]{sql_path}[/green] [cyan]...[/cyan]")
        import_database(sql_path, db)
        summary["imported"] = True
    except DbError as exc:
        rollback_error = None
        try:
            drop_all(db)
            import_database(backup_path, db)
            summary["rolled_back"] = True
        except DbError as exc2:
            summary["rolled_back"] = False
            keep_backup = True
            rollback_error = str(exc2)

        console.print(
            Panel(
                f"[red]Falló la importacion[/red]\n{exc}",
                title="[red]Error[/red]",
                border_style="red",
            )
        )
        if summary["rolled_back"]:
            console.print(Panel("[green]Rollback completado: la base quedo como estaba.[/green]", border_style="green"))
        else:
            console.print(
                Panel(
                    f"[red]El rollback tambien falló[/red]\n{rollback_error}\n\n"
                    f"Tu respaldo esta en:\n[bold]{backup_path}[/bold]",
                    title="[red]Atencion[/red]",
                    border_style="red",
                )
            )
        raise typer.Exit(1)
    finally:
        if not keep_backup and backup_path.exists():
            try:
                backup_path.unlink()
            except OSError:
                pass

    return summary


def perform_truncate(db: str) -> int:
    backup_path = Path(tempfile.gettempdir()) / f"lt_backup_{db}.sql"
    console.print("[cyan]Creando respaldo de seguridad...[/cyan]")
    try:
        backup_database(db, backup_path)
    except DbError as exc:
        console.print(Panel(f"[red]No se pudo crear el respaldo[/red]\n{exc}", title="[red]Error[/red]", border_style="red"))
        raise typer.Exit(1)

    try:
        count = truncate_all(db)
    except DbError as exc:
        console.print(Panel(f"[red]Falló al borrar datos[/red]\n{exc}\n\n[cyan]Rollback...[/cyan]", title="[red]Error[/red]", border_style="red"))
        try:
            drop_all(db)
            import_database(backup_path, db)
            console.print(Panel("[green]Rollback completado: la base quedo como estaba.[/green]", border_style="green"))
        except DbError as exc2:
            console.print(Panel(f"[red]Rollback falló[/red]\n{exc2}\n\nRespaldo: {backup_path}", title="[red]Atencion[/red]", border_style="red"))
            backup_path.unlink(missing_ok=True)
            raise typer.Exit(1)
        backup_path.unlink(missing_ok=True)
        raise typer.Exit(1)

    backup_path.unlink(missing_ok=True)
    return count


@app.command("list")
def list_databases(
    help: bool = typer.Option(False, "??", help="Mostrar ayuda"),
):
    if help:
        console.print(Panel(HELP_TEXT, title="db", border_style=COLOR_ACCENT, expand=False))
        raise typer.Exit()

    dbs = user_databases()
    table = Table(show_header=True, header_style=f"bold {COLOR_ACCENT}", box=None)
    table.add_column("Base de datos", style="green")
    for name in dbs:
        table.add_row(name)
    console.print(Panel(table, title=f"{len(dbs)} bases de datos", border_style=COLOR_ACCENT, expand=False))


@app.command("tables")
def list_tables(
    db_arg: str = typer.Argument(None, help="Nombre de la base de datos", autocompletion=complete_databases),
    db: str = typer.Option(None, "--db", "-d", help="Nombre de la base de datos", autocompletion=complete_databases),
    help: bool = typer.Option(False, "??", help="Mostrar ayuda"),
):
    if help:
        console.print(Panel(HELP_TEXT, title="db", border_style=COLOR_ACCENT, expand=False))
        raise typer.Exit()

    database = db_arg or db or DEFAULT_DB
    rows = table_names(database)
    table = Table(show_header=True, header_style=f"bold {COLOR_ACCENT}", box=None)
    table.add_column("Tabla", style="green")
    for name in rows:
        table.add_row(name)
    console.print(Panel(table, title=f"{len(rows)} tablas en {database}", border_style=COLOR_ACCENT, expand=False))


@app.command("drop")
def drop_data(
    db_arg: str = typer.Argument(None, help="Nombre de la base de datos", autocompletion=complete_databases),
    db: str = typer.Option(None, "--db", "-d", help="Nombre de la base de datos", autocompletion=complete_databases),
    path: Path = typer.Option(None, "--path", "-p", help="Archivo .sql a importar tras borrar datos", autocompletion=complete_path),
    no_truncate: bool = typer.Option(False, "--no-truncate", help="No borrar datos, solo importar"),
    yes: bool = typer.Option(False, "--yes", "-y", help="No pedir confirmacion"),
    help: bool = typer.Option(False, "??", help="Mostrar ayuda"),
):
    if help:
        console.print(Panel(HELP_TEXT, title="db", border_style=COLOR_ACCENT, expand=False))
        raise typer.Exit()

    database = db_arg or db or DEFAULT_DB

    if path is not None and not path.exists():
        console.print(Panel(f"[red]Archivo no encontrado:[/red]\n  {path}", title="[red]Error[/red]", border_style="red"))
        raise typer.Exit(1)

    if not yes:
        if path:
            accion = (
                f"Borrar los DATOS de las tablas de [green]{database}[/green] "
                f"e importar [green]{path.name}[/green]?"
                if not no_truncate
                else f"Importar [green]{path.name}[/green] en [green]{database}[/green]?"
            )
        else:
            accion = f"Borrar los DATOS de todas las tablas de [green]{database}[/green] (no las tablas)?"
        if not Confirm.ask(f"[bold red]{accion}[/bold red]", default=False):
            console.print("[yellow]Cancelado[/yellow]")
            raise typer.Exit()

    if path is not None:
        summary = perform_import(database, path, do_truncate=not no_truncate)
        print_summary(summary)
        return

    count = perform_truncate(database)
    if count == 0:
        console.print(f"[yellow]La base {database} no tiene tablas.[/yellow]")
    else:
        console.print(Panel(f"[green]Datos borrados en {count} tabla(s) de {database}.[/green]", border_style="green"))


@app.command("import")
def import_sql(
    sql: Path = typer.Argument(..., help="Archivo .sql a importar", autocompletion=complete_path),
    db: str = typer.Option(DEFAULT_DB, "--db", "-d", help="Nombre de la base de datos", autocompletion=complete_databases),
    truncate: bool = typer.Option(False, "--truncate", "-t", help="Vacia las tablas antes de importar"),
    create: bool = typer.Option(False, "--create", "-c", help="Crear la base de datos si no existe"),
    yes: bool = typer.Option(False, "--yes", "-y", help="No pedir confirmacion"),
    help: bool = typer.Option(False, "??", help="Mostrar ayuda"),
):
    if help:
        console.print(Panel(HELP_TEXT, title="db", border_style=COLOR_ACCENT, expand=False))
        raise typer.Exit()

    if not sql.exists():
        console.print(Panel(f"[red]Archivo no encontrado:[/red]\n  {sql}", title="[red]Error[/red]", border_style="red"))
        raise typer.Exit(1)

    if create:
        ensure_database(db)

    if not yes and truncate:
        if not Confirm.ask(f"[bold red]Vaciar los datos de [green]{db}[/green] e importar [green]{sql.name}[/green]?[/bold red]", default=False):
            console.print("[yellow]Cancelado[/yellow]")
            raise typer.Exit()

    summary = perform_import(db, sql, do_truncate=truncate)
    print_summary(summary)


@app.command("export")
def export_data(
    db_arg: str = typer.Argument(None, help="Nombre de la base de datos", autocompletion=complete_databases),
    db: str = typer.Option(None, "--db", "-d", help="Nombre de la base de datos", autocompletion=complete_databases),
    path: Path = typer.Option(None, "--path", "-p", help="Ruta donde guardar el .sql", autocompletion=complete_path),
    data_only: bool = typer.Option(False, "--data-only", help="Exportar solo datos (sin estructura)"),
    help: bool = typer.Option(False, "??", help="Mostrar ayuda"),
):
    if help:
        console.print(Panel(HELP_TEXT, title="db", border_style=COLOR_ACCENT, expand=False))
        raise typer.Exit()

    database = db_arg or db or DEFAULT_DB
    dest = path or Path.cwd() / f"{database}_{'datos' if data_only else 'completa'}.sql"

    console.print(f"[cyan]Exportando[/cyan] [green]{database}[/green] [cyan]...[/cyan]")
    try:
        export_database(database, dest, data_only=data_only)
    except DbError as exc:
        console.print(Panel(f"[red]Falló la exportacion[/red]\n{exc}", title="[red]Error[/red]", border_style="red"))
        raise typer.Exit(1)

    size = dest.stat().st_size
    console.print(Panel(f"[green]Exportado {database} -> {dest} ({human_size(size)})[/green]", border_style="green"))


@app.command("reset")
def reset_db(
    sql: Path = typer.Argument(..., help="Archivo .sql a importar", autocompletion=complete_path),
    db: str = typer.Option(DEFAULT_DB, "--db", "-d", help="Nombre de la base de datos", autocompletion=complete_databases),
    yes: bool = typer.Option(False, "--yes", "-y", help="No pedir confirmacion"),
    help: bool = typer.Option(False, "??", help="Mostrar ayuda"),
):
    if help:
        console.print(Panel(HELP_TEXT, title="db", border_style=COLOR_ACCENT, expand=False))
        raise typer.Exit()

    if not sql.exists():
        console.print(Panel(f"[red]Archivo no encontrado:[/red]\n  {sql}", title="[red]Error[/red]", border_style="red"))
        raise typer.Exit(1)

    if not yes:
        if not Confirm.ask(
            f"[bold red]Borrar la ESTRUCTURA de {db} e importar [green]{sql.name}[/green]?[/bold red]",
            default=False,
        ):
            console.print("[yellow]Cancelado[/yellow]")
            raise typer.Exit()

    dropped = drop_all(db)
    console.print(f"[cyan]Eliminados {dropped} objeto(s). Recreando base {db}...[/cyan]")
    ensure_database(db)
    console.print(f"[cyan]Importando[/cyan] [green]{sql}[/green] [cyan]...[/cyan]")
    try:
        import_database(sql, db)
    except DbError as exc:
        console.print(Panel(f"[red]Falló la importacion[/red]\n{exc}", title="[red]Error[/red]", border_style="red"))
        raise typer.Exit(1)
    console.print(Panel(f"[green]Reset completado: {db} lista desde {sql.name}.[/green]", border_style="green"))


def interactive_flow() -> None:
    dbs = user_databases()
    if not dbs:
        console.print("[yellow]No hay bases de datos disponibles.[/yellow]")
        raise typer.Exit()

    table = Table(show_header=True, header_style=f"bold {COLOR_ACCENT}", box=None)
    table.add_column("#", style="dim", justify="right")
    table.add_column("Base de datos", style="green")
    for i, name in enumerate(dbs, 1):
        table.add_row(str(i), name)
    console.print(Panel(table, title="¿Que base de datos?", border_style=COLOR_ACCENT, expand=False))

    default_db = DEFAULT_DB if DEFAULT_DB in dbs else dbs[0]
    db = Prompt.ask("[bold]Base de datos[/bold]", choices=dbs, default=default_db)

    accion = Prompt.ask("[bold]¿Importar o exportar?[/bold]", choices=["importar", "exportar"], default="importar")

    if accion == "exportar":
        modo = Prompt.ask("[bold]¿Exportacion completa o solo datos?[/bold]", choices=["completa", "datos"], default="completa")
        default_name = f"{db}_{'completa' if modo == 'completa' else 'datos'}.sql"
        raw = Prompt.ask("[bold]Ruta donde guardar el .sql[/bold]", default=str(Path.cwd() / default_name))
        dest = Path(raw.strip().strip('"').strip("'"))
        console.print(f"[cyan]Exportando[/cyan] [green]{db}[/green] [cyan]...[/cyan]")
        try:
            export_database(db, dest, data_only=(modo == "datos"))
        except DbError as exc:
            console.print(Panel(f"[red]Falló la exportacion[/red]\n{exc}", title="[red]Error[/red]", border_style="red"))
            raise typer.Exit(1)
        console.print(Panel(f"[green]Exportado {db} -> {dest} ({human_size(dest.stat().st_size)})[/green]", border_style="green"))
        return

    do_truncate = Confirm.ask(
        "[bold]¿Borrar los datos de las tablas (droptable) antes de importar?[/bold]",
        default=True,
    )
    raw = Prompt.ask("[bold]Ruta del archivo .sql a importar[/bold]")
    sql_path = Path(raw.strip().strip('"').strip("'"))
    if not sql_path.exists():
        console.print(Panel(f"[red]Archivo no encontrado:[/red]\n  {sql_path}", title="[red]Error[/red]", border_style="red"))
        raise typer.Exit(1)

    resumen_accion = "vaciando datos e importando" if do_truncate else "importando"
    if not Confirm.ask(f"[bold]{resumen_accion.capitalize()} en [green]{db}[/green]?[/bold]", default=True):
        console.print("[yellow]Cancelado[/yellow]")
        raise typer.Exit()

    summary = perform_import(db, sql_path, do_truncate=do_truncate)
    print_summary(summary)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    help: bool = typer.Option(False, "??", help="Mostrar ayuda"),
):
    if help:
        console.print(Panel(HELP_TEXT, title="db", border_style=COLOR_ACCENT, expand=False))
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        interactive_flow()

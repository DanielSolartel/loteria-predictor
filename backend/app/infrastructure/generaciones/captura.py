"""Captura coherente y sellado de una generacion (E10.4; D10 pendiente para datos reales).

METODO `observacion-doble-e104/1`. Cada intento, SIN pausar Fase 6 ni tomar cerrojos ajenos:

  t0  evidencia viva de escritores (`escritores`): cerrojos de juego y de ejecucion tomados, ejecuciones
      `en_curso`, advisory en la base y transacciones que ya escribieron sin terminar. Si hay: intento rechazado.
  t1  fotografia de TODOS los arboles observados (publicables y operativos) con inodo, tamano, mtime y ctime.
  t2  instantanea: transaccion `REPEATABLE READ READ ONLY` y `pg_export_snapshot()`. En ella se leen el
      catalogo, la huella del esquema, la revision de Alembic, el ultimo sorteo por juego y el volcado logico
      con la huella de contenido y la de versiones de fila (`xmin`) de cada tabla.
  t3  copia verificada de los archivos publicables fotografiados en t1 y coherencia cruzada contra la MISMA
      instantanea (otra conexion la importa con `SET TRANSACTION SNAPSHOT`) con los lectores de la aplicacion.
  t4  observacion final INDEPENDIENTE: transaccion NUEVA con su propia instantanea (huellas de versiones de
      todas las tablas), fotografia nueva y evidencia viva otra vez.

Se sella solo si la fotografia t4 es identica a la de t1, las versiones de fila de todas las tablas en t4 son
las de la instantanea t2, no hubo evidencia viva en t0 ni en t4 y la coherencia no tiene rechazos. Entonces:
- ningun archivo observado cambio en [t1, t4] y ninguna transaccion confirmo cambios en ninguna tabla entre
  t2 y t4 (ni una iniciada antes de t2: sus versiones aparecen en t4 con otro `xmin`, C1; ni una que no altera
  recuentos ni maximos, C2; la observacion t4 es otra transaccion, C3);
- por tanto la base de la instantanea t2 y los archivos copiados son el estado de un MISMO instante (t2), y
  se mantuvieron identicos durante toda la ventana: esa es la definicion de corte conjunto de E10.4;
- la evidencia viva cubre a los escritores en mitad de una operacion de varios pasos que esten quietos
  durante la ventana (C4), y la coherencia cruzada a un artefacto escrito antes que su base (C8).
Lo que NO cubre (declarado): un proceso externo sin cerrojo que deje un estado intermedio fuera de la base y
de los arboles observados; SQL que cambie el reloj o escriba como superusuario en el mismo nanosegundo; en
Windows, la deteccion de archivos depende de `mtime` (ver `archivos`), pendiente de validacion nativa.

FALLO SEGURO (C6): la preparacion `.preparando-<aleatorio>` no tiene manifiesto hasta el final y solo se
renombra a `<id>` al terminar; cualquier error la borra (es propia), cierra las conexiones (la instantanea
exportada termina con su transaccion) y suelta el cerrojo PROPIO de captura (del sistema operativo, liberado
tambien si el proceso muere). Nunca se toma, pausa ni modifica nada de Fase 6. Tras agotar los intentos (con
un plazo total acotado) se escribe la alerta `captura_rechazada` y no hay generacion nueva.
"""
from __future__ import annotations

import datetime as dt
import os
import secrets
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from app.infrastructure.generaciones import archivos as ar
from app.infrastructure.generaciones import base_logica as bl
from app.infrastructure.generaciones import coherencia as co
from app.infrastructure.generaciones import escritores
from app.infrastructure.generaciones import firma
from app.infrastructure.generaciones import inventario as inv
from app.infrastructure.generaciones.formato import (
    COHERENCIA, FIRMA, FORMATO, MANIFIESTO, GeneracionNoValida, canonico, escribir_exclusivo, sha256_archivo,
    sha256_bytes, sincronizar_carpeta,
)

METODO = "observacion-doble-e104/1"
BACKEND = Path(__file__).resolve().parents[3]


class CapturaRechazada(RuntimeError):
    def __init__(self, motivos: list[dict]):
        super().__init__("captura rechazada: " + "; ".join(m["motivo"] for m in motivos[-1:]))
        self.motivos = motivos


class _Intento(Exception):
    def __init__(self, motivo: str, detalle, reintentable: bool = True):
        super().__init__(motivo)
        self.motivo, self.detalle, self.reintentable = motivo, detalle, reintentable


class Plazo:
    """Presupuesto TOTAL de la captura (E104-PLA-04): limita cada fase, cada conexion y sentencia
    (`connect_timeout`, `statement_timeout`, `lock_timeout`), cada bloque de copia y el sellado. Vencido, nada
    se sella: el intento se aborta y su preparacion se borra."""

    def __init__(self, segundos: float, reloj=time.monotonic):
        self.reloj, self.fin = reloj, reloj() + segundos

    def restante(self) -> float:
        return self.fin - self.reloj()

    def comprobar(self, donde: str) -> None:
        if self.restante() <= 0:
            raise _Intento("plazo_total_agotado", donde, reintentable=False)


@dataclass
class Fuente:
    url: str
    almacenes: dict[str, Path]
    secretos: list[Path] = field(default_factory=list)

    @classmethod
    def desde_ajustes(cls, ajustes, url: str | None = None) -> "Fuente":
        base = Path.cwd()
        almacenes = {a.nombre: (base / getattr(ajustes, a.ajuste)).resolve() for a in inv.ALMACENES}
        secretos = [(base / getattr(ajustes, s)).resolve() for s in inv.SECRETOS]
        return cls(url or ajustes.database_url, almacenes, secretos)


def ahora() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds")


def huella_del_codigo() -> dict:
    """Huella de las fuentes que definen esquema y contratos (`app/` y `alembic/`), commit y revision de Alembic
    del codigo que captura o importa."""
    filas = []
    for carpeta in ("app", "alembic"):
        for ruta in sorted((BACKEND / carpeta).rglob("*")):
            if ruta.is_file() and "__pycache__" not in ruta.parts and ruta.suffix in (".py", ".mako", ".sql"):
                filas.append([ruta.relative_to(BACKEND).as_posix(), sha256_archivo(ruta)[1]])
    commit = None
    try:
        r = subprocess.run(["git", "-C", str(BACKEND), "rev-parse", "HEAD"], capture_output=True, text=True,
                           timeout=10)
        commit = r.stdout.strip() if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        pass
    from app.infrastructure.generaciones import codigo

    huella_app, archivos_app = codigo.huella_app(BACKEND / "app")
    return {"huella_fuentes": sha256_bytes(canonico(filas)), "archivos": len(filas), "commit": commit,
            "revision_alembic": cabeza_alembic(), "huella_app": huella_app, "archivos_app": archivos_app,
            "revision_esquema_del_codigo": codigo.REVISION_ESQUEMA}


def cabeza_alembic() -> str:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    return ScriptDirectory.from_config(config).get_current_head()


def id_de(manifiesto: dict) -> str:
    return sha256_bytes(canonico({k: v for k, v in manifiesto.items() if k != "id"}))[:32]


class _Cerrojo:
    """Cerrojo PROPIO de captura en el destino (del sistema operativo; se libera si el proceso muere)."""

    def __init__(self, ruta: Path):
        self.ruta = ruta

    def __enter__(self):
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.descriptor = os.open(self.ruta, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            os.close(self.descriptor)
            raise CapturaRechazada([{"motivo": "otra_captura_en_curso", "detalle": str(self.ruta.name)}]) from error
        return self

    def __exit__(self, *_):
        os.close(self.descriptor)


def _historico_de_la_instantanea(url: str, snapshot: str, limite: float | None = None):
    """Sesion SQLAlchemy que IMPORTA la instantanea exportada: los repositorios de la aplicacion leen
    exactamente la base de t2."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import NullPool

    from app.application.use_cases.laboratorio import Lectura, leer_historico
    from app.infrastructure.repositories.juego_repository_sqlalchemy import JuegoRepositorySQLAlchemy
    from app.infrastructure.repositories.resultados_historicos_repository_sqlalchemy import (
        ResultadosHistoricosRepositorySQLAlchemy,
    )

    argumentos = {}
    if limite is not None:
        argumentos = {"connect_timeout": max(1, int(limite)),
                      "options": f"-c statement_timeout={max(1, int(limite * 1000))}"}
    motor = create_engine(url if "+psycopg" in url else url.replace("postgresql://", "postgresql+psycopg://", 1),
                          poolclass=NullPool, connect_args=argumentos)
    conexion = motor.connect().execution_options(isolation_level="REPEATABLE READ")
    conexion.exec_driver_sql(f"SET TRANSACTION SNAPSHOT '{snapshot}'")
    conexion.exec_driver_sql("SET TRANSACTION READ ONLY")
    sesion = Session(bind=conexion)
    lectura = Lectura(JuegoRepositorySQLAlchemy(sesion), ResultadosHistoricosRepositorySQLAlchemy(sesion))

    def historico(juego):
        try:
            return list(leer_historico(lectura, juego))
        except Exception as error:  # juego ausente de la base
            if type(error).__name__ == "JuegoNoEncontradoError":
                return None
            raise

    def cerrar():
        sesion.close()
        conexion.rollback()
        conexion.close()
        motor.dispose()

    return historico, cerrar


def _validar_raices(fuente: Fuente, foto: dict, alcance: str) -> None:
    for secreto in fuente.secretos:
        for nombre, raiz in fuente.almacenes.items():
            if secreto == raiz or raiz in secreto.parents or secreto in raiz.parents:
                raise _Intento("almacen_y_secretos_solapados", nombre, reintentable=False)
    problemas = []
    for clave, entrada in foto.items():
        almacen, relativa = clave.split("/", 1)
        if entrada[0] in ("enlace", "otro"):
            problemas.append(f"{clave}: {entrada[0]} no admitido")
        elif relativa and inv.clase(almacen, relativa) == "no_clasificado":
            problemas.append(f"{clave}: ruta no clasificada en la matriz de datos (DAT-01)")
    if problemas:
        raise _Intento("arbol_no_admitido", problemas[:20], reintentable=False)


def _a_copiar(foto: dict, alcance: str) -> list[str]:
    clases = {inv.PUBLICABLE} if alcance == "publicacion" else {inv.PUBLICABLE, inv.INTERNO, inv.OPERATIVO}
    salida = []
    for clave, entrada in sorted(foto.items()):
        almacen, relativa = clave.split("/", 1)
        if entrada[0] != "archivo" or not relativa:
            continue
        nombre = relativa.rsplit("/", 1)[-1]
        if ar.es_temporal(nombre) or inv.clase(almacen, relativa) not in clases:
            continue
        salida.append(clave)
    return salida


def _intento(fuente: Fuente, prep: Path, alcance: str, fase_externa: Callable[[str], None],
             plazo: Plazo | None = None) -> dict:
    plazo = plazo or Plazo(float("inf"))

    def fase(nombre: str) -> None:
        plazo.comprobar(nombre)
        fase_externa(nombre)
        plazo.comprobar(nombre)

    def limite() -> float | None:
        return None if plazo.restante() == float("inf") else plazo.restante()

    instantes = {"t0": ahora()}
    fase("t0")
    with bl.conectar(fuente.url, autocommit=True, limite=limite()) as obs:
        if not escritores.visibilidad_suficiente(obs):
            raise _Intento("rol_sin_visibilidad_de_sesiones", "el rol de captura necesita pg_read_all_stats",
                           reintentable=False)
        vivos = escritores.en_archivos(fuente.almacenes) + escritores.en_base(obs)
    if vivos:
        raise _Intento("escritores_activos_en_t0", vivos)
    instantes["t1"] = ahora()
    foto = ar.fotografiar(fuente.almacenes)
    _validar_raices(fuente, foto, alcance)
    fase("t1")
    import psycopg

    snap = bl.conectar(fuente.url, limite=limite())
    cerrar_historico = None
    try:
        snap.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        snap.read_only = True
        snapshot = snap.execute("SELECT pg_export_snapshot()").fetchone()[0]
        instantes["t2"] = ahora()
        catalogo = bl.tablas(snap)
        esquema = {"revision_alembic": bl.revision_alembic(snap), "huella": bl.huella_esquema(snap)}
        juegos = bl.ultimos_sorteos(snap)
        fase("instantanea")
        huellas_t2 = bl.volcar(snap, prep / "base", catalogo)
        fase("volcado")
        copiados = {}
        for clave in _a_copiar(foto, alcance):
            almacen, relativa = clave.split("/", 1)
            origen = fuente.almacenes[almacen] / relativa
            if inv.clase(almacen, relativa) == inv.PUBLICABLE and relativa.endswith((".secuencia", ".version")) \
                    and ar.reserva_huerfana(origen):
                continue  # transitorio (v2, 2.5)
            tam, sha = ar.copiar_verificado(origen, prep / "archivos" / almacen / relativa, comprobar=plazo.comprobar)
            if tam != foto[clave][3]:
                raise _Intento("archivo_cambio_durante_la_copia", clave)
            copiados[f"archivos/{almacen}/{relativa}"] = {"bytes": tam, "sha256": sha}
        for a in inv.PUBLICABLES:
            (prep / "archivos" / a.nombre).mkdir(parents=True, exist_ok=True)
        fase("copia")
        historico, cerrar_historico = _historico_de_la_instantanea(fuente.url, snapshot, limite())
        informe = co.evaluar(prep / "archivos", historico, juegos_de_la_base=juegos)
        fase("coherencia")
    finally:
        if cerrar_historico is not None:
            cerrar_historico()
        snap.rollback()
        snap.close()
    # t4: observacion INDEPENDIENTE (transaccion y conexion nuevas, instantanea propia)
    instantes["t4"] = ahora()
    plazo.comprobar("t4")
    with bl.conectar(fuente.url, limite=limite()) as fin:
        fin.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        fin.read_only = True
        huellas_t4 = bl.huellas(fin, bl.tablas(fin))
        fin.rollback()
    foto_t4 = ar.fotografiar(fuente.almacenes)
    with bl.conectar(fuente.url, autocommit=True, limite=limite()) as obs:
        vivos = escritores.en_archivos(fuente.almacenes) + escritores.en_base(obs)
    fase("t4")
    versiones_t2 = {n: h.versiones for n, h in huellas_t2.items()}
    versiones_t4 = {n: h.versiones for n, h in huellas_t4.items()}
    cambios_base = sorted(n for n in set(versiones_t2) | set(versiones_t4) if versiones_t2.get(n) != versiones_t4.get(n))
    if cambios_base:
        raise _Intento("base_cambio_durante_la_captura", cambios_base)
    if foto_t4 != foto:
        raise _Intento("archivos_cambiaron_durante_la_captura", ar.diferencias(foto, foto_t4))
    if vivos:
        raise _Intento("escritores_activos_en_t4", vivos)
    if informe["rechazos"]:
        raise _Intento("coherencia_cruzada", informe["rechazos"][:50], reintentable=False)
    return {"instantes": instantes, "catalogo": catalogo, "esquema": esquema, "juegos": juegos,
            "huellas": huellas_t2, "copiados": copiados, "coherencia": informe}


def capturar(fuente: Fuente, destino: Path, clave_privada: Path, *, alcance: str = "publicacion",
             intentos: int = 3, espera: float = 30.0, plazo: float = 900.0, autorizacion: str = "sintetico",
             fase: Callable[[str], None] = lambda _: None, reloj=time.monotonic, dormir=time.sleep) -> Path:
    """Devuelve la carpeta sellada `<destino>/<id>`; si no, lanza `CapturaRechazada` con los motivos de cada
    intento y deja la alerta en `<destino>/alertas/`."""
    if alcance not in ("publicacion", "respaldo"):
        raise ValueError("alcance: publicacion o respaldo")
    if intentos < 1 or espera < 0 or plazo <= 0:
        raise ValueError("intentos >= 1, espera >= 0 y plazo > 0")
    clave = firma.cargar_privada(clave_privada)
    destino.mkdir(parents=True, exist_ok=True)
    motivos, presupuesto = [], Plazo(plazo, reloj)
    with _Cerrojo(destino / ".captura.lock"):
        _descartar_restos(destino)
        for numero in range(1, intentos + 1):
            intento_id = secrets.token_hex(16)
            prep = ar.crear_propia(destino / f".preparando-{intento_id[:16]}", intento_id)
            try:
                presupuesto.comprobar("inicio del intento")
                datos = _intento(fuente, prep, alcance, fase, presupuesto)
                presupuesto.comprobar("antes de sellar")
                return _sellar(prep, destino, datos, clave, alcance, numero, autorizacion, presupuesto)
            except _Intento as fallo:
                motivos.append({"intento": numero, "motivo": fallo.motivo, "detalle": fallo.detalle})
                if not fallo.reintentable:
                    break
            except Exception as error:  # fallo intermedio (disco, conexion, ...): sin generacion
                vencido = presupuesto.restante() <= 0  # p. ej. statement_timeout o connect_timeout del plazo
                motivos.append({"intento": numero, "motivo": "plazo_total_agotado" if vencido else "fallo_intermedio",
                                "detalle": f"{type(error).__name__}: {str(error)[:300]}"})
                if vencido:
                    break
            finally:
                try:
                    if os.path.lexists(prep):
                        ar.borrar_propia(prep, destino, intento_id)
                    else:
                        ar.soltar_marca(prep)
                except (ar.NoPropia, OSError) as fallo:  # sustituida durante el intento: no se sigue ni se borra
                    motivos.append({"intento": numero, "motivo": "limpieza_sin_prueba_de_propiedad",
                                    "detalle": f"{type(fallo).__name__}: {str(fallo)[:300]}"})
            if numero < intentos:
                if presupuesto.restante() <= espera:
                    motivos.append({"intento": numero, "motivo": "plazo_total_agotado", "detalle": plazo})
                    break
                dormir(espera)
    alerta = destino / "alertas" / f"captura_rechazada-{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%S%fZ}.json"
    escribir_exclusivo(alerta, canonico({"alerta": "captura_rechazada", "metodo": METODO, "motivos": motivos,
                                         "fecha": ahora(), "generacion_nueva": None}))
    raise CapturaRechazada(motivos)


def _descartar_restos(destino: Path) -> None:
    """Preparaciones de una captura anterior terminada a la fuerza: se borran SOLO si se acreditan como propias
    (carpeta real, mismo usuario, dentro del destino y con su marca). Lo demas se deja intacto y se avisa en
    `alertas/` (E104-LIM-03). Se ejecuta bajo el cerrojo propio, que excluye otra captura en el mismo destino."""
    ajenos = []
    for resto in sorted(destino.glob(".preparando-*")):
        try:
            ar.borrar_propia(resto, destino)
        except (ar.NoPropia, OSError) as error:
            ajenos.append(f"{resto.name}: {error}")
    for marca in sorted(destino.glob("..preparando-*" + ar.MARCA)):
        carpeta = destino / marca.name[1:-len(ar.MARCA)]
        if not os.path.lexists(carpeta) and marca.is_file() and not marca.is_symlink():
            marca.unlink()  # marca de una preparacion ya borrada o sellada
    if ajenos:
        alerta = destino / "alertas" / f"restos_no_propios-{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%S%fZ}.json"
        escribir_exclusivo(alerta, canonico({"alerta": "restos_no_propios", "no_tocados": ajenos, "fecha": ahora()}))


def _sellar(prep: Path, destino: Path, datos: dict, clave, alcance: str, intento: int, autorizacion: str,
            plazo: Plazo | None = None) -> Path:
    plazo = plazo or Plazo(float("inf"))
    coherencia_bytes = canonico(datos["coherencia"])
    escribir_exclusivo(prep / COHERENCIA, coherencia_bytes)
    listado = dict(datos["copiados"])
    for nombre in sorted(datos["catalogo"]):
        tam, sha = sha256_archivo(prep / "base" / f"{nombre}.jsonl")
        listado[f"base/{nombre}.jsonl"] = {"bytes": tam, "sha256": sha}
    listado[COHERENCIA] = {"bytes": len(coherencia_bytes), "sha256": sha256_bytes(coherencia_bytes)}
    conteo = {}
    for ruta in datos["copiados"]:
        almacen = ruta.split("/")[1]
        conteo[almacen] = conteo.get(almacen, 0) + 1
    manifiesto = {
        "formato": FORMATO, "alcance": alcance, "creada_en": ahora(),
        "captura": {"metodo": METODO, "intento": intento, "instantes": datos["instantes"],
                    "autorizacion": autorizacion, "plataforma": sys.platform,
                    "deteccion_de_archivos": "posix_ctime" if os.name == "posix" else "mtime_pendiente_windows"},
        "codigo": huella_del_codigo(), "esquema": datos["esquema"],
        "base": {"tablas": {n: h.como_dict() for n, h in sorted(datos["huellas"].items())}},
        "juegos": datos["juegos"],
        "almacenes": {a.nombre: {"ajuste": a.ajuste, "clase": a.clase, "archivos": conteo.get(a.nombre, 0)}
                      for a in inv.ALMACENES if alcance == "respaldo" or a.clase == inv.PUBLICABLE},
        "archivos": dict(sorted(listado.items())),
        "coherencia": datos["coherencia"]["resumen"],
        "clave_firma": firma.id_de_privada(clave),
    }
    if manifiesto["esquema"]["revision_alembic"] != manifiesto["codigo"]["revision_alembic"]:
        raise GeneracionNoValida("la base no esta en la revision de Alembic del codigo que captura")
    manifiesto["id"] = id_de(manifiesto)
    datos_manifiesto = canonico(manifiesto)
    plazo.comprobar("sellado")
    escribir_exclusivo(prep / MANIFIESTO, datos_manifiesto)
    escribir_exclusivo(prep / FIRMA, (firma.firmar(clave, datos_manifiesto) + "\n").encode("ascii"))
    sincronizar_carpeta(prep)
    final = destino / manifiesto["id"]
    plazo.comprobar("sellado")  # ultimo punto: vencido, la preparacion se borra y no hay generacion
    os.rename(prep, final)
    ar.soltar_marca(prep)
    sincronizar_carpeta(destino)
    return final

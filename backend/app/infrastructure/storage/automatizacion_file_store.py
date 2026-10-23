"""Estado operativo de Fase 6, separado de modelos y artefactos emitidos.

Las lecturas nunca inicializan carpetas o cerrojos. Los cambios explícitos
usan publicación atómica y lectura cooperante Windows ya validadas; no
reescriben los temporales de otras ejecuciones. Las propuestas de corrección
y sus decisiones son entradas inmutables distintas del estado mutable.

Los cerrojos de este almacén coordinan procesos que comparten su directorio.
No sustituyen la coordinación de base de datos del adaptador operativo ni
demuestran exclusión entre equipos con directorios diferentes.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.infrastructure.storage import operacion_file_store as ofs

JUEGOS = ("BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO")
_CLAVE = re.compile(r"^[0-9a-f]{64}$")
_SECRETOS = frozenset({"database_url", "password", "passwd", "secret", "secreto",
                      "credential", "credentials", "api_key", "access_token"})
_POLITICA = {"intervalo_minutos": 15, "intervalo_fuera_ventana_minutos": 180,
             "reintento_inicial_segundos": 300, "reintento_maximo_segundos": 3600,
             "max_paginas": 3, "reconciliar_ultimos": 12, "max_reintentos": 8}


class AutomatizacionOcupadaError(RuntimeError):
    """Otro escritor conserva un recurso mutable; puede reintentarse."""


def _verificar_objeto(valor: dict) -> bytes:
    if not isinstance(valor, dict):
        raise ValueError("El registro operativo debe ser un objeto JSON.")

    def recorrer(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if not isinstance(k, str) or k.lower() in _SECRETOS:
                    raise ValueError("Clave no admitida en el registro operativo.")
                recorrer(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                recorrer(v)
    recorrer(valor)
    try:
        return (json.dumps(valor, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                           allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as error:
        raise ValueError("El registro debe contener JSON UTF-8 finito.") from error


def _codigo(codigo: str) -> str:
    if codigo not in JUEGOS:
        raise ValueError("Juego no admitido en la automatización.")
    return codigo


def _clave(clave: str) -> str:
    if not isinstance(clave, str) or not _CLAVE.fullmatch(clave):
        raise ValueError("La clave de revisión debe ser SHA-256 hexadecimal.")
    return clave


def _defecto() -> dict:
    return {"version": 1, "activada": False, "pausada": True,
            "juegos": list(JUEGOS), "politica": dict(_POLITICA)}


def _configuracion(configuracion: dict) -> dict:
    _verificar_objeto(configuracion)
    c = {**_defecto(), **configuracion}
    if type(c["version"]) is not int or c["version"] != 1:
        raise ValueError("Versión de configuración operativa no admitida.")
    if type(c["activada"]) is not bool or type(c["pausada"]) is not bool:
        raise ValueError("Activada y pausada deben ser booleanos explícitos.")
    if not isinstance(c["juegos"], list) or not c["juegos"]:
        raise ValueError("Debe seleccionar juegos para la operación.")
    if any(not isinstance(j, str) or j not in JUEGOS for j in c["juegos"]) or len(set(c["juegos"])) != len(c["juegos"]):
        raise ValueError("Juegos operativos ajenos o repetidos.")
    if any(k in c for k in ("modelo", "modelos", "registrado", "configuracion_modelos")):
        raise ValueError("La configuración operativa no elige ni modifica modelos.")
    if not isinstance(c["politica"], dict):
        raise ValueError("La política operativa debe ser un objeto.")
    c["politica"] = {**_POLITICA, **c["politica"]}
    for k in _POLITICA:
        v = c["politica"][k]
        if type(v) is not int or v <= 0:
            raise ValueError("Los límites operativos deben ser enteros positivos.")
    if c["politica"]["max_paginas"] > 10 or c["politica"]["reconciliar_ultimos"] > 100:
        raise ValueError("La reconciliación debe permanecer acotada.")
    if c["politica"]["reintento_maximo_segundos"] < c["politica"]["reintento_inicial_segundos"]:
        raise ValueError("El máximo de reintento es menor que la espera inicial.")
    return json.loads(_verificar_objeto(c))


class AlmacenAutomatizacion:
    def __init__(self, directorio: str | Path, *, espera=time.sleep, reloj=time.monotonic):
        self.directorio = Path(directorio)
        self._espera, self._reloj = espera, reloj
        self._registro = ofs.RegistroEjecucionesArchivo(self.directorio, espera=espera, reloj=reloj)
        self._cerrojo = ofs.CerrojoPorJuego(self.directorio / "ciclos")

    def _leer(self, ruta: Path) -> dict | None:
        def leer():
            with ofs._abrir_lectura_registro(ruta) as f:
                texto = f.read()
            def constante(_):
                raise ValueError("JSON no finito.")
            valor = json.loads(texto, parse_constant=constante)
            _verificar_objeto(valor)
            return valor
        try:
            valor, bloqueo = self._registro._reintentar(leer, ruta, ofs.LIMITE_DE_LECTURA)
        except FileNotFoundError:
            return None
        except (ValueError, UnicodeError) as error:
            raise ValueError(f"Registro operativo ilegible: {ruta.name}.") from error
        if bloqueo is not None:
            raise ofs.ReemplazoBloqueadoError("No se pudo leer el registro operativo bloqueado.") from bloqueo
        return valor

    @contextmanager
    def _recurso(self, nombre: str):
        # Nombre fijo o SHA completo derivado internamente, nunca entrada-ruta.
        carpeta = self.directorio / "l"
        carpeta.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(carpeta / (hashlib.sha256(nombre.encode()).hexdigest()[:16] + ".lock"),
                             os.O_RDWR | os.O_CREAT, 0o600)
        tomado = False
        try:
            inicio = self._reloj()
            pausa = 0.005
            while not tomado:
                tomado = ofs._bloquear(descriptor)
                if tomado:
                    break
                if self._reloj() - inicio + pausa > ofs.LIMITE_DE_LECTURA:
                    raise AutomatizacionOcupadaError("Otro proceso está actualizando el recurso operativo.")
                self._espera(pausa)
                pausa = min(pausa * 2, 0.1)
            yield
        finally:
            if tomado:
                ofs._soltar(descriptor)
            else:
                os.close(descriptor)

    def _publicar(self, ruta: Path, valor: dict) -> None:
        contenido = _verificar_objeto(valor)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = ruta.parent / (".a-" + secrets.token_hex(8) + ".tmp")
        try:
            with open(temporal, "xb") as f:
                f.write(contenido)
                f.flush()
                os.fsync(f.fileno())
            _, bloqueo = self._registro._reintentar(
                lambda: ofs._publicar_temporal(temporal, ruta), ruta, ofs.LIMITE_DE_REEMPLAZO)
            if bloqueo is not None:
                raise ofs.ReemplazoBloqueadoError("No se pudo publicar el registro operativo bloqueado.") from bloqueo
        except BaseException as error:
            # No ocultar el fallo original si también falla la limpieza.
            # Se conserva la ruta propia para diagnóstico, nunca se barre la
            # carpeta ni se promueve un temporal ajeno.
            try:
                if temporal.exists():
                    temporal.unlink()
            except OSError as limpieza:
                error.add_note(f"Temporal propio pendiente: {temporal}; limpieza: {type(limpieza).__name__}.")
                error.temporal_pendiente = str(temporal)
            raise

    def configuracion(self) -> dict:
        valor = self._leer(self.directorio / "configuracion.json")
        return _defecto() if valor is None else _configuracion(valor)

    def guardar_configuracion(self, configuracion: dict) -> dict:
        c = _configuracion(configuracion)
        with self._recurso("configuracion"):
            self._publicar(self.directorio / "configuracion.json", c)
        return c

    def actualizar_configuracion(self, cambios: dict) -> dict:
        _verificar_objeto(cambios)
        with self._recurso("configuracion"):
            previo = self.configuracion()
            combinado = {**previo, **cambios}
            if "politica" in cambios and isinstance(cambios["politica"], dict):
                combinado["politica"] = {**previo["politica"], **cambios["politica"]}
            c = _configuracion(combinado)
            self._publicar(self.directorio / "configuracion.json", c)
            return c

    def estado(self, codigo: str) -> dict:
        codigo = _codigo(codigo)
        return self._leer(self.directorio / "e" / (codigo + ".json")) or {"juego": codigo, "estado": "sin_comprobar"}

    def guardar_estado(self, codigo: str, estado: dict) -> dict:
        codigo = _codigo(codigo)
        _verificar_objeto(estado)
        if estado.get("juego", codigo) != codigo:
            raise ValueError("El estado pertenece a otro juego.")
        e = {**estado, "juego": codigo}
        with self._recurso("estado:" + codigo):
            self._publicar(self.directorio / "e" / (codigo + ".json"), e)
        return e

    def actualizar_estado(self, codigo: str, cambios: dict) -> dict:
        codigo = _codigo(codigo)
        _verificar_objeto(cambios)
        if cambios.get("juego", codigo) != codigo:
            raise ValueError("El estado pertenece a otro juego.")
        with self._recurso("estado:" + codigo):
            e = {**self.estado(codigo), **cambios, "juego": codigo}
            self._publicar(self.directorio / "e" / (codigo + ".json"), e)
            return e

    def guardar_ejecucion(self, ejecucion: dict) -> None:
        _verificar_objeto(ejecucion)
        if not isinstance(ejecucion.get("id"), str) or not ofs.identificador_valido(ejecucion["id"]):
            raise ValueError("Identificador operativo no válido.")
        with self._recurso("ejecucion:" + ejecucion["id"]):
            self._registro.guardar(ejecucion)

    def obtener_ejecucion(self, identificador: str) -> dict | None:
        if not isinstance(identificador, str):
            return None
        return self._registro.obtener(identificador)

    def actualizar_ejecucion_interrumpida(self, identificador: str, actualizar) -> dict | None:
        """Revalida y modifica solo un registro aún abierto sin trabajador.

        Comparte el recurso de guardar_ejecucion: una recuperación no puede
        publicar una proyección obsoleta encima de un cierre o de otra
        recuperación. Los identificadores de ejecución no se reutilizan y
        el trabajador conserva su lease hasta después de publicar el cierre.
        """
        if not isinstance(identificador, str) or not ofs.identificador_valido(identificador):
            raise ValueError("Identificador operativo no válido.")
        with self._recurso("ejecucion:" + identificador):
            actual = self.obtener_ejecucion(identificador)
            if not actual or actual.get("estado") != "en_curso" or self.viva(identificador):
                return None
            nuevo = actualizar(actual)
            _verificar_objeto(nuevo)
            if nuevo.get("id") != identificador or nuevo.get("estado") != "interrumpida":
                raise ValueError("La recuperación debe conservar la identidad y registrar su interrupción.")
            self._registro.guardar(nuevo)
            return nuevo

    def recientes(self, limite: int = 20) -> list[dict]:
        return self._registro.listar(max(1, min(int(limite), 200)))

    def revision(self, clave: str) -> dict | None:
        return self._leer(self.directorio / "r" / (_clave(clave) + ".json"))

    def guardar_revision(self, revision: dict) -> dict:
        _verificar_objeto(revision)
        clave = _clave(revision.get("clave"))
        _codigo(revision.get("juego"))
        if type(revision.get("numero_sorteo")) is not int or revision["numero_sorteo"] <= 0:
            raise ValueError("La revisión debe identificar un sorteo positivo.")
        if revision.get("estado") != "pendiente" or any(k not in revision for k in ("antes", "propuesta", "huellas")):
            raise ValueError("La propuesta debe conservar antes, propuesta y huellas, con estado pendiente.")
        with self._recurso("revision:" + clave):
            previo = self.revision(clave)
            if previo is not None:
                if _verificar_objeto(previo) != _verificar_objeto(revision):
                    raise ValueError("No se sobrescribe una revisión ya registrada.")
                return previo
            self._publicar(self.directorio / "r" / (clave + ".json"), revision)
        return json.loads(_verificar_objeto(revision))

    def guardar_decision_revision(self, clave: str, decision: dict) -> dict:
        clave = _clave(clave)
        _verificar_objeto(decision)
        if self.revision(clave) is None:
            raise ValueError("No existe la revisión para esa decisión.")
        contenido = {"revision": clave, "decision": decision}
        identidad = hashlib.sha256(_verificar_objeto(contenido)).hexdigest()
        ruta = self.directorio / "d" / (identidad + ".json")
        with self._recurso("decision:" + identidad):
            previo = self._leer(ruta)
            if previo is not None:
                if _verificar_objeto(previo) != _verificar_objeto(contenido):
                    raise ValueError("No se sobrescribe una decisión ya registrada.")
            else:
                self._publicar(ruta, contenido)
        return {"clave": identidad, **contenido}

    def _listar(self, carpeta: str, limite: int) -> list[dict]:
        p = self.directorio / carpeta
        if not p.is_dir():
            return []
        rutas = [q for q in p.glob("*.json") if _CLAVE.fullmatch(q.stem)]
        rutas.sort(key=lambda q: (q.stat().st_mtime_ns, q.name), reverse=True)
        return [valor for q in rutas[:max(1, min(int(limite), 1000))] if (valor := self._leer(q)) is not None]

    def revisiones(self, limite: int = 100) -> list[dict]:
        return self._listar("r", limite)

    def revisiones_pendientes(self, codigo: str, primer_sorteo: int | None,
                             ultimo_sorteo: int | None) -> list[dict]:
        """Todas las propuestas sin resolver que afectan al histórico usado.

        Esta consulta operativa no hereda el límite de presentación ni el
        presupuesto del proveedor. Los números fuera del intervalo y los
        demás juegos pertenecen a otro histórico; las propuestas se leen sin
        modificarlas. Un corte vacío no contiene resultados que corregir.
        """
        codigo = _codigo(codigo)
        if ultimo_sorteo is None:
            return []
        # Puertos históricos pueden omitir el primer número: no estrechar
        # silenciosamente su intervalo y olvidar una corrección anterior.
        primero = 1 if primer_sorteo is None else primer_sorteo
        if (type(primero) is not int or type(ultimo_sorteo) is not int
                or not 0 < primero <= ultimo_sorteo):
            raise ValueError("El intervalo de revisión debe identificar un histórico válido.")
        carpeta = self.directorio / "r"
        if not carpeta.is_dir():
            return []
        pendientes = []
        for ruta in sorted(carpeta.glob("*.json")):
            if not _CLAVE.fullmatch(ruta.stem):
                continue
            revision = self._leer(ruta)
            if revision is None:
                continue
            if revision.get("clave") != ruta.stem:
                raise ValueError("La revisión no coincide con su identidad persistida.")
            juego = _codigo(revision.get("juego"))
            numero = revision.get("numero_sorteo")
            if type(numero) is not int or numero <= 0 or revision.get("estado") != "pendiente":
                raise ValueError("La propuesta persistida no identifica una revisión pendiente válida.")
            if juego != codigo or not primero <= numero <= ultimo_sorteo:
                continue
            decisiones = self.decisiones_revision(revision["clave"], limite=1)
            ultima = decisiones[0].get("decision", {}) if decisiones and not decisiones[0].get("orden_ambiguo") else {}
            if ultima.get("estado") not in ("aceptada", "rechazada"):
                pendientes.append(revision)
        return pendientes

    def decisiones_revision(self, clave: str, limite: int = 100) -> list[dict]:
        """Proyección temporal compatible, sin modificar decisiones guardadas.

        Si todas las fechas declaradas incluyen zona, su instante UTC define
        el orden. Para registros históricos sin fecha comparable se usa el
        mtime del grupo completo, sin mezclar ambas cronologías. Un máximo
        compartido por contenidos distintos es ambiguo: el SHA solo ordena
        su presentación y no puede convertirlo en una decisión vigente.
        La ambigüedad se calcula antes del límite de presentación.
        """
        clave = _clave(clave)
        carpeta = self.directorio / "d"
        if not carpeta.is_dir():
            return []
        registros = []
        for ruta in carpeta.glob("*.json"):
            if not _CLAVE.fullmatch(ruta.stem):
                continue
            valor = self._leer(ruta)
            if valor is None or valor.get("revision") != clave:
                continue
            decision = valor.get("decision")
            if not isinstance(decision, dict):
                raise ValueError("La decisión persistida debe ser un objeto.")
            try:
                fecha = datetime.fromisoformat(decision.get("en"))
                if fecha.tzinfo is None or fecha.utcoffset() is None:
                    raise ValueError("La fecha no incluye zona.")
                fecha = fecha.astimezone(timezone.utc)
            except (TypeError, ValueError, OverflowError):
                fecha = None
            registros.append((ruta.name, ruta.stat().st_mtime_ns, fecha, valor))
        if not registros:
            return []
        con_fecha = all(r[2] is not None for r in registros)
        indice = 2 if con_fecha else 1
        registros.sort(key=lambda r: (r[indice], r[0]), reverse=True)
        maximo = registros[0][indice]
        primeras = [r for r in registros if r[indice] == maximo]
        ambiguo = len({_verificar_objeto(r[3]) for r in primeras}) > 1
        limite = max(1, min(int(limite), 1000))
        return [{**r[3], "orden_ambiguo": True}
                if ambiguo and r[indice] == maximo else r[3]
                for r in registros[:limite]]

    def adquirir(self, juegos, identificador: str):
        juegos = tuple(dict.fromkeys(juegos))
        if not juegos:
            raise ValueError("Debe indicar juegos para el ciclo.")
        for juego in juegos:
            _codigo(juego)
        return self._cerrojo.adquirir(juegos, identificador)

    def viva(self, identificador: str) -> bool:
        if not isinstance(identificador, str):
            return False
        return self._cerrojo.ejecucion_viva(identificador)

    def activa(self, codigo: str) -> str | None:
        return self._cerrojo.activa(_codigo(codigo))

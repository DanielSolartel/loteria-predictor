"""AE-48, validada: evidencia y comparacion de la consulta manual.

Modulo auxiliar de `scripts/consultar_estado_prediccion.py`, solo con
biblioteca estandar:

- `validar_reporte_estado`: validacion estricta de un reporte JSON 1.1
  o 1.2 (el archivo anterior de `--comparar`). Rechaza cualquier clave
  inesperada, estados o condiciones fuera del catalogo, incoherencias
  de progreso, `desbloqueable` distinto de `false` y claves predictivas
  en cualquier nivel.
- `comparar_reportes`: comparacion DESCRIPTIVA de metadatos agregados
  entre dos ejecuciones. No evalua modelos ni convierte los sorteos
  desde 2706 en holdout; una variacion de sorteos no es evidencia
  predictiva ni modifica el NO-GO de AE-39. La `comparacion` de un
  archivo anterior 1.2 se valida, pero nunca se reutiliza ni se copia.
- `escribir_evidencia_atomica`: escribe los bytes exactos en un
  temporal (binario, `fsync`) y lo publica con un enlace duro, que
  falla si el destino ya existe: nunca sobrescribe. Si el sistema de
  archivos no admite enlaces duros, falla sin publicar.

El catalogo de estados y condiciones lo inyecta el script desde los
enums reales, para no duplicarlos aqui."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass

ESQUEMAS_ACEPTADOS = ("1.1", "1.2")
JUEGOS_ESPERADOS = ("BALOTO", "BALOTO_REVANCHA")
NOTA_COMPARACION = (
    "Comparacion descriptiva de metadatos agregados: no es evidencia predictiva "
    "ni modifica el NO-GO de AE-39."
)
CLAVES_PREDICTIVAS = frozenset({
    "combinaciones", "numeros_fuertes", "numeros_debiles", "probabilidades", "nivel_confianza",
})
CLAVES_RAIZ_1_1 = frozenset({"esquema", "alembic_revision", "juegos"})
CLAVES_JUEGO = frozenset({
    "codigo", "estado", "motivos", "explicacion", "disclaimer",
    "progreso", "condiciones_pendientes", "desbloqueable",
})
CLAVES_PROGRESO = frozenset({
    "evaluable", "desde_numero_sorteo", "total_sorteos_nuevos",
    "minimo_requerido", "faltantes", "numero_sorteo_objetivo_minimo",
})
CLAVES_COMPARACION = frozenset({"esquema_anterior", "revision_alembic_anterior", "misma_revision_alembic", "juegos", "nota"})
CLAVES_COMPARACION_JUEGO = frozenset({
    "codigo", "sorteos_nuevos_anterior", "sorteos_nuevos_actual", "variacion_sorteos_nuevos",
    "faltantes_anterior", "faltantes_actual", "estado_anterior", "estado_actual", "estado_cambio",
    "condiciones_resueltas", "condiciones_nuevas", "retroceso",
})


class ReporteAnteriorInvalidoError(ValueError):
    """El archivo anterior no es un reporte 1.1/1.2 valido."""


class RutaSalidaNoPermitidaError(ValueError):
    """La ruta de `--salida` coincide con `--comparar`, ya existe o su
    directorio no existe."""


class EscrituraEvidenciaError(Exception):
    """No se pudo publicar la evidencia sin sobrescribir."""


@dataclass(frozen=True)
class CatalogoEstados:
    """Valores de `EstadoPrediccionML` y `CondicionDesbloqueoML`, en su
    orden de declaracion, inyectados por el script."""
    estados: tuple[str, ...]
    condiciones: tuple[str, ...]
    condiciones_sin_mecanismo: frozenset[str]
    condicion_numeracion: str
    condicion_minimo: str
    condicion_evidencia: str
    estado_no_go: str


def _invalido(mensaje: str) -> ReporteAnteriorInvalidoError:
    return ReporteAnteriorInvalidoError(mensaje)


def _es_entero(valor) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


def _claves_exactas(objeto, esperadas: frozenset, donde: str) -> None:
    if not isinstance(objeto, dict):
        raise _invalido(f"{donde} debe ser un objeto JSON")
    if set(objeto) != esperadas:
        raise _invalido(f"{donde}: claves {sorted(objeto)}, se esperaban {sorted(esperadas)}")


def _sin_claves_predictivas(objeto, donde: str = "reporte") -> None:
    if isinstance(objeto, dict):
        for clave, valor in objeto.items():
            if clave in CLAVES_PREDICTIVAS:
                raise _invalido(f"{donde} contiene la clave predictiva '{clave}'")
            _sin_claves_predictivas(valor, f"{donde}.{clave}")
    elif isinstance(objeto, list):
        for indice, valor in enumerate(objeto):
            _sin_claves_predictivas(valor, f"{donde}[{indice}]")


def _subsecuencia_ordenada(valores, orden: tuple[str, ...], donde: str, vacia_permitida: bool) -> None:
    if not isinstance(valores, list) or not all(isinstance(v, str) for v in valores):
        raise _invalido(f"{donde} debe ser una lista de textos")
    if not valores and not vacia_permitida:
        raise _invalido(f"{donde} no puede estar vacia")
    if any(v not in orden for v in valores):
        raise _invalido(f"{donde} contiene valores fuera del catalogo: {valores}")
    if valores != sorted(set(valores), key=orden.index):
        raise _invalido(f"{donde} debe estar en orden de catalogo y sin duplicados")


def _validar_progreso(progreso, donde: str) -> None:
    _claves_exactas(progreso, CLAVES_PROGRESO, donde)
    if not isinstance(progreso["evaluable"], bool) or not _es_entero(progreso["desde_numero_sorteo"]):
        raise _invalido(f"{donde}: 'evaluable' debe ser bool y 'desde_numero_sorteo' entero")
    cifras = [progreso[c] for c in ("total_sorteos_nuevos", "minimo_requerido", "faltantes", "numero_sorteo_objetivo_minimo")]
    if not progreso["evaluable"]:
        if any(c is not None for c in cifras):
            raise _invalido(f"{donde}: un progreso no evaluable no lleva cifras")
        return
    if not all(_es_entero(c) for c in cifras):
        raise _invalido(f"{donde}: un progreso evaluable exige cifras enteras")
    total, minimo, faltantes, _ = cifras
    if total < 0 or minimo <= 0 or faltantes != max(0, minimo - total):
        raise _invalido(f"{donde}: progreso incoherente (total={total}, minimo={minimo}, faltantes={faltantes})")


def _validar_juego(juego, codigo: str, catalogo: CatalogoEstados) -> None:
    donde = f"juego {codigo}"
    _claves_exactas(juego, CLAVES_JUEGO, donde)
    if juego["codigo"] != codigo:
        raise _invalido(f"{donde}: codigo '{juego['codigo']}' fuera de orden o desconocido")
    for campo in ("explicacion", "disclaimer"):
        if not isinstance(juego[campo], str) or not juego[campo].strip():
            raise _invalido(f"{donde}: '{campo}' debe ser un texto no vacio")
    _subsecuencia_ordenada(juego["motivos"], catalogo.estados, f"{donde}.motivos", vacia_permitida=False)
    if juego["estado"] != juego["motivos"][0]:
        raise _invalido(f"{donde}: 'estado' debe ser el primer motivo")
    if juego["desbloqueable"] is not False:
        raise _invalido(f"{donde}: 'desbloqueable' debe ser false")
    _validar_progreso(juego["progreso"], f"{donde}.progreso")
    pendientes = juego["condiciones_pendientes"]
    _subsecuencia_ordenada(pendientes, catalogo.condiciones, f"{donde}.condiciones_pendientes", vacia_permitida=False)
    progreso = juego["progreso"]
    esperadas_pendientes = {
        catalogo.condicion_numeracion: not progreso["evaluable"],
        catalogo.condicion_minimo: not (progreso["evaluable"] and progreso["faltantes"] == 0),
        catalogo.condicion_evidencia: catalogo.estado_no_go in juego["motivos"],
        **{c: True for c in catalogo.condiciones_sin_mecanismo},
    }
    for condicion, debe_estar in esperadas_pendientes.items():
        if (condicion in pendientes) != debe_estar:
            raise _invalido(f"{donde}: condicion '{condicion}' incoherente con progreso o motivos")


def _validar_comparacion(
    comparacion, revision_alembic: str, juegos_actuales: list, catalogo: CatalogoEstados,
) -> None:
    _claves_exactas(comparacion, CLAVES_COMPARACION, "comparacion")
    if comparacion["esquema_anterior"] not in ESQUEMAS_ACEPTADOS:
        raise _invalido("comparacion.esquema_anterior desconocido")
    if not isinstance(comparacion["revision_alembic_anterior"], str) or not comparacion["revision_alembic_anterior"]:
        raise _invalido("comparacion.revision_alembic_anterior debe ser un texto no vacio")
    if not isinstance(comparacion["misma_revision_alembic"], bool):
        raise _invalido("comparacion.misma_revision_alembic debe ser bool")
    if comparacion["misma_revision_alembic"] is not (comparacion["revision_alembic_anterior"] == revision_alembic):
        raise _invalido(
            "comparacion.misma_revision_alembic no coincide con comparar revision_alembic_anterior "
            "con alembic_revision del propio reporte"
        )
    if comparacion["nota"] != NOTA_COMPARACION:
        raise _invalido("comparacion.nota distinta de la nota fija")
    if not isinstance(comparacion["juegos"], list) or len(comparacion["juegos"]) != len(JUEGOS_ESPERADOS):
        raise _invalido("comparacion.juegos debe tener exactamente dos juegos")
    for entrada, juego_actual, codigo in zip(comparacion["juegos"], juegos_actuales, JUEGOS_ESPERADOS):
        donde = f"comparacion.juegos[{codigo}]"
        _claves_exactas(entrada, CLAVES_COMPARACION_JUEGO, donde)
        if entrada["codigo"] != codigo:
            raise _invalido(f"{donde}: codigo fuera de orden")
        for campo in ("sorteos_nuevos_anterior", "sorteos_nuevos_actual", "faltantes_anterior", "faltantes_actual"):
            if entrada[campo] is not None and not _es_entero(entrada[campo]):
                raise _invalido(f"{donde}: '{campo}' debe ser entero o null")
        for campo in ("estado_anterior", "estado_actual"):
            if entrada[campo] not in catalogo.estados:
                raise _invalido(f"{donde}: '{campo}' fuera del catalogo")
        for campo in ("condiciones_resueltas", "condiciones_nuevas"):
            _subsecuencia_ordenada(entrada[campo], catalogo.condiciones, f"{donde}.{campo}", vacia_permitida=True)
        progreso = juego_actual["progreso"]
        if (entrada["sorteos_nuevos_actual"], entrada["faltantes_actual"], entrada["estado_actual"]) != (
            progreso["total_sorteos_nuevos"], progreso["faltantes"], juego_actual["estado"],
        ):
            raise _invalido(f"{donde}: los valores actuales no coinciden con el propio reporte")
        anterior, actual = entrada["sorteos_nuevos_anterior"], entrada["sorteos_nuevos_actual"]
        variacion = None if anterior is None or actual is None else actual - anterior
        if entrada["variacion_sorteos_nuevos"] != variacion or (
            variacion is not None and not _es_entero(entrada["variacion_sorteos_nuevos"])
        ):
            raise _invalido(f"{donde}: variacion incoherente")
        if entrada["retroceso"] is not (variacion is not None and variacion < 0):
            raise _invalido(f"{donde}: retroceso incoherente")
        if entrada["estado_cambio"] is not (entrada["estado_anterior"] != entrada["estado_actual"]):
            raise _invalido(f"{donde}: estado_cambio incoherente")


def validar_reporte_estado(reporte, catalogo: CatalogoEstados) -> dict:
    """Validacion estricta de un reporte 1.1 o 1.2. Devuelve el mismo
    objeto si es valido; si no, `ReporteAnteriorInvalidoError`."""
    if not isinstance(reporte, dict):
        raise _invalido("el reporte debe ser un objeto JSON")
    esquema = reporte.get("esquema") if "esquema" in reporte else None
    if esquema not in ESQUEMAS_ACEPTADOS:
        raise _invalido(f"esquema {esquema!r} no aceptado; solo {ESQUEMAS_ACEPTADOS}")
    esperadas = CLAVES_RAIZ_1_1 | ({"comparacion"} if esquema == "1.2" else set())
    _claves_exactas(reporte, frozenset(esperadas), "raiz")
    _sin_claves_predictivas(reporte)
    if not isinstance(reporte["alembic_revision"], str) or not reporte["alembic_revision"]:
        raise _invalido("alembic_revision debe ser un texto no vacio")
    juegos = reporte["juegos"]
    if not isinstance(juegos, list) or len(juegos) != len(JUEGOS_ESPERADOS):
        raise _invalido("juegos debe contener exactamente BALOTO y BALOTO_REVANCHA")
    for juego, codigo in zip(juegos, JUEGOS_ESPERADOS):
        _validar_juego(juego, codigo, catalogo)
    if esquema == "1.2":
        _validar_comparacion(reporte["comparacion"], reporte["alembic_revision"], juegos, catalogo)
    return reporte


def leer_reporte_anterior(ruta: str, catalogo: CatalogoEstados) -> dict:
    """Lee (UTF-8 estricto) y valida el archivo de `--comparar`."""
    try:
        with open(ruta, "rb") as archivo:
            datos = archivo.read()
        reporte = json.loads(datos.decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ReporteAnteriorInvalidoError(f"No se pudo leer el archivo anterior '{ruta}': {error}") from error
    return validar_reporte_estado(reporte, catalogo)


def comparar_reportes(anterior: dict, actual: dict, catalogo: CatalogoEstados) -> dict:
    """Comparacion descriptiva por juego. Solo usa `juegos` y
    `alembic_revision` de cada reporte; la `comparacion` de un anterior
    1.2 nunca se reutiliza."""
    juegos = []
    for juego_anterior, juego_actual in zip(anterior["juegos"], actual["juegos"]):
        progreso_anterior, progreso_actual = juego_anterior["progreso"], juego_actual["progreso"]
        total_anterior = progreso_anterior["total_sorteos_nuevos"]
        total_actual = progreso_actual["total_sorteos_nuevos"]
        variacion = None if total_anterior is None or total_actual is None else total_actual - total_anterior
        pendientes_anteriores = juego_anterior["condiciones_pendientes"]
        pendientes_actuales = juego_actual["condiciones_pendientes"]
        juegos.append({
            "codigo": juego_actual["codigo"],
            "sorteos_nuevos_anterior": total_anterior,
            "sorteos_nuevos_actual": total_actual,
            "variacion_sorteos_nuevos": variacion,
            "faltantes_anterior": progreso_anterior["faltantes"],
            "faltantes_actual": progreso_actual["faltantes"],
            "estado_anterior": juego_anterior["estado"],
            "estado_actual": juego_actual["estado"],
            "estado_cambio": juego_anterior["estado"] != juego_actual["estado"],
            "condiciones_resueltas": [c for c in pendientes_anteriores if c not in pendientes_actuales],
            "condiciones_nuevas": [c for c in pendientes_actuales if c not in pendientes_anteriores],
            "retroceso": variacion is not None and variacion < 0,
        })
    return {
        "esquema_anterior": anterior["esquema"],
        "revision_alembic_anterior": anterior["alembic_revision"],
        "misma_revision_alembic": anterior["alembic_revision"] == actual["alembic_revision"],
        "juegos": juegos,
        "nota": NOTA_COMPARACION,
    }


def serializar_reporte(reporte: dict) -> bytes:
    """Serializacion unica: el mismo texto que AE-47 imprime con
    `print(json.dumps(...))`, codificado en UTF-8 con LF."""
    return (json.dumps(reporte, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _ruta_normalizada(ruta: str) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(ruta)))


def validar_ruta_salida(salida: str, comparar: str | None) -> None:
    """Rechaza `--salida` igual a `--comparar` (rutas relativas, `..`,
    enlaces simbolicos y, si ambos existen, enlaces duros), ya existente
    o en un directorio inexistente."""
    if comparar is not None:
        misma = _ruta_normalizada(salida) == _ruta_normalizada(comparar)
        if not misma and os.path.exists(salida) and os.path.exists(comparar):
            misma = os.path.samefile(salida, comparar)
        if misma:
            raise RutaSalidaNoPermitidaError(
                f"--salida '{salida}' apunta al mismo archivo que --comparar '{comparar}'"
            )
    if os.path.lexists(salida):
        raise RutaSalidaNoPermitidaError(f"--salida '{salida}' ya existe; la evidencia nunca se sobrescribe")
    directorio = os.path.dirname(os.path.abspath(salida))
    if not os.path.isdir(directorio):
        raise RutaSalidaNoPermitidaError(f"El directorio de --salida '{directorio}' no existe")


def _publicar_exclusivo(temporal: str, destino: str) -> None:
    """Enlace duro: crea `destino` de forma atomica y falla con
    `FileExistsError` si ya existe (POSIX `link`, Windows
    `CreateHardLinkW`). Nunca sobrescribe."""
    os.link(temporal, destino)


def escribir_evidencia_atomica(contenido: bytes, ruta: str) -> str:
    """Escribe `contenido` en un temporal del mismo directorio (binario,
    `fsync`), lo publica con `_publicar_exclusivo`, elimina el temporal
    y verifica la huella releyendo el destino. Devuelve el SHA-256.
    Un fallo al releer tras publicar se informa como
    `EscrituraEvidenciaError`; el destino ya publicado no se borra."""
    destino = os.path.abspath(ruta)
    directorio = os.path.dirname(destino)
    huella = hashlib.sha256(contenido).hexdigest()
    try:
        fd, temporal = tempfile.mkstemp(dir=directorio, prefix=".evidencia-ae48-", suffix=".tmp")
    except OSError as error:
        raise EscrituraEvidenciaError(f"No se pudo crear el temporal en '{directorio}': {error}") from error
    try:
        try:
            with os.fdopen(fd, "wb") as archivo:
                archivo.write(contenido)
                archivo.flush()
                os.fsync(archivo.fileno())
        except OSError as error:
            raise EscrituraEvidenciaError(f"No se pudo escribir el temporal: {error}") from error
        try:
            _publicar_exclusivo(temporal, destino)
        except FileExistsError as error:
            raise EscrituraEvidenciaError(f"El destino '{ruta}' ya existe; no se sobrescribe") from error
        except (OSError, NotImplementedError) as error:
            raise EscrituraEvidenciaError(
                f"El sistema de archivos no permitio publicar '{ruta}' de forma exclusiva: {error}"
            ) from error
    finally:
        try:
            os.remove(temporal)
        except OSError:
            pass
    try:
        with open(destino, "rb") as archivo:
            releido = archivo.read()
    except OSError as error:
        raise EscrituraEvidenciaError(
            f"'{ruta}' se publico pero no se pudo releer para verificar su huella: {error}"
        ) from error
    if hashlib.sha256(releido).hexdigest() != huella:
        raise EscrituraEvidenciaError(f"La huella de '{ruta}' no coincide con los bytes escritos")
    return huella

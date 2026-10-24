"""Fase 7 -identidad, integridad y exportaciones de una simulacion.

La fila de la tabla `simulaciones` es la FUENTE CANONICA del resultado:

- `parametros` (JSONB): la IDENTIDAD completa -esquema, version del motor,
  juego, corte, historico (sorteos, huecos, transiciones y SHA-256),
  reglas y mecanismo, algoritmo (generador, derivacion de la semilla,
  consumo, seleccion, version de NumPy), semilla, iteraciones, estadisticas
  fijadas y familia- y `clave` = SHA-256 de la serializacion canonica
  (AE-52) de esa identidad sin `clave`.
- `resultado_resumen` (JSONB): `contenido` (resultado cientifico
  determinista: mismo contenido para la misma identidad, con cualquier
  tamano de lote) con su `contenido_sha256`; `ejecucion` (lote, lotes,
  duracion y entorno: metadatos que NO forman parte del resultado) e
  `integridad_sha256` de parametros + resultado.
- `num_iteraciones`, `juego_id`, `ejecutado_en` (hora de publicacion del
  servidor) y `duracion_ms` (calculo) aprovechan las columnas existentes.

Las exportaciones JSON y CSV se derivan de la fila verificada; el registro de
ejecuciones (progreso) solo la referencia y nunca es fuente del resultado.

Modulo puro."""
from __future__ import annotations

import copy
import csv
import io
import json

from app.application.fase7 import motor as fm
from app.application.ml import laboratorio_variables as lv
from app.application.ml.registro_prospectivo import EntradaRegistroInvalidaError, hash_entrada, serializar_entrada

ESQUEMA_IDENTIDAD = "fase7-simulacion-identidad/1"
ESQUEMA_RESULTADO = "fase7-simulacion-resultado/1"
ESQUEMA_EXPORTACION = "fase7-simulacion-exportacion/1"
ESTADO_DE_USO = "experimental_no_acreditado"


class ArtefactoSimulacionError(ValueError):
    """La fila no cumple el contrato de la Fase 7 o esta alterada."""


def sha256(valor) -> str:
    return hash_entrada(serializar_entrada(valor))


def identidad(h: fm.Historico, iteraciones: int, semilla: int) -> dict:
    iteraciones, semilla = fm.validar_parametros(iteraciones, semilla)
    return {"esquema": ESQUEMA_IDENTIDAD, "version_motor": fm.VERSION_MOTOR, "juego": h.juego,
            "corte": h.instantanea.corte, "historico": fm.descripcion_historico(h), "reglas": fm.reglas_y_mecanismo(h),
            "algoritmo": fm.algoritmo(), "iteraciones": iteraciones, "semilla": semilla,
            "estadisticas": fm.definicion_de_familia(h.juego),
            "familia": {"metodo": "bonferroni", "alpha": fm.ALPHA, "tamano": len(fm.familia(h.juego)),
                        "alcance": "comparaciones_de_este_juego_en_esta_ejecucion"},
            "estado_de_uso": ESTADO_DE_USO}


def parametros(identidad_: dict) -> dict:
    return {**identidad_, "clave": sha256(identidad_)}


def resultado(parametros_: dict, contenido: dict, ejecucion: dict) -> dict:
    cuerpo = {"esquema": ESQUEMA_RESULTADO, "clave": parametros_["clave"], "contenido": contenido,
              "contenido_sha256": sha256(contenido), "ejecucion": ejecucion}
    return {**cuerpo, "integridad_sha256": sha256({"parametros": parametros_, "resultado": cuerpo})}


def _es_entero(valor) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


def _es_numero(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def _es_texto(valor) -> bool:
    return isinstance(valor, str)


def _objeto(objeto, /, **campos) -> bool:
    """Objeto JSON cuyos `campos` cumplen su comprobacion de tipo."""
    return isinstance(objeto, dict) and all(comprobar(objeto.get(c)) for c, comprobar in campos.items())


def _estadistica_valida(e) -> bool:
    return _objeto(e, nombre=_es_texto, descripcion=_es_texto,
                   supera_umbral_exploratorio=lambda v: isinstance(v, bool),
                   observado=lambda v: _objeto(v, valor=_es_numero, exacto=_es_texto),
                   simulado=lambda v: _objeto(v, media=_es_numero, desviacion=_es_numero, media_exacta=_es_texto),
                   referencia_analitica=lambda v: v is None or _objeto(v, valor=_es_numero),
                   percentil_observado=lambda v: _objeto(v, valor=_es_numero),
                   p_valor_empirico=lambda v: _objeto(v, valor=_es_numero, exacto=_es_texto),
                   p_valor_ajustado_bonferroni=lambda v: _objeto(v, valor=_es_numero))


def _forma(parametros_: dict, resultado_resumen: dict) -> None:
    """Tipos de los campos que leen el listado, la ficha, las exportaciones y
    `verificar`, comprobados antes de usarlos: las huellas no son una firma y
    quien edita la fila puede recalcularlas."""
    if not _objeto(parametros_, juego=lambda v: v in lv.JUEGOS, corte=_es_entero, iteraciones=_es_entero,
                   semilla=_es_entero, version_motor=_es_texto,
                   historico=lambda v: _objeto(v, sha256=_es_texto),
                   algoritmo=lambda v: _objeto(v, numpy=_es_texto),
                   reglas=lambda v: _objeto(v, paleta=lambda x: x is None or isinstance(x, list))):
        raise ArtefactoSimulacionError("la identidad no tiene la forma de la Fase 7")
    contenido = resultado_resumen["contenido"]
    if not (isinstance(resultado_resumen.get("ejecucion"), dict)
            and isinstance(contenido.get("alguna_supera_umbral_exploratorio"), bool)
            and isinstance(contenido.get("estadisticas"), list)
            and all(_estadistica_valida(e) for e in contenido["estadisticas"])):
        raise ArtefactoSimulacionError("el contenido no tiene la forma de la Fase 7")


def verificar(parametros_: dict, resultado_resumen: dict, num_iteraciones: int | None = None) -> None:
    """Lanza `ArtefactoSimulacionError` con el motivo si la fila no es integra.
    Comprueba cada tipo antes de usarlo: con cualquier valor JSON no lanza
    otra excepcion."""
    if not isinstance(parametros_, dict) or not isinstance(resultado_resumen, dict):
        raise ArtefactoSimulacionError("parametros o resultado no son objetos JSON")
    if parametros_.get("esquema") != ESQUEMA_IDENTIDAD or resultado_resumen.get("esquema") != ESQUEMA_RESULTADO:
        raise ArtefactoSimulacionError("esquema desconocido")
    try:
        sin_clave = {k: v for k, v in parametros_.items() if k != "clave"}
        if parametros_.get("clave") != sha256(sin_clave):
            raise ArtefactoSimulacionError("la clave no corresponde a los parametros (identidad alterada)")
        if resultado_resumen.get("clave") != parametros_["clave"]:
            raise ArtefactoSimulacionError("el resultado pertenece a otra identidad")
        contenido = resultado_resumen.get("contenido")
        if resultado_resumen.get("contenido_sha256") != sha256(contenido):
            raise ArtefactoSimulacionError("el contenido no corresponde a su huella (resultado alterado)")
        cuerpo = {k: v for k, v in resultado_resumen.items() if k != "integridad_sha256"}
        if resultado_resumen.get("integridad_sha256") != sha256({"parametros": parametros_, "resultado": cuerpo}):
            raise ArtefactoSimulacionError("la huella de integridad no coincide (fila alterada)")
    except ArtefactoSimulacionError:
        raise
    except (EntradaRegistroInvalidaError, TypeError, ValueError, RecursionError) as error:  # NaN, anidacion extrema
        raise ArtefactoSimulacionError(f"la fila no tiene serializacion canonica ({type(error).__name__})") from None
    if not isinstance(contenido, dict):
        raise ArtefactoSimulacionError("el contenido no es un objeto JSON")
    iteraciones = parametros_.get("iteraciones")
    if contenido.get("iteraciones") != iteraciones or contenido.get("juego") != parametros_.get("juego"):
        raise ArtefactoSimulacionError("el contenido no coincide con la identidad")
    if num_iteraciones is not None and num_iteraciones != iteraciones:
        raise ArtefactoSimulacionError("num_iteraciones de la fila no coincide con la identidad")
    _forma(parametros_, resultado_resumen)


def verificar_fila(parametros_, resultado_resumen, num_iteraciones, juego_de_la_fila: str | None) -> None:
    """Comprobacion UNICA de una fila de la tabla `simulaciones` (listado,
    panel, lectura individual, reutilizacion y publicacion concurrente):
    `verificar` y, ademas, que el juego de la columna `juego_id`
    (`juego_de_la_fila`, None si no corresponde a ninguno) sea el de su
    identidad."""
    verificar(parametros_, resultado_resumen, num_iteraciones)
    if juego_de_la_fila != parametros_["juego"]:
        raise ArtefactoSimulacionError(f"el juego de la fila ({juego_de_la_fila or 'desconocido'}) no coincide con "
                                       f"el de su identidad ({parametros_['juego']})")


def exportacion(fila: dict) -> dict:
    """JSON derivado de la fila verificada (no es otra fuente canonica)."""
    return {"esquema": ESQUEMA_EXPORTACION, "derivado_de": "tabla simulaciones", "id": fila["id"],
            "juego": fila["juego"], "num_iteraciones": fila["num_iteraciones"], "ejecutado_en": fila["ejecutado_en"],
            "duracion_ms": fila["duracion_ms"], "parametros": copy.deepcopy(fila["parametros"]),
            "resultado_resumen": copy.deepcopy(fila["resultado_resumen"])}


def json_de_exportacion(fila: dict) -> str:
    return json.dumps(exportacion(fila), ensure_ascii=False, indent=1, sort_keys=True) + "\n"


_COLUMNAS = ("id", "clave", "juego", "corte", "iteraciones", "semilla", "estadistica", "observado",
             "media_simulada", "desviacion_simulada", "referencia_analitica", "percentil_observado",
             "p_valor_empirico", "p_valor_ajustado_bonferroni", "supera_umbral_exploratorio", "observado_exacto",
             "media_simulada_exacta", "p_valor_empirico_exacto")


def _celda(valor) -> str:
    """Sin formulas: un texto que empieza por = + - @ se antepone con '."""
    texto = "" if valor is None else str(valor)
    return "'" + texto if texto[:1] in ("=", "+", "-", "@") else texto


def csv_de_exportacion(fila: dict) -> str:
    p = fila["parametros"]
    salida = io.StringIO()
    escritor = csv.writer(salida, lineterminator="\n")
    escritor.writerow(_COLUMNAS)
    for e in fila["resultado_resumen"]["contenido"]["estadisticas"]:
        ref = e["referencia_analitica"]
        escritor.writerow([_celda(v) for v in (
            fila["id"], p["clave"], p["juego"], p["corte"], p["iteraciones"], p["semilla"], e["nombre"],
            e["observado"]["valor"], e["simulado"]["media"], e["simulado"]["desviacion"],
            None if ref is None else ref["valor"], e["percentil_observado"]["valor"], e["p_valor_empirico"]["valor"],
            e["p_valor_ajustado_bonferroni"]["valor"], str(e["supera_umbral_exploratorio"]).lower(),
            e["observado"]["exacto"], e["simulado"]["media_exacta"], e["p_valor_empirico"]["exacto"])])
    return salida.getvalue()

"""
Seguimiento acumulado del rendimiento por juego (Producto 3).

Se calcula siempre desde los pronosticos guardados y el historico ACTUAL
(sin copias de resultados): si un sorteo se corrige, la comparacion cambia
y se avisa; el artefacto original no cambia.

POLITICA DE SELECCION (fijada antes de calcular): una sola emision por
juego y objetivo, la PRIMERA segun la secuencia de emision sellada en el
artefacto (`generacion.secuencia_en_el_objetivo`). Nunca se elige despues
la version con mas aciertos; las versiones posteriores se pueden consultar
pero no son oportunidades adicionales. El objetivo se excluye (sin
sustituir la emision por otra mas favorable) si:
- hay un artefacto ilegible o alterado de ese objetivo (no se puede saber
  si era el primero);
- hay varios artefactos y alguno no tiene secuencia (artefactos antiguos):
  el orden es ambiguo y no se supone anterioridad;
- el historico hasta el corte de la emision seleccionada cambio o no esta
  disponible;
- el resultado no se puede evaluar con las probabilidades guardadas.

TIPOS DE EMISION, siempre separados (nunca se agregan juntos):
- `retrospectiva`: el objetivo ya estaba en la base local al generar;
- `seguimiento`: el objetivo no estaba cargado al generar. Esa condicion
  local no demuestra que el pronostico se emitiera antes del sorteo real.
Aparte se muestra la evaluacion walk-forward incluida en el artefacto.

Filtros (iguales para JSON, tabla y grafica): juego, tipo de emision y
periodo por fecha de generacion del pronostico seleccionado.

Diferencia = perdida del modelo - perdida de la uniforme sobre los mismos
objetivos: negativa si el modelo tuvo menor perdida. Es una descripcion de
estos objetivos, no una ventaja predictiva demostrada.
"""
from __future__ import annotations

from collections import Counter
from datetime import date

from app.application.interfaces.pronostico_experimental_store import PronosticoGuardado, PronosticoIlegible
from app.application.ml import rendimiento_observado as ro_metricas
from app.application.ml import resultados_observados as ro
from app.application.use_cases.pronostico_experimental import JUEGOS, _historicos, _juego

TIPOS = {"reconstruccion_retrospectiva": "retrospectiva",
         "emitido_sin_el_resultado_en_la_base_local": "seguimiento",
         "sin_clasificacion_al_generar": "sin_clasificacion"}
FILTROS_DE_EMISION = ("todas", "retrospectiva", "seguimiento")
MUESTRA_PEQUENA = 10

POLITICA = ("Una emision por objetivo: la primera segun la secuencia sellada. Nunca se elige despues la mas "
            "favorable; si la seleccionada no es evaluable, el objetivo se excluye sin sustituirla.")
NOTA_SEGUIMIENTO = ("Seguimiento: el objetivo no estaba cargado en la base local al generar. Eso no demuestra que "
                    "el pronostico se emitiera antes de celebrarse el sorteo.")
SIGNO = ("Diferencia = perdida del modelo - perdida de la referencia uniforme en los mismos objetivos. Negativa: el "
         "modelo tuvo menor perdida; positiva: la uniforme fue mejor. Describe estos objetivos; no demuestra ventaja.")


def _secuencia(g: PronosticoGuardado) -> int:
    v = g.artefacto["generacion"].get("secuencia_en_el_objetivo")
    return v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else 0


def _seleccionar(guardados: list[PronosticoGuardado], ilegibles_del_objetivo: int):
    """(seleccionado, motivo de exclusion o None, versiones)."""
    if ilegibles_del_objetivo:
        return None, "artefacto_ilegible_en_el_objetivo", len(guardados) + ilegibles_del_objetivo
    if len(guardados) > 1 and any(_secuencia(g) == 0 for g in guardados):
        return None, "orden_de_emision_ambiguo", len(guardados)
    return min(guardados, key=_secuencia), None, len(guardados)


def _fecha_generacion(artefacto: dict) -> str | None:
    valor = str((artefacto.get("generacion") or {}).get("generado_en") or "")
    return valor[:10] or None


def _fila(codigo: str, objetivo: int, seleccionado, motivo, versiones: int, completo) -> dict:
    fila = {"objetivo": objetivo, "identificador": None, "versiones": versiones, "fecha_generacion": None,
            "tipo": "desconocido", "estado": "excluido", "motivo": motivo, "fecha_sorteo": None,
            "aciertos": None, "de": None, "superbalota": None, "metricas": None, "avisos": []}
    if seleccionado is None:
        return fila
    a = seleccionado.artefacto
    fila.update(identificador=seleccionado.identificador, fecha_generacion=_fecha_generacion(a))
    comparacion = ro.comparar_con_resultado(a, completo)
    fila["tipo"] = TIPOS.get(comparacion["emision"], "sin_clasificacion")
    fila["avisos"] = [d["tipo"] for d in comparacion["discrepancias"]]
    if fila["tipo"] == "sin_clasificacion":
        fila["motivo"] = "sin_clasificacion_temporal_al_generar"
        return fila
    if comparacion["estado"] == "pendiente":
        fila.update(estado="pendiente", motivo=None)
        return fila
    if comparacion["estado"] == "no_corresponde":
        fila["motivo"] = "sin_resultado_en_la_base"
        return fila
    corte = comparacion["historico_hasta_el_corte"]["estado"]
    fila["fecha_sorteo"] = comparacion["fecha"]
    if corte != "coincide":
        fila["motivo"] = f"historico_hasta_el_corte_{corte}"
        return fila
    resultado, coincidencias = comparacion["resultado"], comparacion["coincidencias"]
    try:
        if codigo == "COLORLOTO":
            metricas = ro_metricas.metricas_colorloto(a, resultado["pares"])
            fila.update(aciertos=coincidencias["pares"], de=coincidencias["de"])
        else:
            metricas = ro_metricas.metricas_numeros(a, resultado["numeros"])
            fila.update(aciertos=coincidencias["numeros"], de=coincidencias["de"])
            fila["superbalota"] = ro_metricas.metricas_superbalota(a, resultado.get("superbalota"))
    except ro_metricas.ObjetivoNoEvaluableError:
        fila["motivo"] = "resultado_no_evaluable_con_el_artefacto"
        return fila
    fila.update(estado="incluido", motivo=None, metricas=metricas)
    return fila


def _media(valores: list[float]) -> float | None:
    return sum(valores) / len(valores) if valores else None


def _agregado(filas: list[dict], codigo: str) -> dict:
    incluidas = sorted((f for f in filas if f["estado"] == "incluido"), key=lambda f: f["objetivo"])
    n = len(incluidas)
    salida = {
        "objetivos": len(filas), "incluidos": n,
        "pendientes": sum(1 for f in filas if f["estado"] == "pendiente"),
        "excluidos": sum(1 for f in filas if f["estado"] == "excluido"),
        "excluidos_por_motivo": dict(Counter(f["motivo"] for f in filas if f["estado"] == "excluido")),
        "muestra_pequena": 0 < n < MUESTRA_PEQUENA,
        "aciertos": None, "superbalota": None, "perdidas": None, "serie": [],
    }
    if not n:
        return salida
    de = incluidas[0]["de"]
    aciertos = [f["aciertos"] for f in incluidas]
    salida["aciertos"] = {"suma": sum(aciertos), "promedio": sum(aciertos) / n, "de": de, "objetivos": n,
                          "distribucion": {str(k): v for k, v in sorted(Counter(aciertos).items())}}
    perdidas = {}
    claves = [("log_loss", "log_loss_uniforme"), ("brier", "brier_uniforme")]
    if codigo == "COLORLOTO":
        claves.append(("log_loss_multiconjunto", "log_loss_multiconjunto_uniforme"))
    for modelo, uniforme in claves:
        m = _media([f["metricas"][modelo] for f in incluidas])
        u = _media([f["metricas"][uniforme] for f in incluidas])
        perdidas[modelo] = {"modelo": m, "uniforme": u, "diferencia": m - u, "objetivos": n}
    salida["perdidas"] = perdidas
    con_sb = [f["superbalota"] for f in incluidas if f["superbalota"]]
    if con_sb:
        k = len(con_sb)
        salida["superbalota"] = {
            "aciertos": sum(1 for s in con_sb if s["acierto"]), "objetivos": k,
            "log_loss": {"modelo": _media([s["log_loss"] for s in con_sb]),
                         "uniforme": _media([s["log_loss_uniforme"] for s in con_sb])},
            "brier": {"modelo": _media([s["brier"] for s in con_sb]),
                      "uniforme": _media([s["brier_uniforme"] for s in con_sb])}}
        for clave in ("log_loss", "brier"):
            salida["superbalota"][clave]["diferencia"] = (salida["superbalota"][clave]["modelo"]
                                                         - salida["superbalota"][clave]["uniforme"])
    acumulada = 0.0
    for f in incluidas:
        diferencia = f["metricas"]["log_loss"] - f["metricas"]["log_loss_uniforme"]
        acumulada += diferencia
        salida["serie"].append({"objetivo": f["objetivo"], "diferencia": diferencia, "acumulada": acumulada})
    return salida


class ConsultarRendimiento:
    def __init__(self, almacen, juego_repository, resultados_repository):
        self._almacen = almacen
        self._juegos = juego_repository
        self._resultados = resultados_repository

    def ejecutar(self, codigo_juego: str, *, emision: str = "todas", desde: date | None = None,
                 hasta: date | None = None) -> dict:
        codigo = _juego(codigo_juego)
        if emision not in FILTROS_DE_EMISION:
            raise ValueError(f"tipo de emision admitido: {', '.join(FILTROS_DE_EMISION)}")
        elementos = self._almacen.listar(codigo)
        guardados = [e for e in elementos if isinstance(e, PronosticoGuardado)]
        ilegibles = [e for e in elementos if isinstance(e, PronosticoIlegible)]
        objetivos_de = getattr(self._almacen, "objetivos_de_archivos", lambda _c: {})(codigo)
        ilegibles_por_objetivo = Counter(objetivos_de.get(e.identificador) for e in ilegibles)
        _, completo = _historicos(self._juegos, self._resultados, codigo, None)

        por_objetivo: dict[int, list[PronosticoGuardado]] = {}
        for g in guardados:
            por_objetivo.setdefault(int(g.artefacto["pronostico"]["objetivo"]), []).append(g)
        objetivos = sorted(set(por_objetivo) | {o for o in ilegibles_por_objetivo if o is not None})
        filas = []
        for objetivo in objetivos:
            seleccionado, motivo, versiones = _seleccionar(por_objetivo.get(objetivo, []),
                                                           ilegibles_por_objetivo.get(objetivo, 0))
            filas.append(_fila(codigo, objetivo, seleccionado, motivo, versiones, completo))

        def pasa(f: dict) -> bool:
            if emision != "todas" and f["tipo"] != emision:
                return False
            if desde or hasta:
                if f["fecha_generacion"] is None:
                    return False
                d = date.fromisoformat(f["fecha_generacion"])
                if (desde and d < desde) or (hasta and d > hasta):
                    return False
            return True

        filtradas = [f for f in filas if pasa(f)]
        tipos = ["retrospectiva", "seguimiento"] if emision == "todas" else [emision]
        ultimo = guardados[0] if guardados else None
        walk_forward = None
        if ultimo is not None:
            agregado = ultimo.artefacto["evaluacion_walk_forward"]["agregado"]
            walk_forward = {"identificador": ultimo.identificador, "objetivo": ultimo.artefacto["pronostico"]["objetivo"],
                            "modelo": agregado["modelo"], "referencia_uniforme": agregado["referencia_uniforme"],
                            "veredicto": agregado["comparacion"]["veredicto"]}
        return {
            "juego": codigo,
            "estado_de_uso": "experimental_no_acreditado",
            "filtros": {"emision": emision, "desde": desde.isoformat() if desde else None,
                        "hasta": hasta.isoformat() if hasta else None,
                        "periodo_por": "fecha de generacion del pronostico seleccionado"},
            "politica": POLITICA, "signo": SIGNO, "nota_seguimiento": NOTA_SEGUIMIENTO,
            "por_tipo": {t: _agregado([f for f in filtradas if f["tipo"] == t], codigo) for t in tipos},
            "otros": {"sin_clasificacion_o_desconocido": sum(1 for f in filtradas
                                                             if f["tipo"] not in ("retrospectiva", "seguimiento"))},
            "artefactos_ilegibles": len(ilegibles),
            "filas": filtradas,
            "walk_forward_del_ultimo_artefacto": walk_forward,
        }


__all__ = ["ConsultarRendimiento", "FILTROS_DE_EMISION", "JUEGOS"]

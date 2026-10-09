"""
Producto 6: agregados por linea, comparacion directa sobre una muestra comun,
evolucion por objetivo y evaluacion de carteras. Modulo puro.

- Las perdidas por objetivo son las de `rendimiento_observado` (las mismas de
  Productos 3 y 4) con las probabilidades congeladas; aqui solo se promedian
  igual que Producto 3 (media aritmetica por objetivo incluido).
- Diferencia = perdida del modelo - perdida de la uniforme que declara el
  propio artefacto (Productos 1-4) o la uniforme exacta del mismo universo
  (vector fuente de Producto 5): negativa = menor perdida en ESA muestra.
- Comparacion directa: la interseccion de los objetivos admitidos de TODAS las
  lineas elegidas (una linea elegida sin objetivos deja la muestra comun vacia;
  nunca se retira en silencio). Un objetivo con universos distintos entre las
  lineas sale de la muestra comun con su motivo. Sin muestra comun no hay
  clasificacion.
- La superbalota va aparte y nunca se suma a la perdida de los numeros; no se
  agregan juegos distintos ni tipos de emision distintos.
- Carteras: aciertos observados por combinacion y maximo por cartera, en una
  seccion separada del vector de probabilidades; solo se comparan carteras con
  el mismo numero de combinaciones, con diversidad y semilla visibles.
"""
from __future__ import annotations

from collections import Counter

MUESTRA_PEQUENA = 10
# Empate: |diferencia| <= 1e-9. Las probabilidades se guardan con 12 decimales
# (vector fuente de Producto 5); por debajo de ese umbral la diferencia es ruido
# de redondeo del almacenamiento, no una ventaja ni una desventaja.
TOLERANCIA_EMPATE = 1e-9
SIGNO = ("Diferencia = pérdida del modelo − pérdida de la uniforme en los mismos objetivos. Negativa: menor pérdida "
         "en esta muestra; positiva: la uniforme fue mejor. Describe estos objetivos; no demuestra ventaja futura.")
CLAVES_DE_PERDIDA = (("log_loss", "log_loss_uniforme"), ("brier", "brier_uniforme"))
CLAVES_COLORLOTO = (("log_loss_multiconjunto", "log_loss_multiconjunto_uniforme"),)


def _media(valores: list[float]) -> float | None:
    return sum(valores) / len(valores) if valores else None


def veredicto(diferencia: float | None) -> str | None:
    if diferencia is None:
        return None
    if abs(diferencia) <= TOLERANCIA_EMPATE:
        return "empate"
    return "menor_perdida_que_la_uniforme_en_esta_muestra" if diferencia < 0 else "la_uniforme_fue_mejor"


def agregado(filas: list[dict], juego: str) -> dict:
    """Recuentos de estado y, sobre las incluidas, perdidas medias, aciertos,
    superbalota aparte y la serie de diferencias (misma muestra en tabla y
    grafica)."""
    incluidas = sorted((f for f in filas if f["estado"] == "incluido"), key=lambda f: f["objetivo"])
    n = len(incluidas)
    salida = {"objetivos": len(filas), "incluidos": n,
              "pendientes": sum(1 for f in filas if f["estado"] == "pendiente"),
              "excluidos": sum(1 for f in filas if f["estado"] == "excluido"),
              "sin_base": sum(1 for f in filas if f["estado"] == "sin_base"),
              "excluidos_por_motivo": dict(sorted(Counter(f["motivo"] for f in filas
                                                          if f["estado"] == "excluido").items())),
              "muestra_pequena": 0 < n < MUESTRA_PEQUENA, "aciertos": None, "perdidas": None,
              "superbalota": None, "serie": []}
    if not n:
        return salida
    con_aciertos = [f for f in incluidas if f.get("aciertos") is not None]
    if con_aciertos:
        valores = [f["aciertos"] for f in con_aciertos]
        salida["aciertos"] = {"suma": sum(valores), "promedio": sum(valores) / len(valores),
                              "de": con_aciertos[0]["de"], "objetivos": len(valores),
                              "distribucion": {str(k): v for k, v in sorted(Counter(valores).items())}}
    perdidas = {}
    claves = CLAVES_DE_PERDIDA + (CLAVES_COLORLOTO if juego == "COLORLOTO" else ())
    for modelo, uniforme in claves:
        m = _media([f["metricas"][modelo] for f in incluidas])
        u = _media([f["metricas"][uniforme] for f in incluidas])
        perdidas[modelo] = {"modelo": m, "uniforme": u, "diferencia": m - u, "objetivos": n,
                            "veredicto": veredicto(m - u)}
    salida["perdidas"] = perdidas
    con_sb = [f["superbalota"] for f in incluidas if f.get("superbalota")]
    if con_sb:
        sb = {"aciertos": sum(1 for s in con_sb if s["acierto"]), "objetivos": len(con_sb)}
        for clave, uniforme in (("log_loss", "log_loss_uniforme"), ("brier", "brier_uniforme")):
            m, u = _media([s[clave] for s in con_sb]), _media([s[uniforme] for s in con_sb])
            sb[clave] = {"modelo": m, "uniforme": u, "diferencia": m - u, "veredicto": veredicto(m - u)}
        salida["superbalota"] = sb
    acumulada = 0.0
    for f in incluidas:
        diferencia = f["metricas"]["log_loss"] - f["metricas"]["log_loss_uniforme"]
        acumulada += diferencia
        salida["serie"].append({"objetivo": f["objetivo"], "log_loss": f["metricas"]["log_loss"],
                                "log_loss_uniforme": f["metricas"]["log_loss_uniforme"],
                                "diferencia": diferencia, "acumulada": acumulada})
    return salida


def comparar(seleccion: list[str], filas_por_linea: dict[str, list[dict]], juego: str, tipo: str) -> dict:
    """Comparacion directa de las lineas elegidas sobre la interseccion exacta
    de sus objetivos admitidos (del tipo y filtros ya aplicados)."""
    admitidos = {clave: {f["objetivo"]: f for f in filas_por_linea.get(clave, [])
                         if f["tipo"] == tipo and f["estado"] == "incluido"} for clave in seleccion}
    totales = {clave: len(v) for clave, v in admitidos.items()}
    salida = {"tipo": tipo, "lineas": list(seleccion), "totales_individuales": totales, "objetivos_comunes": [],
              "fuera_de_la_muestra_comun": [], "por_linea": {}, "uniforme": None, "clasificacion": [],
              "estado": "sin_muestra_comun", "motivo": None, "signo": SIGNO}
    if len(seleccion) < 2:
        salida["motivo"] = "elige al menos dos lineas para una comparacion directa"
        return salida
    vacias = [clave for clave, v in admitidos.items() if not v]
    candidatos = set.union(*(set(v) for v in admitidos.values())) if admitidos else set()
    comunes = []
    for objetivo in sorted(candidatos):
        faltan = [clave for clave in seleccion if objetivo not in admitidos[clave]]
        if faltan:
            for clave in faltan:
                candidatas = [f for f in filas_por_linea.get(clave, []) if f["objetivo"] == objetivo]
                fila = (next((f for f in candidatas if f["tipo"] == tipo), None)
                        or next((f for f in candidatas if f["tipo"] in (None, "sin_clasificacion")), None)
                        or (candidatas[0] if candidatas else None))
                if fila is None:
                    motivo = "sin_emision_de_la_linea_para_el_objetivo"
                elif fila["tipo"] not in (tipo, None, "sin_clasificacion"):
                    motivo = f"emision_de_tipo_{fila['tipo']}"
                else:
                    motivo = f"{fila['estado']}: {fila['motivo']}" if fila["motivo"] else fila["estado"]
                salida["fuera_de_la_muestra_comun"].append({"objetivo": objetivo, "linea": clave, "motivo": motivo})
            continue
        universos = {admitidos[clave][objetivo]["universo"]["clave"] for clave in seleccion}
        if len(universos) > 1:
            salida["fuera_de_la_muestra_comun"].append(
                {"objetivo": objetivo, "linea": None,
                 "motivo": "universos_incompatibles: " + ", ".join(sorted(universos))})
            continue
        comunes.append(objetivo)
    salida["objetivos_comunes"] = comunes
    if not comunes:
        salida["motivo"] = ("lineas elegidas sin objetivos admitidos: " + ", ".join(vacias) if vacias
                            else "las lineas elegidas no comparten objetivos admitidos y compatibles")
        return salida
    salida["estado"] = "con_muestra_comun"
    for clave in seleccion:
        salida["por_linea"][clave] = agregado([admitidos[clave][o] for o in comunes], juego)
    primera = salida["por_linea"][seleccion[0]]["perdidas"]
    salida["uniforme"] = {clave: {"modelo": v["uniforme"]} for clave, v in primera.items()}
    filas = [{"linea": clave, "log_loss": a["perdidas"]["log_loss"]["modelo"],
              "uniforme": a["perdidas"]["log_loss"]["uniforme"],
              "diferencia": a["perdidas"]["log_loss"]["diferencia"],
              "veredicto": a["perdidas"]["log_loss"]["veredicto"]} for clave, a in salida["por_linea"].items()]
    filas.append({"linea": "uniforme", "log_loss": primera["log_loss"]["uniforme"],
                  "uniforme": primera["log_loss"]["uniforme"], "diferencia": 0.0, "veredicto": "referencia"})
    salida["clasificacion"] = sorted(filas, key=lambda f: (0.0 if f["veredicto"] in ("empate", "referencia")
                                                           else f["diferencia"], f["linea"] != "uniforme", f["linea"]))
    salida["muestra_pequena"] = len(comunes) < MUESTRA_PEQUENA
    return salida


# ---------------------------------------------------------------------------
# Carteras (aciertos observados de las combinaciones)
# ---------------------------------------------------------------------------

def resumen_de_cartera(filas: list[dict]) -> dict:
    incluidas = [f for f in filas if f["estado"] == "incluido"]
    maximos = [f["aciertos"]["maximo"] for f in incluidas]
    salida = {"objetivos": len(filas), "incluidos": len(incluidas),
              "pendientes": sum(1 for f in filas if f["estado"] == "pendiente"),
              "excluidos": sum(1 for f in filas if f["estado"] == "excluido"),
              "sin_base": sum(1 for f in filas if f["estado"] == "sin_base"),
              "excluidos_por_motivo": dict(sorted(Counter(f["motivo"] for f in filas
                                                          if f["estado"] == "excluido").items())),
              "maximos": dict(sorted(Counter(maximos).items())),
              "maximo_medio": sum(maximos) / len(maximos) if maximos else None,
              "superbalota_en_alguna_linea": sum(1 for f in incluidas
                                                 if f["aciertos"].get("superbalota_en_alguna_linea")),
              "muestra_pequena": 0 < len(incluidas) < MUESTRA_PEQUENA}
    return salida


def comparar_carteras(carteras: dict[str, dict], seleccion: list[str], tipo: str) -> dict:
    """Grupos por numero de combinaciones; dentro de cada grupo, la
    interseccion de objetivos incluidos de todas las carteras del grupo (una
    cartera sin objetivos se muestra con muestra vacia, no se retira)."""
    grupos: dict[int, list[str]] = {}
    for linea in seleccion:
        meta = (carteras.get(linea) or {}).get("metadatos") or {}
        grupos.setdefault(meta.get("cantidad"), []).append(linea)
    salida = []
    for cantidad, lineas in sorted(grupos.items(), key=lambda x: (x[0] is None, x[0] or 0)):
        incluidos = {l: {f["objetivo"]: f for f in carteras[l]["filas"]
                         if f.get("tipo") == tipo and f["estado"] == "incluido"} for l in lineas}
        comunes = sorted(set.intersection(*(set(v) for v in incluidos.values()))) if len(lineas) >= 2 else []
        salida.append({"combinaciones_por_cartera": cantidad, "lineas": lineas,
                       "totales_individuales": {l: len(v) for l, v in incluidos.items()},
                       "objetivos_comunes": comunes,
                       "maximos": {l: [incluidos[l][o]["aciertos"]["maximo"] for o in comunes] for l in lineas}
                       if comunes else {},
                       "estado": ("con_muestra_comun" if comunes else
                                  "una_sola_cartera" if len(lineas) < 2 else "sin_muestra_comun")})
    return {"tipo": tipo, "grupos": salida,
            "nota": ("Solo se comparan carteras con el mismo número de combinaciones sobre objetivos incluidos "
                     "comunes; una cartera de veinte líneas no se clasifica frente a una de una línea.")}

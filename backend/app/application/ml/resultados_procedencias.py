"""
Producto 6: adaptadores de las tres procedencias a una unidad comun de
evaluacion. Modulo puro: recibe artefactos ya leidos y el historico ya
consultado; no lee la base, no entrena y no escribe.

UNIDAD DE EVALUACION: una emision admitida por procedencia, linea y objetivo.
Cada procedencia conserva su politica de seleccion sellada (nunca fecha,
hash del nombre, mtime, orden de directorio ni la version con mas aciertos):

- `operacion` (pronosticos experimentales de Productos 1-3): la politica y las
  metricas de Producto 3 sin cambios (`rendimiento._seleccionar` y
  `rendimiento._fila`): una emision por juego y objetivo, la primera segun
  `secuencia_en_el_objetivo`; artefactos antiguos sin secuencia o un archivo
  ilegible en el objetivo excluyen el objetivo. La linea es la del artefacto
  seleccionado: `version_de_la_linea` y la huella de su configuracion.
- `laboratorio` (Producto 4): `laboratorio_artefactos.seguimiento_de_linea`
  por linea de modelo (modelo, version y perfil), primera emision por
  `secuencia_en_la_linea`.
- `carteras` (Producto 5): el vector `fuente` evaluado como probabilidades del
  MODELO (linea = modelo, version y perfil), nunca como probabilidades de
  inclusion de las lineas muestreadas. Una vez por objetivo y tipo aunque lo
  usen varias carteras (se registra cuales); si las primeras emisiones de esas
  carteras traen vectores distintos, el objetivo se excluye sin elegir uno.
  Los aciertos de las combinaciones se evaluan aparte (`carteras_de_juego`).

Cuatro estados separados por emision:
1. `integridad`: legible | ilegible_en_el_objetivo | orden_ambiguo.
2. `historico`: coincide | cambio | no_disponible (hasta el corte), o None si
   no se consulto.
3. `resultado`: observado | pendiente | no_corresponde | sin_base.
4. `estado` (admision): incluido | pendiente | excluido | sin_base, con
   `motivo`. Solo `incluido` entra en metricas y comparaciones. Una consulta
   sin base no es cero aciertos, cero perdida ni un pendiente confirmado.

`seguimiento` significa que el objetivo no estaba cargado en la base local al
emitir; no acredita que la emision precediera al sorteo real.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Sequence

from app.application.ml import carteras_artefactos as ca
from app.application.ml import laboratorio_artefactos as la
from app.application.ml import rendimiento_observado as rmet
from app.application.ml import resultados_observados as ro
from app.application.ml.registro_prospectivo import serializar_entrada
from app.application.use_cases import rendimiento as r3

PROCEDENCIAS = ("operacion", "laboratorio", "carteras")
NOMBRES_DE_PROCEDENCIA = {"operacion": "Operación diaria (Productos 1-3)",
                          "laboratorio": "Laboratorio de modelos (Producto 4)",
                          "carteras": "Modelo de cartera (Producto 5, vector fuente)"}
TIPOS = ("seguimiento", "retrospectiva")
ESTRATEGIAS_OPERACION = {"logistica_calibrada_ae36": "Logística calibrada AE-36",
                         "frecuencia_con_contraccion_a_la_uniforme": "Frecuencia contraída a la uniforme",
                         "pares_multinomial_con_suavizado_aditivo": "Pares multinomiales suavizados"}
NOTA_SEGUIMIENTO = la.NOTA_SEGUIMIENTO


def _huella(objeto) -> str:
    return hashlib.sha256(serializar_entrada(objeto)).hexdigest()


def clave_de_linea(procedencia: str, linea: str) -> str:
    return f"{procedencia}:{linea}"


# ---------------------------------------------------------------------------
# Probabilidades congeladas (las guardadas, sin normalizar de nuevo)
# ---------------------------------------------------------------------------

def _congelado_de_ranking(juego: str, pronostico: dict, superbalota: dict | None) -> dict:
    """Vectores del artefacto (Productos 1-4) tal como se guardaron."""
    if juego == "COLORLOTO":
        filas = sorted(pronostico["ranking_de_pares"], key=lambda f: (f["numero"], f["color"]))
        salida = {"tipo": "pares", "candidatos": [[f["numero"], f["color"]] for f in filas],
                  "probabilidad": [f["probabilidad"] for f in filas],
                  "probabilidad_uniforme": [f["probabilidad_uniforme"] for f in filas]}
    else:
        filas = sorted(pronostico["ranking"], key=lambda f: f["numero"])
        salida = {"tipo": "numeros", "candidatos": [f["numero"] for f in filas],
                  "probabilidad": [f["probabilidad"] for f in filas],
                  "probabilidad_uniforme": [f["probabilidad_uniforme"] for f in filas]}
    if superbalota:
        filas_sb = sorted(superbalota["pronostico"]["ranking"], key=lambda f: f["superbalota"])
        salida["superbalota"] = {"candidatos": [f["superbalota"] for f in filas_sb],
                                 "probabilidad": [f["probabilidad"] for f in filas_sb],
                                 "probabilidad_uniforme": [f["probabilidad_uniforme"] for f in filas_sb],
                                 "sugerida": superbalota["pronostico"]["sugerida"]}
    return salida


def congelado_de_fuente(juego: str, fuente: dict) -> dict:
    """Vector fuente de Producto 5 como probabilidades del modelo. Uniforme
    del mismo universo congelado: masa / candidatos (5/N por numero) o 1/M por
    par; se calcula exacta porque el vector fuente no la guarda."""
    candidatos = fuente["candidatos"]
    if juego == "COLORLOTO":
        orden = sorted(range(len(candidatos)), key=lambda i: (candidatos[i][0], candidatos[i][1]))
        salida = {"tipo": "pares", "candidatos": [list(candidatos[i]) for i in orden],
                  "probabilidad": [fuente["probabilidades"][i] for i in orden],
                  "probabilidad_uniforme": [1 / len(candidatos)] * len(candidatos)}
    else:
        orden = sorted(range(len(candidatos)), key=lambda i: candidatos[i])
        salida = {"tipo": "numeros", "candidatos": [candidatos[i] for i in orden],
                  "probabilidad": [fuente["probabilidades"][i] for i in orden],
                  "probabilidad_uniforme": [fuente["masa"] / len(candidatos)] * len(candidatos)}
    sb = fuente.get("superbalota")
    if sb:
        p = dict(zip(sb["candidatos"], sb["probabilidades"]))
        salida["superbalota"] = {"candidatos": sorted(p), "probabilidad": [p[c] for c in sorted(p)],
                                 "probabilidad_uniforme": [1 / len(p)] * len(p),
                                 "sugerida": min(p, key=lambda c: (-p[c], c))}
    return salida


def artefacto_de_congelado(juego: str, objetivo: int, congelado: dict) -> dict:
    """Estructura minima que esperan las funciones de `rendimiento_observado`
    (las mismas de Productos 3 y 4), construida con los valores congelados."""
    if congelado["tipo"] == "pares":
        pronostico = {"objetivo": objetivo, "ranking_de_pares": [
            {"numero": c[0], "color": c[1], "probabilidad": p, "probabilidad_uniforme": u}
            for c, p, u in zip(congelado["candidatos"], congelado["probabilidad"], congelado["probabilidad_uniforme"])]}
        return {"juego": juego, "pronostico": pronostico}
    pronostico = {"objetivo": objetivo, "ranking": [
        {"numero": c, "probabilidad": p, "probabilidad_uniforme": u}
        for c, p, u in zip(congelado["candidatos"], congelado["probabilidad"], congelado["probabilidad_uniforme"])]}
    artefacto = {"juego": juego, "pronostico": pronostico}
    sb = congelado.get("superbalota")
    if sb:
        artefacto["superbalota"] = {"pronostico": {"sugerida": sb["sugerida"], "ranking": [
            {"superbalota": c, "probabilidad": p, "probabilidad_uniforme": u}
            for c, p, u in zip(sb["candidatos"], sb["probabilidad"], sb["probabilidad_uniforme"])]}}
    return artefacto


def metricas_de_congelado(juego: str, objetivo: int, congelado: dict, resultado: dict) -> tuple[dict, dict | None]:
    """(metricas, superbalota) con las funciones existentes. Lanza
    `ObjetivoNoEvaluableError` si el resultado cae fuera del universo."""
    artefacto = artefacto_de_congelado(juego, objetivo, congelado)
    if juego == "COLORLOTO":
        return rmet.metricas_colorloto(artefacto, resultado["pares"]), None
    return (rmet.metricas_numeros(artefacto, resultado["numeros"]),
            rmet.metricas_superbalota(artefacto, resultado.get("superbalota")))


def universo_de(congelado: dict | None) -> dict | None:
    """Universo congelado: compatibilidad de comparacion y de la uniforme."""
    if congelado is None:
        return None
    n = len(congelado["candidatos"])
    if congelado["tipo"] == "pares":
        colores = sorted({c[1] for c in congelado["candidatos"]})
        return {"clave": f"pares:{n}:{_huella(congelado['candidatos'])[:12]}", "tipo": "pares", "candidatos": n,
                "descripcion": f"{n} pares número-color ({len(colores)} colores)"}
    return {"clave": f"numeros:{n}", "tipo": "numeros", "candidatos": n,
            "descripcion": f"{n} números candidatos"}


# ---------------------------------------------------------------------------
# Fila comun
# ---------------------------------------------------------------------------

def _fila(procedencia: str, linea: str, juego: str, objetivo: int, **campos) -> dict:
    fila = {"procedencia": procedencia, "linea": linea, "clave_linea": clave_de_linea(procedencia, linea),
            "juego": juego, "objetivo": objetivo, "tipo": None, "identificador": None, "versiones": None,
            "integridad": "legible", "historico": None, "resultado_estado": None, "estado": "excluido",
            "motivo": None, "fecha_sorteo": None, "resultado": None, "aciertos": None, "de": None,
            "metricas": None, "superbalota": None, "universo": None, "enlace": None, "carteras": None,
            "congelado": None}
    fila.update(campos)
    return fila


SIN_TIPO = (None, "sin_clasificacion")


def de_tipo(fila: dict, tipo: str) -> bool:
    """La fila entra en la vista de `tipo`. Las emisiones sin tipo (orden
    ambiguo, artefactos antiguos sin clasificacion temporal) se muestran en
    las dos vistas, siempre excluidas: nunca desaparecen en silencio."""
    return fila["tipo"] == tipo or fila["tipo"] in SIN_TIPO


def _cerrar(filas: list[dict]) -> list[dict]:
    """Una emision sin clasificacion temporal al generar no se admite (no se
    sabe si es seguimiento o retrospectiva): excluida con su motivo."""
    for f in filas:
        if f["tipo"] == "sin_clasificacion":
            f.update(estado="excluido", motivo="sin_clasificacion_temporal_al_generar", metricas=None,
                     superbalota=None, congelado=None)
    return filas


def _fecha_de(completo, objetivo: int) -> str | None:
    observado = next((r for r in completo if r.numero_sorteo == objetivo), None)
    return observado.fecha.isoformat() if observado is not None else None


def _con_resultado(fila: dict, comparacion: dict | None, completo) -> dict:
    """Integra el resultado observado y el historico hasta el corte (estados
    2 y 3), sin decidir la admision."""
    if completo is None:
        fila.update(resultado_estado="sin_base", historico=None)
        return fila
    if comparacion is not None:
        fila.update(historico=comparacion["historico_hasta_el_corte"]["estado"],
                    resultado_estado=comparacion["estado"], fecha_sorteo=comparacion.get("fecha"),
                    resultado=comparacion.get("resultado"))
    return fila


# ---------------------------------------------------------------------------
# Procedencia `operacion` (Productos 1-3)
# ---------------------------------------------------------------------------

def linea_de_operacion(artefacto: dict) -> dict:
    version = artefacto.get("version_de_la_linea") or artefacto.get("esquema", "sin_version")
    configuracion = artefacto.get("configuracion") or {}
    estrategia = artefacto.get("estrategia") or {}
    nombre = estrategia.get("nombre") or ("logistica_calibrada_ae36" if version == "producto1-1" else version)
    huella_conf = _huella(configuracion)
    return {"id": f"{version}-c{huella_conf[:10]}", "version": version, "estrategia": nombre,
            "nombre": f"{ESTRATEGIAS_OPERACION.get(nombre, nombre)} ({version})",
            "configuracion": configuracion, "configuracion_sha256": huella_conf}


def emisiones_operacion(juego: str, elementos: Sequence, objetivos_de_archivos: dict, completo, slug: str
                        ) -> tuple[dict, list[dict]]:
    """`elementos`: lo que devuelve el almacen de Productos 1-3 para el juego
    (guardados e ilegibles). Devuelve ({linea: metadatos}, filas)."""
    from app.application.interfaces.pronostico_experimental_store import PronosticoGuardado, PronosticoIlegible

    guardados = [e for e in elementos if isinstance(e, PronosticoGuardado)]
    ilegibles = [e for e in elementos if isinstance(e, PronosticoIlegible)]
    ilegibles_por_objetivo = Counter(objetivos_de_archivos.get(e.identificador) for e in ilegibles)
    lineas: dict[str, dict] = {}
    por_objetivo: dict[int, list] = {}
    for g in guardados:
        linea = linea_de_operacion(g.artefacto)
        lineas.setdefault(linea["id"], {**linea, "procedencia": "operacion", "artefactos": 0})["artefactos"] += 1
        por_objetivo.setdefault(int(g.artefacto["pronostico"]["objetivo"]), []).append(g)
    objetivos = sorted(set(por_objetivo) | {o for o in ilegibles_por_objetivo if o is not None})
    filas = []
    for objetivo in objetivos:
        grupo = por_objetivo.get(objetivo, [])
        seleccionado, motivo, versiones = r3._seleccionar(grupo, ilegibles_por_objetivo.get(objetivo, 0))
        if seleccionado is None:
            # el objetivo no tiene primera emision determinable: se excluye en cada linea afectada
            afectadas = sorted({linea_de_operacion(g.artefacto)["id"] for g in grupo}) or sorted(lineas)
            integridad = "ilegible_en_el_objetivo" if motivo == "artefacto_ilegible_en_el_objetivo" else "orden_ambiguo"
            for linea in afectadas:
                filas.append(_fila("operacion", linea, juego, objetivo, versiones=versiones, integridad=integridad,
                                   estado="excluido", motivo=motivo))
            continue
        a = seleccionado.artefacto
        linea = linea_de_operacion(a)["id"]
        congelado = _congelado_de_ranking(juego, a["pronostico"], a.get("superbalota"))
        fila = _fila("operacion", linea, juego, objetivo, identificador=seleccionado.identificador,
                     versiones=versiones, universo=universo_de(congelado), congelado=congelado,
                     enlace=f"/pronosticos/{slug}?id={seleccionado.identificador}")
        if completo is None:
            tipo = r3.TIPOS.get(ro._emision(a), "sin_clasificacion")
            filas.append({**_con_resultado(fila, None, None), "tipo": tipo, "estado": "sin_base",
                          "motivo": "base de datos no disponible", "congelado": None})
            continue
        comparacion = ro.comparar_con_resultado(a, completo)
        _con_resultado(fila, comparacion, completo)
        p3 = r3._fila(juego, objetivo, seleccionado, None, versiones, completo)
        fila.update(tipo=p3["tipo"], estado=p3["estado"], motivo=p3["motivo"], aciertos=p3["aciertos"], de=p3["de"],
                    metricas=p3["metricas"], superbalota=p3["superbalota"])
        if fila["estado"] != "incluido":
            fila["congelado"] = None
        filas.append(fila)
    return lineas, _cerrar(filas)


# ---------------------------------------------------------------------------
# Procedencia `laboratorio` (Producto 4)
# ---------------------------------------------------------------------------

def linea_de_laboratorio(artefacto: dict) -> dict:
    linea = artefacto["linea"]
    modelo = artefacto.get("modelo") or {}
    perfil = linea.get("perfil", "predeterminado")
    registrado = linea.get("registrado")
    return {"id": linea["id"], "modelo": linea["modelo"], "version": str(linea["version"]), "perfil": perfil,
            "nombre": f"{modelo.get('nombre', linea['modelo'])} v{linea['version']}"
                      + ("" if perfil == "predeterminado" else f" ({perfil})")
                      + ("" if not registrado else f" · versión registrada {registrado['numero']}")}


def emisiones_laboratorio(juego: str, lineas_y_elementos: dict, completo) -> tuple[dict, list[dict]]:
    """`lineas_y_elementos`: {linea: [GuardadoLaboratorio | IlegibleLaboratorio]} del almacen de Producto 4."""
    from app.application.interfaces.laboratorio_store import GuardadoLaboratorio

    lineas, filas = {}, []
    for nombre, guardados in sorted(lineas_y_elementos.items()):
        elementos, artefactos = [], {}
        meta = None
        for e in guardados:
            if isinstance(e, GuardadoLaboratorio):
                elementos.append({"objetivo": e.objetivo, "secuencia": e.secuencia, "identificador": e.identificador,
                                  "artefacto": e.artefacto})
                artefactos[e.identificador] = e.artefacto
                meta = meta or linea_de_laboratorio(e.artefacto)
            else:
                elementos.append({"objetivo": e.objetivo, "secuencia": None, "identificador": e.identificador,
                                  "artefacto": None, "ilegible": e.motivo})
        lineas[nombre] = {**(meta or {"id": nombre, "nombre": nombre}), "procedencia": "laboratorio",
                          "artefactos": len(guardados)}
        seguimiento = la.seguimiento_de_linea(elementos, completo)
        for f in seguimiento["filas"]:
            a = artefactos.get(f.get("identificador"))
            congelado = _congelado_de_ranking(juego, a["pronostico"], a.get("superbalota")) if a else None
            fila = _fila("laboratorio", nombre, juego, f["objetivo"], tipo=f.get("tipo"),
                         identificador=f.get("identificador"), versiones=f.get("versiones"),
                         universo=universo_de(congelado), congelado=congelado,
                         enlace=f"/laboratorio/pronosticos/{f['identificador']}" if f.get("identificador") else None)
            if f["estado"] == "excluido" and f.get("motivo") == "orden_ambiguo_por_archivo_ilegible":
                filas.append({**fila, "integridad": "orden_ambiguo", "estado": "excluido", "motivo": f["motivo"],
                              "congelado": None})
                continue
            if f["estado"] == "sin_base":
                filas.append({**fila, "resultado_estado": "sin_base", "estado": "sin_base", "motivo": f["motivo"],
                              "congelado": None})
                continue
            fila.update(historico=f.get("historico_hasta_el_corte"), resultado=f.get("resultado"))
            if f["estado"] in ("pendiente", "no_corresponde"):
                filas.append({**fila, "resultado_estado": f["estado"],
                              "estado": "pendiente" if f["estado"] == "pendiente" else "excluido",
                              "motivo": f["motivo"] if f["estado"] == "pendiente" else "sin_resultado_en_la_base",
                              "congelado": None})
                continue
            fila["resultado_estado"] = "observado"
            fila["fecha_sorteo"] = _fecha_de(completo, f["objetivo"])
            coincidencias = f.get("coincidencias") or {}
            clave = "pares" if juego == "COLORLOTO" else "numeros"
            fila.update(aciertos=coincidencias.get(clave), de=coincidencias.get("de"))
            if f["estado"] != "incluido":
                # Producto 4 da el texto del error de las metricas; aqui el mismo codigo que las otras procedencias
                motivo = (f["motivo"] if str(f["motivo"]).startswith("historico_hasta_el_corte_")
                          else "resultado_no_evaluable_con_el_artefacto")
                filas.append({**fila, "estado": "excluido", "motivo": motivo, "congelado": None})
                continue
            metricas = dict(f["metricas"])
            superbalota = metricas.pop("superbalota", None)
            filas.append({**fila, "estado": "incluido", "metricas": metricas, "superbalota": superbalota})
    return lineas, _cerrar(filas)


# ---------------------------------------------------------------------------
# Procedencia `carteras` (Producto 5): vector fuente y carteras
# ---------------------------------------------------------------------------

def linea_de_modelo_de_cartera(artefacto: dict) -> dict:
    linea = artefacto["linea"]
    perfil = linea.get("perfil", "predeterminado")
    modelo = artefacto.get("modelo") or {}
    sufijo = "" if perfil == "predeterminado" else f"-{perfil}"
    registrado = linea.get("registrado")
    reg = "" if not registrado else f"-reg{registrado['numero']}"
    return {"id": f"{linea['modelo']}-v{linea['version']}{reg}{sufijo}", "modelo": linea["modelo"],
            "version": str(linea["version"]), "perfil": perfil,
            "nombre": f"{modelo.get('nombre', linea['modelo'])} v{linea['version']}"
                      + ("" if perfil == "predeterminado" else f" ({perfil})")
                      + ("" if not registrado else f" · versión registrada {registrado['numero']}") + " · vector fuente"}


def seguimientos_de_carteras(lineas_y_elementos: dict, completo) -> dict:
    """{linea de cartera: (seguimiento de Producto 5, {identificador: artefacto})}."""
    from app.application.interfaces.carteras_store import GuardadoCarteras

    salida = {}
    for nombre, guardados in sorted(lineas_y_elementos.items()):
        elementos, artefactos = [], {}
        for e in guardados:
            if isinstance(e, GuardadoCarteras):
                elementos.append({"objetivo": e.objetivo, "secuencia": e.secuencia, "identificador": e.identificador,
                                  "artefacto": e.artefacto})
                artefactos[e.identificador] = e.artefacto
            else:
                elementos.append({"objetivo": e.objetivo, "secuencia": None, "identificador": e.identificador,
                                  "artefacto": None, "ilegible": e.motivo})
        salida[nombre] = (ca.seguimiento_de_linea(elementos, completo), artefactos)
    return salida


def emisiones_carteras(juego: str, seguimientos: dict, completo) -> tuple[dict, list[dict]]:
    """Vector fuente por linea de MODELO, objetivo y tipo: una sola vez aunque
    lo usen varias carteras; nunca se elige entre vectores distintos."""
    grupos: dict[tuple, list] = {}
    lineas: dict[str, dict] = {}
    ambiguas: dict[str, set] = {}
    for linea_cartera, (seguimiento, artefactos) in seguimientos.items():
        modelo_linea = None
        for a in artefactos.values():
            modelo_linea = linea_de_modelo_de_cartera(a)
            lineas.setdefault(modelo_linea["id"], {**modelo_linea, "procedencia": "carteras", "carteras": []})
            if linea_cartera not in lineas[modelo_linea["id"]]["carteras"]:
                lineas[modelo_linea["id"]]["carteras"].append(linea_cartera)
            break
        for f in seguimiento["filas"]:
            if f.get("identificador") is None or f.get("tipo") is None:
                if modelo_linea is not None:
                    ambiguas.setdefault(modelo_linea["id"], set()).add(f["objetivo"])
                continue
            a = artefactos[f["identificador"]]
            grupos.setdefault((linea_de_modelo_de_cartera(a)["id"], f["objetivo"], f["tipo"]), []).append(
                (linea_cartera, f, a))
    filas = []
    for (linea, objetivo, tipo), miembros in sorted(grupos.items(), key=lambda x: (x[0][0], x[0][1], x[0][2])):
        miembros.sort(key=lambda m: m[0])
        usos = [{"linea": m[0], "identificador": m[1]["identificador"]} for m in miembros]
        vectores = {_huella(m[2]["fuente"]) for m in miembros}
        _, f0, a0 = miembros[0]
        congelado = congelado_de_fuente(juego, a0["fuente"])
        fila = _fila("carteras", linea, juego, objetivo, tipo=tipo, identificador=f0["identificador"],
                     versiones=None, universo=universo_de(congelado), carteras=usos,
                     enlace=f"/carteras/guardadas/{f0['identificador']}", congelado=congelado)
        if objetivo in ambiguas.get(linea, set()):
            filas.append({**fila, "integridad": "orden_ambiguo", "estado": "excluido",
                          "motivo": "orden_ambiguo_en_alguna_cartera_del_modelo", "congelado": None})
            continue
        if len(vectores) > 1:
            filas.append({**fila, "estado": "excluido", "motivo": "vectores_fuente_distintos_en_el_objetivo",
                          "congelado": None})
            continue
        if f0["estado"] == "sin_base" or completo is None:
            filas.append({**fila, "resultado_estado": "sin_base", "estado": "sin_base",
                          "motivo": "base de datos no disponible", "congelado": None})
            continue
        fila["historico"] = f0.get("historico_hasta_el_corte")
        if f0["estado"] in ("pendiente", "no_corresponde"):
            filas.append({**fila, "resultado_estado": f0["estado"],
                          "estado": "pendiente" if f0["estado"] == "pendiente" else "excluido",
                          "motivo": f0["motivo"] if f0["estado"] == "pendiente" else "sin_resultado_en_la_base",
                          "congelado": None})
            continue
        resultado = f0.get("resultado")
        fila.update(resultado_estado="observado", resultado=resultado)
        fila["fecha_sorteo"] = _fecha_de(completo, objetivo)
        if fila["historico"] != "coincide":
            filas.append({**fila, "estado": "excluido", "motivo": "historico_hasta_el_corte_" + str(fila["historico"]),
                          "congelado": None})
            continue
        try:
            metricas, superbalota = metricas_de_congelado(juego, objetivo, congelado, resultado)
        except rmet.ObjetivoNoEvaluableError:
            filas.append({**fila, "estado": "excluido", "motivo": "resultado_no_evaluable_con_el_artefacto",
                          "congelado": None})
            continue
        # el vector no tiene sugerencia propia emitida: sus aciertos son los de las carteras (seccion aparte)
        filas.append({**fila, "estado": "incluido", "metricas": metricas, "superbalota": superbalota})
    return lineas, _cerrar(filas)


def carteras_de_juego(seguimientos: dict) -> dict:
    """Lineas de cartera (aciertos de las combinaciones), separadas del vector."""
    salida = {}
    for linea, (seguimiento, artefactos) in seguimientos.items():
        meta = None
        for a in artefactos.values():
            meta = {"modelo": a["linea"]["modelo"], "version": str(a["linea"]["version"]),
                    "perfil": a["linea"].get("perfil", "predeterminado"), "cantidad": a["linea"]["cantidad"],
                    "diversidad": a["linea"]["diversidad"], "semilla": a["linea"]["semilla"],
                    "nombre": (a.get("modelo") or {}).get("nombre", a["linea"]["modelo"])}
            break
        # Combinaciones congeladas de cada cartera INCLUIDA: con ellas y el resultado observado se recalculan
        # despues sus aciertos (funcion de Producto 5) sin la base ni el almacen de carteras.
        filas = [{**f, "congelado": {"combinaciones": artefactos[f["identificador"]]["cartera"]["combinaciones"]}}
                 if f["estado"] == "incluido" and f.get("identificador") in artefactos else f
                 for f in seguimiento["filas"]]
        salida[linea] = {"linea": linea, "metadatos": meta, "filas": filas,
                         "ilegibles_sin_objetivo": seguimiento["ilegibles_sin_objetivo"]}
    return salida

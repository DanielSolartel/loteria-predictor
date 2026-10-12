"""
Producto 5 -esquemas, identidad, seguimiento y exportacion de carteras.

ESQUEMAS NUEVOS (no cambian los de Productos 1-4):
- `carteras-comparacion/1`: comparacion exterior del modelo combinado con los
  candidatos de Producto 4, con la instantanea canonica del historico.
- `carteras-cartera/1`: cartera de combinaciones de un modelo para un
  objetivo, con la instantanea canonica y el vector fuente CONGELADO.
- `carteras-simulacion/1`: simulacion de una cartera frente a la cartera
  uniforme guardada, con las dos carteras exactas y el vector fuente.
- `carteras-configuracion/1`: configuracion explicita y versionada de
  carteras de un juego (modelo y version, cantidad, diversidad, semilla).

IDENTIDAD. La CLAVE DE ENTRADA es el SHA-256 canonico (AE-52) de lo que se
conoce ANTES del trabajo costoso: juego, reglas, paleta, corte y objetivo,
huella del historico, version de variables, modelo y receta (y, en el
modelo combinado, sus componentes y protocolo de pesos), parametros de la
cartera, version del algoritmo y de los flujos aleatorios, escenarios de
simulacion y entorno numerico. Con ella se busca lo ya guardado sin
reentrenar. Pesos, probabilidades y resultados derivados van en el cuerpo y
quedan cubiertos por `huella_de_reproduccion` y por el `sello` del archivo.
Fechas, tiempos y progreso van fuera del cuerpo reproducible.

SEGUIMIENTO. Por linea (modelo, version y parametros de cartera) y
objetivo, la PRIMERA cartera integra segun la secuencia sellada; si es
ilegible, alterada o no evaluable se excluye con su motivo, sin avanzar a
otra version. Emision con el objetivo no cargado, reconstruccion
retrospectiva, pendiente y excluida van por separado. Los resultados
observados no escriben en el artefacto. Nada de esto se mezcla con
frecuencias simuladas ni con perdidas del modelo en un unico porcentaje.

Modulo puro.
"""
from __future__ import annotations

import csv
import io
from collections import Counter
from collections.abc import Sequence

from app.application.ml import carteras_construccion as cc
from app.application.ml import carteras_ensemble as ce
from app.application.ml import carteras_simulacion as cs
from app.application.ml import laboratorio_artefactos as la
from app.application.ml import laboratorio_modelos as lm
from app.application.ml import laboratorio_variables as lv
from app.application.ml import pronostico_colorloto as pcl
from app.application.ml.pronostico_experimental import ESTADO_DE_USO
from app.application.ml.registro_prospectivo import serializar_entrada

ESQUEMA_COMPARACION = "carteras-comparacion/1"
ESQUEMA_CARTERA = "carteras-cartera/1"
ESQUEMA_SIMULACION = "carteras-simulacion/1"
ESQUEMA_CONFIGURACION = "carteras-configuracion/1"
VERSION_IMPLEMENTACION = "producto5-1"
VOLATILES = {ESQUEMA_COMPARACION: ("huella_de_reproduccion", "ejecucion", "sello"),
             ESQUEMA_CARTERA: ("huella_de_reproduccion", "generacion", "sello"),
             ESQUEMA_SIMULACION: ("huella_de_reproduccion", "ejecucion", "sello"),
             ESQUEMA_CONFIGURACION: ("huella_de_reproduccion", "registro", "sello")}

huella = la.huella
entorno = la.entorno


def json_canonico(artefacto: dict) -> bytes:
    """Bytes canonicos (AE-52) del artefacto: los mismos del archivo publicado.
    Las capas web y de comando exportan con esta funcion."""
    return serializar_entrada(artefacto)


class ArtefactoCarterasError(ValueError):
    pass


def contexto() -> dict:
    return {**la.contexto(), "uso": ("modelo combinado, carteras y simulacion experimentales; no es evidencia "
                                     "prospectiva, ventaja predictiva acreditada ni recomendacion de apuesta")}


def componer(cuerpo: dict, volatil: str, datos_volatiles: dict) -> dict:
    artefacto = {**cuerpo, "huella_de_reproduccion": huella(cuerpo), volatil: datos_volatiles}
    return {**artefacto, "sello": huella(artefacto)}


def cuerpo_de(artefacto: dict) -> dict:
    volatiles = VOLATILES.get(artefacto.get("esquema"))
    if volatiles is None:
        raise ArtefactoCarterasError(f"esquema no admitido: {artefacto.get('esquema')!r}")
    return {k: v for k, v in artefacto.items() if k not in volatiles}


def integro(artefacto: dict) -> bool:
    try:
        return (artefacto.get("sello") == huella({k: v for k, v in artefacto.items() if k != "sello"})
                and artefacto.get("huella_de_reproduccion") == huella(cuerpo_de(artefacto)))
    except (la.ArtefactoLaboratorioError, ArtefactoCarterasError, AttributeError, TypeError):
        return False


def instantanea_de(artefacto: dict) -> lv.Instantanea:
    instantanea = lv.instantanea_desde_canonicos(artefacto["juego"], artefacto["historico"]["sorteos"])
    if instantanea.huella() != artefacto["datos"]["sha256_historico"]:
        raise ArtefactoCarterasError("la instantanea guardada no corresponde a su huella")
    return instantanea


def _transformaciones() -> dict:
    return {"cardinalidad": {"epsilon": lm.EPSILON, "tolerancia": lm.TOLERANCIA_CARDINALIDAD,
                             "metodo": "desplazamiento comun de logits por biseccion"},
            "poisson": {"delta": lm.DELTA_POISSON, "metodo": "normalizacion de intensidades"},
            "mezcla": {"pasos": ce.PASOS_DE_MALLA, "mezclas": len(ce.MALLA),
                       "tolerancia_de_empate": ce.TOLERANCIA_DE_EMPATE, "tolerancia_de_masa": ce.TOLERANCIA_DE_MASA}}


def _datos(instantanea: lv.Instantanea) -> dict:
    return {**instantanea.procedencia(), "paleta_del_corte": list(instantanea.paleta())}


def _historico(instantanea: lv.Instantanea) -> dict:
    return {"formato": "sorteos canonicos (numero, fecha, numeros/superbalota o pares ordenados)",
            "sorteos": lv.sorteos_canonicos(instantanea)}


def receta_del_modelo(juego: str, modelo: str, perfil: str, registrado: dict | None = None) -> dict:
    """Receta de un modelo admitido para carteras (identidad de entrada).
    Fase 3: `registrado` ({clave, numero, sha256_estimador,
    corte_de_entrenamiento}) fija una version registrada CONGELADA del modelo;
    sin el, la receta es la de siempre (reentrena con la instantanea)."""
    if modelo not in ce.modelos_de_cartera(juego):
        raise ArtefactoCarterasError(f"modelo no admitido para {juego}: {modelo!r}")
    if modelo == ce.ID_ENSEMBLE:
        protocolo = ce.ProtocoloCarteras(perfil=perfil)
        return {"id": ce.ID_ENSEMBLE, "version": ce.VERSION_ENSEMBLE, "tipo": "modelo_combinado",
                "componentes": [{"id": c, "version": lm.CATALOGO[c].version,
                                 "parametros": lm.parametros_de(lm.CATALOGO[c], perfil)} for c in ce.COMPONENTES[juego]],
                "pesos": {"bloque_interno": protocolo.bloque_interno, "malla": protocolo.como_dict()["malla"]}}
    e = lm.CATALOGO[modelo]
    receta = {"id": e.id, "version": e.version, "tipo": e.tipo, "parametros": lm.parametros_de(e, perfil)}
    if registrado is not None:
        receta["registrado"] = dict(registrado)
    return receta


def descripcion_del_modelo(juego: str, modelo: str, perfil: str) -> dict:
    if modelo == ce.ID_ENSEMBLE:
        return ce.entrada_del_ensemble(juego)
    return lm.CATALOGO[modelo].como_dict(perfil)


# ---------------------------------------------------------------------------
# Comparacion
# ---------------------------------------------------------------------------

def identidad_de_comparacion(instantanea: lv.Instantanea, protocolo: ce.ProtocoloCarteras) -> dict:
    codigo = instantanea.codigo
    return {"esquema": ESQUEMA_COMPARACION, "implementacion": VERSION_IMPLEMENTACION, "juego": codigo,
            "reglas": instantanea.reglas.como_dict(), "paleta_del_corte": list(instantanea.paleta()),
            "corte": instantanea.corte, "sha256_historico": instantanea.huella(),
            "version_de_variables": lv.VERSION_VARIABLES,
            "candidatos": [{"id": e.id, "version": e.version, "parametros": lm.parametros_de(e, protocolo.perfil)}
                           for e in ce.candidatos_de_comparacion(codigo)]
            + [receta_del_modelo(codigo, ce.ID_ENSEMBLE, protocolo.perfil)],
            "protocolo": protocolo.como_dict(), "transformaciones": _transformaciones(),
            "semilla": lm.SEMILLA, "hilos": lm.HILOS, "entorno": entorno()}


def cuerpo_de_comparacion(instantanea: lv.Instantanea, identidad: dict, evaluacion: dict) -> dict:
    return {"esquema": ESQUEMA_COMPARACION, "clave": huella(identidad), "identidad": identidad,
            "estado_de_uso": ESTADO_DE_USO, "contexto": contexto(), "juego": instantanea.codigo,
            "datos": _datos(instantanea), "historico": _historico(instantanea),
            "nota": ("Informe nuevo de Producto 5: reevalua los candidatos de Producto 4 con el protocolo de "
                     "Producto 5 y anade el modelo combinado. No cambia los experimentos del laboratorio."),
            **evaluacion}


def protocolo_de(artefacto: dict) -> ce.ProtocoloCarteras:
    p = artefacto["identidad"]["protocolo"]
    return ce.ProtocoloCarteras(**{k: p[k] for k in ("bloques", "tamano_bloque", "calentamiento", "minimo_ajuste",
                                                      "bloque_interno", "minimo_evaluables", "perfil", "decimales")})


def comprobar_recetas(artefacto: dict) -> None:
    """Las recetas guardadas siguen en este catalogo con la misma version y
    parametros; si no, no se puede reproducir con este codigo."""
    identidad = artefacto["identidad"]
    juego = artefacto["juego"]
    if identidad["esquema"] == ESQUEMA_COMPARACION:
        perfil = identidad["protocolo"]["perfil"]
        esperado = [{"id": e.id, "version": e.version, "parametros": lm.parametros_de(e, perfil)}
                    for e in ce.candidatos_de_comparacion(juego)] + [receta_del_modelo(juego, ce.ID_ENSEMBLE, perfil)]
        if identidad["candidatos"] != esperado:
            raise ArtefactoCarterasError("las recetas de la comparacion no coinciden con este catalogo")
        return
    modelo = identidad["modelo"]
    if modelo != receta_del_modelo(juego, modelo["id"], identidad["perfil"], modelo.get("registrado")):
        raise ArtefactoCarterasError(f"la receta {modelo['id']} v{modelo['version']} no esta en este catalogo")


def comparar_reproduccion(guardado: dict, recalculado: dict) -> dict:
    exacta = huella(cuerpo_de(guardado)) == huella(recalculado)
    diferencia = 0.0
    a = {c["id"]: {f["objetivo"]: f["log_loss"] for f in c.get("por_objetivo", [])} for c in guardado.get("candidatos", [])}
    b = {c["id"]: {f["objetivo"]: f["log_loss"] for f in c.get("por_objetivo", [])}
         for c in recalculado.get("candidatos", [])}
    for cid, valores in a.items():
        otros = b.get(cid, {})
        if set(valores) != set(otros):
            diferencia = None
            break
        diferencia = max([diferencia, *(abs(valores[o] - otros[o]) for o in valores)])
    return {"huella_exacta": exacta, "maxima_diferencia_de_log_loss": diferencia}


# ---------------------------------------------------------------------------
# Carteras
# ---------------------------------------------------------------------------

def linea_de(juego: str, modelo: str, perfil: str, cantidad: int, diversidad: str, semilla: int,
             registrado: dict | None = None) -> dict:
    receta = receta_del_modelo(juego, modelo, perfil)
    sufijo = "" if perfil == "predeterminado" else f"-{perfil}"
    version = f"{receta['version']}-reg{registrado['numero']}" if registrado else receta["version"]
    linea = {"id": f"{modelo}-v{version}-n{cantidad}-{diversidad}-s{semilla}{sufijo}", "modelo": modelo,
             "version": receta["version"], "perfil": perfil, "cantidad": cantidad, "diversidad": diversidad,
             "semilla": semilla, "juego": juego}
    if registrado:
        linea["registrado"] = {"clave": registrado["clave"], "numero": registrado["numero"]}
    return linea


def identidad_de_cartera(instantanea: lv.Instantanea, modelo: str, perfil: str, cantidad: int, semilla: int,
                         diversidad: str, registrado: dict | None = None) -> dict:
    cantidad, semilla, diversidad = cc.validar_parametros(cantidad, semilla, diversidad)
    reglas = instantanea.reglas
    salida = {"esquema": ESQUEMA_CARTERA, "implementacion": VERSION_IMPLEMENTACION, "juego": instantanea.codigo,
              "reglas": reglas.como_dict(), "paleta_del_corte": list(instantanea.paleta()),
              "corte": instantanea.corte, "objetivo": instantanea.corte + 1, "sha256_historico": instantanea.huella(),
              "version_de_variables": lv.VERSION_VARIABLES, "perfil": perfil,
              "modelo": receta_del_modelo(instantanea.codigo, modelo, perfil, registrado),
              "cartera": {"cantidad": cantidad, "semilla": semilla, "diversidad": diversidad,
                          "limite_de_diversidad": (cc.LIMITE_COINCIDENCIAS_COLORLOTO if reglas.colores
                                                   else cc.LIMITE_NUMEROS_COMPARTIDOS),
                          "presupuesto_de_intentos": cc.PRESUPUESTO_DE_INTENTOS,
                          "version": cc.VERSION_CONSTRUCCION, "algoritmo_rng": cc.ALGORITMO_RNG,
                          "primera_combinacion": ("sugerencia del modelo, salvo un vector fuente constante (entonces "
                                                  "todas las lineas se muestrean)"
                                                  if modelo not in ("uniforme", "uniforme_paleta")
                                                  else "muestreo (la uniforme no tiene sugerencia)")},
              "transformaciones": _transformaciones(), "semilla_de_los_modelos": lm.SEMILLA, "hilos": lm.HILOS,
              "entorno": entorno()}
    if reglas.superbalota:
        salida["superbalota"] = {"estrategia": "frecuencia_con_suavizado_de_laplace", "objetivo_separado": True}
    return salida


def es_uniforme(modelo: str) -> bool:
    return modelo in ("uniforme", "uniforme_paleta")


def cuerpo_de_cartera(instantanea: lv.Instantanea, identidad: dict, fuente: dict) -> dict:
    """Cuerpo reproducible: construye la cartera con el vector fuente."""
    juego = instantanea.codigo
    modelo = identidad["modelo"]["id"]
    parametros = identidad["cartera"]
    informativa = cc.fuente_informativa(fuente)
    con_sugerencia = not es_uniforme(modelo) and informativa
    construccion = cc.construir(fuente, juego, con_sugerencia=con_sugerencia,
                                cantidad=parametros["cantidad"], semilla=parametros["semilla"],
                                diversidad=parametros["diversidad"])
    metricas = cc.metricas_de_cartera(construccion["combinaciones"], juego, fuente)
    return {"esquema": ESQUEMA_CARTERA, "clave_de_entrada": huella(identidad), "identidad": identidad,
            "linea": linea_de(juego, modelo, identidad["perfil"], parametros["cantidad"], parametros["diversidad"],
                              parametros["semilla"], identidad["modelo"].get("registrado")),
            "estado_de_uso": ESTADO_DE_USO, "contexto": contexto(), "juego": juego,
            "modelo": _descripcion_con_registro(juego, modelo, identidad),
            "datos": {"corte": instantanea.corte, "sha256_historico": instantanea.huella(), "sorteos": len(instantanea),
                      "ultima_fecha": instantanea.sorteos[-1].fecha.isoformat(),
                      "paleta_del_corte": list(instantanea.paleta())},
            "historico": _historico(instantanea), "fuente": fuente,
            "cartera": {"objetivo": instantanea.corte + 1, **construccion, "parametros": parametros,
                        "primera_combinacion": ("sugerencia_del_modelo" if con_sugerencia else
                                                "sin_sugerencia_modelo_uniforme" if es_uniforme(modelo) else
                                                "sin_sugerencia_vector_fuente_constante"),
                        "metricas": metricas, "nota": cc.NOTA_CONSTRUCCION,
                        "aviso": ("Una cartera no es un resultado real del sorteo ni una lista de numeros "
                                  "garantizados; no se presenta ninguna probabilidad del premio mayor.")}}


def _descripcion_con_registro(juego: str, modelo: str, identidad: dict) -> dict:
    descripcion = descripcion_del_modelo(juego, modelo, identidad["perfil"])
    registrado = identidad["modelo"].get("registrado")
    return descripcion if registrado is None else {**descripcion, "registrado": registrado}


def comparar_cartera(guardado: dict, recalculado: dict) -> dict:
    exacta = huella(cuerpo_de(guardado)) == huella(recalculado)
    a, b = guardado["fuente"]["probabilidades"], recalculado["fuente"]["probabilidades"]
    misma_lista = guardado["cartera"]["combinaciones"] == recalculado["cartera"]["combinaciones"]
    return {"huella_exacta": exacta, "mismas_combinaciones": misma_lista,
            "maxima_diferencia_de_probabilidad": (max(abs(x - y) for x, y in zip(a, b)) if len(a) == len(b) else None)}


def clasificar_objetivo(juego: str, objetivo: int, disponibles: Sequence) -> dict:
    """Objetivo frente a todo el historico cargado al generar (misma regla y
    nombres que Productos 1-4)."""
    ordenado = sorted(disponibles, key=lambda r: r.numero_sorteo)
    ultimo = ordenado[-1]
    observado = next((r for r in ordenado if r.numero_sorteo == objetivo), None)
    base = {"objetivo": objetivo, "objetivo_en_la_base": observado is not None,
            "ultimo_sorteo_disponible": ultimo.numero_sorteo, "ultima_fecha_disponible": ultimo.fecha.isoformat()}
    if observado is not None:
        return {**base, "tipo": "simulacion_retrospectiva",
                "descripcion": (f"Reconstruccion retrospectiva: el sorteo objetivo {objetivo} ya figura en la base; "
                                "la cartera usa solo datos hasta el corte."),
                "resultado_observado": _resultado(juego, observado)}
    if objetivo > ultimo.numero_sorteo:
        return {**base, "tipo": "pronostico_sobre_el_ultimo_dato_disponible",
                "descripcion": (f"El objetivo {objetivo} es el siguiente al ultimo sorteo cargado "
                                f"({ultimo.numero_sorteo}, {ultimo.fecha.isoformat()}). Esto no prueba que el sorteo "
                                "no se haya celebrado ni que la emision lo precediera."),
                "resultado_observado": None}
    return {**base, "tipo": "objetivo_no_cargado_con_sorteos_posteriores",
            "descripcion": (f"El objetivo {objetivo} no figura en la base, pero hay sorteos posteriores (hasta "
                            f"{ultimo.numero_sorteo}): reconstruccion sobre un hueco, sin resultado para comparar."),
            "resultado_observado": None}


def _resultado(juego: str, r) -> dict:
    if juego == "COLORLOTO":
        return {"pares": sorted([list(p) for p in r.pares])}
    return {"numeros": list(r.numeros), "superbalota": r.superbalota}


# ---------------------------------------------------------------------------
# Simulacion
# ---------------------------------------------------------------------------

def identidad_de_simulacion(elegida: dict, uniforme: dict, simulaciones: int, semilla: int) -> dict:
    simulaciones, semilla = cs.validar(simulaciones, semilla)
    juego = elegida["juego"]
    return {"esquema": ESQUEMA_SIMULACION, "implementacion": VERSION_IMPLEMENTACION, "juego": juego,
            "objetivo": elegida["cartera"]["objetivo"], "corte": elegida["datos"]["corte"],
            "cartera": elegida["clave_de_entrada"], "cartera_uniforme": uniforme["clave_de_entrada"],
            "fuente_sha256": huella(elegida["fuente"]), "simulaciones": simulaciones, "semilla": semilla,
            "escenarios": [cs.supuestos(e, juego) for e in cs.ESCENARIOS], "version": cs.VERSION_SIMULACION,
            "algoritmo_rng": cc.ALGORITMO_RNG + "; flujo 2 = simulacion, un flujo por escenario",
            "controles_exactos": "hipergeometrica y enumeracion del maximo (numeros, sorteos uniformes)",
            "entorno": entorno()}


def _resumen_de_cartera(c: dict) -> dict:
    return {"clave": c["clave_de_entrada"], "modelo": c["modelo"]["id"], "nombre": c["modelo"]["nombre"],
            "linea": c["linea"]["id"], "combinaciones": c["cartera"]["combinaciones"],
            "parametros": c["cartera"]["parametros"]}


def cuerpo_de_simulacion(identidad: dict, elegida: dict, uniforme: dict, avance=None) -> dict:
    juego = elegida["juego"]
    resultados = cs.simular(juego, elegida["fuente"], elegida["cartera"]["combinaciones"],
                            uniforme["cartera"]["combinaciones"], identidad["simulaciones"], identidad["semilla"],
                            avance=avance)
    return {"esquema": ESQUEMA_SIMULACION, "clave": huella(identidad), "identidad": identidad,
            "estado_de_uso": ESTADO_DE_USO, "contexto": contexto(), "juego": juego,
            "objetivo": identidad["objetivo"], "carteras": {"elegida": _resumen_de_cartera(elegida),
                                                            "uniforme": _resumen_de_cartera(uniforme)},
            "fuente": elegida["fuente"], "resultados": resultados,
            "controles_exactos": cs.controles_exactos(juego, elegida["cartera"]["combinaciones"],
                                                      uniforme["cartera"]["combinaciones"]),
            "nota": ("Frecuencias SIMULADAS bajo hipotesis identificadas: cero apariciones en M simulaciones no "
                     "significa imposibilidad. No es una probabilidad real de acertar un sorteo futuro, ni dinero, "
                     "premios o retorno.")}


# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------

def cuerpo_de_configuracion(juego: str, version: int, modelo: str, perfil: str, cantidad: int, diversidad: str,
                            semilla: int, registrado: dict | None = None) -> dict:
    """Fase 3: con `registrado`, la configuracion elige una version registrada
    congelada (la operacion diaria la recarga sin reentrenar). Sin el, el cuerpo
    es identico al de Producto 5."""
    cantidad, semilla, diversidad = cc.validar_parametros(cantidad, semilla, diversidad)
    receta = receta_del_modelo(juego, modelo, perfil)
    elegido = {"id": modelo, "version": receta["version"]}
    if registrado is not None:
        elegido["registrado"] = dict(registrado)
    return {"esquema": ESQUEMA_CONFIGURACION, "juego": juego, "version": version,
            "modelo": elegido, "perfil": perfil, "cantidad": cantidad,
            "diversidad": diversidad, "semilla": semilla,
            "linea": linea_de(juego, modelo, perfil, cantidad, diversidad, semilla, registrado)["id"],
            "nota": ("Configuracion explicita de quien la guardo. No elige el modelo con mejor perdida ni cambia los "
                     "modelos predeterminados de Producto 3.")}


# ---------------------------------------------------------------------------
# Seguimiento observado
# ---------------------------------------------------------------------------

TIPOS = la.TIPOS
NOTA_SEGUIMIENTO = la.NOTA_SEGUIMIENTO


def aciertos_observados(artefacto: dict, r) -> dict:
    juego = artefacto["juego"]
    filas = []
    for c in artefacto["cartera"]["combinaciones"]:
        if juego == "COLORLOTO":
            fila = {"linea": c["linea"], "aciertos": pcl.coincidencias(c["pares"], r.pares)}
        else:
            fila = {"linea": c["linea"], "aciertos": len(set(c["numeros"]) & set(r.numeros))}
            if "superbalota" in c and r.superbalota is not None:
                fila["superbalota"] = c["superbalota"] == r.superbalota
        filas.append(fila)
    maximo = max(f["aciertos"] for f in filas)
    salida = {"por_linea": filas, "maximo": maximo, "lineas": len(filas),
              "definicion": ("coincidencias con multiplicidad de pares (0-6)" if juego == "COLORLOTO" else
                             "numeros principales acertados (0-5); la superbalota aparte")}
    if any("superbalota" in f for f in filas):
        salida["superbalota_en_alguna_linea"] = any(f.get("superbalota") for f in filas)
    return salida


def estado_frente_a_la_base(artefacto: dict, historico_completo: Sequence | None) -> dict:
    """Historico hasta el corte (coincide, cambio, no disponible) y resultado
    del objetivo en la base actual, en lectura."""
    if historico_completo is None:
        return {"estado": "sin_base", "historico_hasta_el_corte": "no_disponible",
                "motivo": "base de datos no disponible"}
    juego = artefacto["juego"]
    corte = artefacto["datos"]["corte"]
    objetivo = artefacto["cartera"]["objetivo"]
    ordenado = sorted(historico_completo, key=lambda r: r.numero_sorteo)
    hasta = [r for r in ordenado if r.numero_sorteo <= corte]
    try:
        actual = lv.validar_instantanea(juego, hasta).huella() if hasta else None
    except lv.HistoricoNoValidoError:
        actual = "no_valido"
    coincide = ("no_disponible" if actual is None else
                "coincide" if actual == artefacto["datos"]["sha256_historico"] else "cambio")
    salida = {"historico_hasta_el_corte": coincide, "ultimo_sorteo_actual": ordenado[-1].numero_sorteo if ordenado
              else None}
    observado = next((r for r in ordenado if r.numero_sorteo == objetivo), None)
    if observado is None:
        if not ordenado or objetivo > ordenado[-1].numero_sorteo:
            return {**salida, "estado": "pendiente",
                    "motivo": f"el sorteo {objetivo} aun no figura en la base"}
        return {**salida, "estado": "no_corresponde",
                "motivo": f"hueco: el sorteo {objetivo} no figura aunque hay sorteos posteriores"}
    return {**salida, "estado": "observado", "fecha": observado.fecha.isoformat(),
            "resultado": _resultado(juego, observado), "aciertos": aciertos_observados(artefacto, observado)}


def seguimiento_de_linea(elementos: list[dict], historico_completo: Sequence | None) -> dict:
    """`elementos`: [{"objetivo", "secuencia", "identificador", "artefacto" | None, "ilegible"}] de UNA linea."""
    por_objetivo: dict = {}
    sin_objetivo = [e for e in elementos if e.get("objetivo") is None]
    for e in elementos:
        if e.get("objetivo") is not None:
            por_objetivo.setdefault(e["objetivo"], []).append(e)
    filas = []
    for objetivo in sorted(por_objetivo):
        grupo = por_objetivo[objetivo]
        legibles = sorted((e for e in grupo if e.get("artefacto") is not None), key=lambda e: e["secuencia"])
        base = {"objetivo": objetivo, "versiones": len(grupo)}
        if any(e.get("ilegible") for e in grupo) or sin_objetivo or not legibles:
            filas.append({**base, "estado": "excluido", "motivo": "orden_ambiguo_por_archivo_ilegible", "tipo": None})
            continue
        primero = legibles[0]
        artefacto = primero["artefacto"]
        clasificacion = (artefacto.get("generacion") or {}).get("clasificacion_temporal") or {}
        tipo = TIPOS.get(clasificacion.get("tipo"), "sin_clasificacion")
        fila = {**base, "identificador": primero["identificador"], "tipo": tipo, "secuencia": primero["secuencia"],
                "generado_en": artefacto["generacion"]["generado_en"],
                "lineas": len(artefacto["cartera"]["combinaciones"])}
        estado = estado_frente_a_la_base(artefacto, historico_completo)
        fila["historico_hasta_el_corte"] = estado["historico_hasta_el_corte"]
        if estado["estado"] != "observado":
            filas.append({**fila, "estado": estado["estado"], "motivo": estado["motivo"]})
            continue
        fila["resultado"] = estado["resultado"]
        if fila["historico_hasta_el_corte"] != "coincide":
            filas.append({**fila, "estado": "excluido",
                          "motivo": "historico_hasta_el_corte_" + fila["historico_hasta_el_corte"]})
            continue
        filas.append({**fila, "estado": "incluido", "aciertos": estado["aciertos"]})
    por_tipo = {}
    for tipo in ("seguimiento", "retrospectiva"):
        de_tipo = [f for f in filas if f["tipo"] == tipo]
        incluidos = [f for f in de_tipo if f["estado"] == "incluido"]
        por_tipo[tipo] = {"objetivos": len(de_tipo), "incluidos": len(incluidos),
                          "pendientes": sum(f["estado"] == "pendiente" for f in de_tipo),
                          "excluidos": sum(f["estado"] == "excluido" for f in de_tipo),
                          "motivos_de_exclusion": dict(Counter(f["motivo"] for f in de_tipo if f["estado"] == "excluido")),
                          "maximos_observados": dict(sorted(Counter(f["aciertos"]["maximo"] for f in incluidos).items()))}
    return {"filas": filas, "por_tipo": por_tipo, "ilegibles_sin_objetivo": len(sin_objetivo), "nota": NOTA_SEGUIMIENTO,
            "politica": ("una cartera por objetivo y linea: la primera segun la secuencia sellada; si no es evaluable "
                         "se excluye sin sustituirla"),
            "aviso": "aciertos observados; no se mezclan con frecuencias simuladas ni con perdidas del modelo"}


def comparacion_entre_lineas(seguimientos: dict[str, dict], tipo: str = "seguimiento") -> dict:
    """Solo objetivos incluidos comunes y lineas con el mismo numero de
    combinaciones; los demas tamanos se muestran aparte."""
    grupos: dict = {}
    for linea, s in seguimientos.items():
        incluidas = {f["objetivo"]: f for f in s["filas"] if f["tipo"] == tipo and f["estado"] == "incluido"}
        if incluidas:
            tamano = next(iter(incluidas.values()))["lineas"]
            grupos.setdefault(tamano, {})[linea] = incluidas
    salida = []
    for tamano, lineas in sorted(grupos.items()):
        comunes = sorted(set.intersection(*(set(v) for v in lineas.values()))) if len(lineas) >= 2 else []
        salida.append({"combinaciones_por_cartera": tamano, "lineas": sorted(lineas), "objetivos_comunes": comunes,
                       "maximos": {linea: [v[o]["aciertos"]["maximo"] for o in comunes] for linea, v in lineas.items()}
                       if comunes else {}})
    return {"tipo": tipo, "grupos": salida,
            "nota": "solo se comparan objetivos incluidos comunes con el mismo numero de combinaciones"}


# ---------------------------------------------------------------------------
# Exportacion
# ---------------------------------------------------------------------------

def _celda(valor) -> str:
    texto = "" if valor is None else str(valor)
    return "'" + texto if texto[:1] in ("=", "+", "-", "@", "\t", "\r") else texto


def csv_de_cartera(artefacto: dict) -> str:
    """CSV UTF-8 de las combinaciones (sin formulas ejecutables)."""
    salida = io.StringIO()
    escritor = csv.writer(salida, lineterminator="\r\n")
    juego = artefacto["juego"]
    cabecera = ["juego", "corte", "objetivo", "modelo", "version_del_modelo", "linea"]
    cabecera += ["pares"] if juego == "COLORLOTO" else ["numeros", "superbalota"]
    cabecera += ["origen", "clave_de_la_cartera"]
    escritor.writerow(cabecera)
    for c in artefacto["cartera"]["combinaciones"]:
        fila = [juego, artefacto["datos"]["corte"], artefacto["cartera"]["objetivo"], artefacto["modelo"]["id"],
                artefacto["modelo"]["version"], c["linea"]]
        if juego == "COLORLOTO":
            fila.append(" ".join(f"{n}:{color}" for n, color in c["pares"]))
        else:
            fila += [" ".join(str(n) for n in c["numeros"]), c.get("superbalota")]
        fila += [c["origen"], artefacto["clave_de_entrada"]]
        escritor.writerow([_celda(v) for v in fila])
    return salida.getvalue()


def csv_de_simulacion(artefacto: dict) -> str:
    """CSV UTF-8 de los conteos SIMULADOS (sin formulas): por escenario y
    cartera, la distribucion del maximo por sorteo y los umbrales «al menos
    k». Son frecuencias bajo hipotesis, no probabilidades reales."""
    salida = io.StringIO()
    escritor = csv.writer(salida, lineterminator="\r\n")
    escritor.writerow(["juego", "objetivo", "escenario", "cartera", "modelo", "medida", "valor", "conteo",
                       "denominador", "frecuencia_simulada", "clave_de_la_simulacion"])
    for escenario in [e for e in cs.ESCENARIOS if e in artefacto["resultados"]]:  # orden declarado, no alfabetico
        r = artefacto["resultados"][escenario]
        for nombre in ("elegida", "uniforme"):
            datos = r["carteras"][nombre]
            modelo = artefacto["carteras"][nombre]["modelo"]
            maximo = datos["maximo_de_la_cartera"]
            filas = [("maximo_de_la_cartera", k, n, maximo["denominador"]) for k, n in enumerate(maximo["conteos"])]
            filas += [("al_menos", k, v["conteo"], v["denominador"]) for k, v in datos["al_menos"].items()]
            if "superbalota" in datos:
                sb = datos["superbalota"]["al_menos_una_linea"]
                filas.append(("superbalota_en_alguna_linea", 1, sb["conteo"], sb["denominador"]))
            for medida, valor, conteo, denominador in filas:
                escritor.writerow([_celda(v) for v in (artefacto["juego"], artefacto["objetivo"], escenario, nombre,
                                                       modelo, medida, valor, conteo, denominador,
                                                       f"{conteo / denominador:.6f}", artefacto["clave"])])
    return salida.getvalue()

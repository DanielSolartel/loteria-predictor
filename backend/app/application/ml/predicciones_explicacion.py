"""
Fase 4: rankings, explicacion y proyeccion de una prediccion. Modulo puro
salvo `importancias_globales`, que recibe un estimador YA cargado (con la
carga restringida de la Fase 3, en el proceso trabajador) y lo lee con
`modelo.valores_globales_por_columna` (este modulo no importa scikit-learn).

LA PREDICCION es una cartera de Producto 5 (vector fuente congelado y sus
combinaciones). Esta capa no entrena, no construye carteras y no evalua: lee
lo que el artefacto ya guarda y anade una EXPLICACION versionada.

RANKINGS (deterministas desde el vector fuente congelado):
- Baloto, Revancha y MiLoto: probabilidad marginal de aparicion de cada
  numero (las marginales suman 5), referencia uniforme 5/N y diferencia.
  `FUERTES` de mayor y `DEBILES` de menor probabilidad (empates por numero).
- Superbalota (Baloto y Revancha): seccion separada; probabilidad de cada
  clase 1..16 (suman 1) frente a 1/16. La estrategia de la superbalota es la
  separada de Producto 1: el modelo de los numeros no la aprende.
- ColorLoto: probabilidad POR BALOTA de cada par numero-color (suman 1 sobre
  el universo de pares de la paleta) frente a 1/pares; multiplicidad
  esperada en las 6 balotas = 6 x p. Aparte, numeros (7) y colores (los de
  la paleta) por SUMA de pares, con sus propios denominadores: nunca se
  inventan 10 numeros en un universo de 7.
«Fuerte» y «debil» describen la CLASIFICACION de ese modelo para ese
objetivo: no son numeros garantizados, causas ni una ventaja acreditada.

EXPLICACION (version `VERSION`):
- metodo: familia, version de la receta, perfil, variables, periodo de
  entrenamiento, transformacion de salida y, si la hay, la version
  registrada; en el modelo combinado, los pesos de la malla elegidos;
- valores de las variables de cada candidato para el objetivo, calculados
  con las funciones causales del motor y SOLO con los sorteos hasta el corte
  guardados en la cartera (sin la base);
- importancias GLOBALES (reduccion de impureza de los bosques) o
  coeficientes (modelos lineales) del estimador PERSISTIDO de una version
  registrada, asociados a sus nombres de variable por la estructura de la
  preparacion de variables. Son globales: no son una atribucion por
  candidato ni una causa. Si el estimador no se conserva (receta reajustada
  al generar) o la familia no las expone, se dice expresamente y no se
  reajusta nada para obtenerlas.

PROYECCION a la tabla `predicciones` del esquema de la Fase 1: solo lectura.
La tabla queda reservada y no se escribe; la fuente canonica es el almacen
inmutable (cartera + explicacion).
"""
from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence

import numpy as np

from app.application.ml import carteras_artefactos as ca
from app.application.ml import carteras_ensemble as ce
from app.application.ml import laboratorio_modelos as lm
from app.application.ml import laboratorio_variables as lv
from app.application.ml import modelos_registrados as mr
from app.application.ml.registro_prospectivo import serializar_entrada

ESQUEMA = "predicciones-explicacion/1"
VERSION = "fase4-explicacion-1"
VOLATILES = ("generacion", "sello")
ESTADO_DE_USO = "experimental_no_acreditado"
FUERTES = DEBILES = 10
EXTREMO_SUPERBALOTA = 4
DECIMALES = 12
RECETAS_DE_FRECUENCIA = ("actual_frecuencia_contraida", "actual_multinomial_suavizada")
AVISO_RANKING = ("«Fuerte» y «débil» describen la clasificación de este modelo para este objetivo. No son números "
                 "garantizados, no indican causas y no acreditan ninguna ventaja frente al azar.")
AVISO_IMPORTANCIAS = ("Importancias y coeficientes son GLOBALES del estimador persistido: describen cuánto usa el "
                      "modelo cada variable en conjunto, no por qué un candidato concreto ocupa su posición ni una "
                      "relación causal. La reducción de impureza favorece variables con muchos valores distintos "
                      "(como la identidad del candidato).")


def huella(objeto) -> str:
    return hashlib.sha256(serializar_entrada(objeto)).hexdigest()


def contexto() -> dict:
    return {"uso": ESTADO_DE_USO, "AUTORIZA_EVALUACION": False, "no_go_ae39": "vigente",
            "resultado_acreditado": False}


def _r(x: float) -> float:
    return round(float(x), DECIMALES)


# ---------------------------------------------------------------------------
# Rankings
# ---------------------------------------------------------------------------

def _filas(etiquetas: Sequence, probabilidades: Sequence[float], uniforme: float, extra=None) -> list[dict]:
    orden = sorted(range(len(etiquetas)), key=lambda i: (-probabilidades[i], str(etiquetas[i])))
    salida = []
    for posicion, i in enumerate(orden, start=1):
        p = probabilidades[i]
        fila = {"posicion": posicion, "candidato": etiquetas[i], "probabilidad": _r(p), "uniforme": _r(uniforme),
                "diferencia": _r(p - uniforme), "razon": _r(p / uniforme) if uniforme > 0 else None}
        if extra is not None:
            fila.update(extra(i, p))
        salida.append(fila)
    return salida


NOTA_EMPATES = ("Hay candidatos con la misma probabilidad emitida en el límite del extremo: entre ellos el orden "
                "sigue el del candidato (desempate fijo) y no expresa ninguna diferencia del modelo.")
NOTA_EMPATES_LISTA = ("Hay candidatos con la misma probabilidad emitida: entre ellos el orden sigue el del candidato "
                      "(desempate fijo) y no expresa ninguna diferencia del modelo.")


def _empates(filas: list[dict]) -> bool:
    return len({f["probabilidad"] for f in filas}) < len(filas)


def _extremos(filas: list[dict], k: int) -> dict:
    k = min(k, len(filas) // 2)
    n = len(filas)
    limite = {"fuertes": k < n and filas[k - 1]["probabilidad"] == filas[k]["probabilidad"],
              "debiles": k < n and filas[n - k]["probabilidad"] == filas[n - k - 1]["probabilidad"]} if k else {
        "fuertes": False, "debiles": False}
    return {"fuertes": filas[:k], "debiles": list(reversed(filas[n - k:])), "universo": n, "por_extremo": k,
            "empate_en_el_limite": limite, "nota_empates": NOTA_EMPATES if any(limite.values()) else None}


def rankings(fuente: dict, juego: str) -> dict:
    """Rankings deterministas del vector fuente congelado de una cartera."""
    reglas = lv.REGLAS[juego]
    candidatos, p = fuente["candidatos"], [float(x) for x in fuente["probabilidades"]]
    salida = {"aviso": AVISO_RANKING, "objetivo": fuente["objetivo"], "corte": fuente["calculado_hasta_sorteo"]}
    if reglas.colores:
        pares = [tuple(c) for c in candidatos]
        balotas = reglas.cantidad
        filas = _filas([list(c) for c in pares], p, 1 / len(pares),
                       lambda i, q: {"multiplicidad_esperada": _r(balotas * q)})
        salida["pares"] = {**_extremos(filas, FUERTES), "todos": filas, "suma": _r(sum(p)),
                           "unidad": "probabilidad por balota del par (suma 1 sobre los pares de la paleta)",
                           "denominador": f"{len(pares)} pares número-color",
                           "nota": "Multiplicidad esperada en las 6 balotas = 6 × probabilidad por balota; no es la "
                                   "probabilidad de que el par aparezca al menos una vez."}
        numeros = sorted({n for n, _ in pares})
        colores = sorted({c for _, c in pares})
        pn = {n: sum(q for (m, _), q in zip(pares, p) if m == n) for n in numeros}
        pc = {c: sum(q for (_, k), q in zip(pares, p) if k == c) for c in colores}
        filas_n = _filas(numeros, [pn[n] for n in numeros], 1 / len(numeros),
                         lambda i, q: {"multiplicidad_esperada": _r(balotas * q)})
        filas_c = _filas(colores, [pc[c] for c in colores], 1 / len(colores),
                         lambda i, q: {"multiplicidad_esperada": _r(balotas * q)})
        salida["numeros"] = {"todos": filas_n, "universo": len(numeros),
                             "nota_empates": NOTA_EMPATES_LISTA if _empates(filas_n)
                             else None,
                             "unidad": "probabilidad por balota del número (suma de sus pares)",
                             "denominador": f"{len(numeros)} números"}
        salida["colores"] = {"todos": filas_c, "universo": len(colores),
                             "nota_empates": NOTA_EMPATES_LISTA if _empates(filas_c)
                             else None,
                             "unidad": "probabilidad por balota del color (suma de sus pares)",
                             "denominador": f"{len(colores)} colores de la paleta del corte"}
        return salida
    masa = fuente.get("masa", reglas.cantidad)
    filas = _filas(list(candidatos), p, masa / len(candidatos))
    salida["numeros"] = {**_extremos(filas, FUERTES), "todos": filas, "suma": _r(sum(p)),
                         "unidad": f"probabilidad marginal de aparición (las marginales suman {masa})",
                         "denominador": f"{len(candidatos)} números; uniforme = {masa}/{len(candidatos)}"}
    sb = fuente.get("superbalota")
    if sb:
        q = [float(x) for x in sb["probabilidades"]]
        filas_sb = _filas(list(sb["candidatos"]), q, 1 / len(q))
        salida["superbalota"] = {**_extremos(filas_sb, EXTREMO_SUPERBALOTA), "todos": filas_sb, "suma": _r(sum(q)),
                                 "unidad": "probabilidad de cada superbalota (suman 1)",
                                 "denominador": f"{len(q)} superbalotas; uniforme = 1/{len(q)}",
                                 "estrategia": sb.get("estrategia"), "nota": sb.get("nota")}
    return salida


def combinaciones(cartera: dict) -> list[dict]:
    """Combinaciones de la cartera con su papel: la sugerencia del modelo
    (los candidatos de mayor probabilidad) o una linea muestreada. A una
    linea muestreada no se le atribuyen las marginales del vector fuente."""
    fuente = cartera["fuente"]
    pares = cartera["juego"] == "COLORLOTO"
    p = {(tuple(c) if pares else c): float(x) for c, x in zip(fuente["candidatos"], fuente["probabilidades"])}
    salida = []
    for c in cartera["cartera"]["combinaciones"]:
        fila = {k: v for k, v in c.items() if k != "origen"}
        if c.get("origen") == "sugerencia_del_modelo":
            fila["papel"] = "sugerencia del modelo"
            fila["detalle"] = ("los candidatos de mayor probabilidad del vector fuente" if not pares else
                               "el multiconjunto más probable de la distribución de pares")
            fila["probabilidades_de_sus_elementos"] = (
                [_r(p[tuple(x)]) for x in c["pares"]] if pares else [_r(p[n]) for n in c["numeros"]])
            fila["unidad_de_los_elementos"] = ("probabilidad por balota de cada par (suma 1 sobre los pares)" if pares
                                               else "probabilidad marginal de aparición de cada número")
            sb = fuente.get("superbalota")
            if sb and c.get("superbalota") is not None:
                q = dict(zip(sb["candidatos"], sb["probabilidades"]))
                fila["probabilidad_de_su_superbalota"] = _r(float(q[c["superbalota"]]))
        else:
            fila["papel"] = "línea muestreada"
            fila["detalle"] = ("muestreo ponderado con semilla y diversidad; sus números no heredan las "
                               "probabilidades marginales del vector fuente")
        salida.append(fila)
    return salida


# ---------------------------------------------------------------------------
# Variables de los candidatos (mismas funciones causales del motor)
# ---------------------------------------------------------------------------

def usa_variables_del_laboratorio(modelo: str) -> bool:
    if modelo == ce.ID_ENSEMBLE:
        return True
    entrada = lm.CATALOGO.get(modelo)
    return entrada is not None and entrada.familia != "uniforme" and modelo not in RECETAS_DE_FRECUENCIA \
        and modelo != "actual_logistica_ae36"


def variables_de_candidatos(instantanea: lv.Instantanea, modelo: str) -> dict:
    """Valores de las variables del objetivo `corte + 1` por candidato, solo
    con los sorteos de la instantanea (hasta el corte)."""
    reglas = instantanea.reglas
    if modelo == "actual_logistica_ae36":
        from app.application.ml.pronostico_experimental import filas_de_inferencia

        nombres = mr._variables(lm.CATALOGO[modelo], False)["nombres"]
        filas = filas_de_inferencia(list(instantanea.sorteos), reglas.codigo, *reglas.rango)
        por_candidato = {str(f.numero_candidato): [_r(getattr(f, n)) for n in nombres] for f in filas}
        return {"version": "ae36", "nombres": list(nombres), "por_candidato": por_candidato,
                "usadas_por_el_modelo": True, "calculado_hasta_sorteo": instantanea.corte,
                "nota": "Variables de la receta de AE-36, calculadas solo con los sorteos hasta el corte."}
    filas = lv.Variables(instantanea).filas([len(instantanea)])
    nombres = list((lv.NOMBRES_VARIABLES_COLORLOTO if reglas.colores else lv.NOMBRES_VARIABLES_NUMEROS)[1:])
    por_candidato = {}
    for c, x in zip(filas.candidatos, filas.X):
        clave = f"{c[0]}|{c[1]}" if reglas.colores else str(c)
        por_candidato[clave] = [_r(v) for v in x[1:]]
    usadas = usa_variables_del_laboratorio(modelo)
    return {"version": lv.VERSION_VARIABLES, "nombres": nombres, "por_candidato": por_candidato,
            "usadas_por_el_modelo": usadas, "calculado_hasta_sorteo": instantanea.corte,
            "nota": ("Variables causales del laboratorio, calculadas solo con los sorteos anteriores al objetivo." if usadas
                     else "Este método no usa estas variables como entradas: se muestran solo como contexto del "
                          "histórico hasta el corte.")}


def clave_de_candidato(candidato) -> str:
    return f"{candidato[0]}|{candidato[1]}" if isinstance(candidato, (list, tuple)) else str(candidato)


# ---------------------------------------------------------------------------
# Importancias globales del estimador persistido (proceso trabajador)
# ---------------------------------------------------------------------------

def no_disponible(motivo: str, **extra) -> dict:
    return {"estado": "no_disponible", "motivo": motivo, **extra}


def importancias_globales(estimador, nombres_de_variables: Sequence[str]) -> dict:
    """Importancias (bosques) o coeficientes (lineales) del estimador ya
    cargado, con el nombre de su variable. Nunca reajusta ni evalua. La
    lectura del estimador esta en `modelo.valores_globales_por_columna` (el
    unico modulo de `application/ml` que importa scikit-learn)."""
    from app.application.ml import modelo as mdl

    leido = mdl.valores_globales_por_columna(estimador, nombres_de_variables)
    if leido.get("motivo"):
        return no_disponible(leido["motivo"], **({"estimador": leido["estimador"]} if leido.get("estimador") else {}))
    clase = leido["estimador"]
    if leido.get("sin_valores"):
        return no_disponible(f"{clase} no expone importancias ni coeficientes; no se calcula una importancia por "
                             "permutación (exigiría volver a evaluar con datos)", estimador=clase)
    columnas, tipo, calibrado = leido["columnas"], leido["tipo"], leido["calibrado"]
    valores = np.asarray(leido["valores"], dtype=float)
    if tipo == "importancia_por_reduccion_de_impureza":
        descripcion = ("Reducción media de impureza aportada por cada variable en los árboles del bosque "
                       "(suma 1). Global, sin signo.")
    elif tipo == "ganancia_total_de_particiones":
        descripcion = ("Ganancia total de las particiones sobre cada variable preparada. Unidades de reducción "
                       "del objetivo del boosting; no está normalizada, no suma 1 y no es un coeficiente lineal. "
                       "Global, sin signo; no atribuye causalidad.")
    else:
        descripcion = ("Coeficientes del modelo lineal sobre las variables ya preparadas (numéricas estandarizadas; "
                       "identidad en One-Hot). Escala de la función de enlace antes de la calibración y de la "
                       "transformación de salida.")
    if len(valores) != len(columnas) or not np.all(np.isfinite(valores)):
        return no_disponible("el número de valores no coincide con el de columnas transformadas", estimador=clase)
    identidad = nombres_de_variables[0]
    por_variable: dict[str, list[float]] = {}
    for (variable, _), v in zip(columnas, valores):
        por_variable.setdefault(variable, []).append(float(v))
    filas = []
    for variable in nombres_de_variables:
        if variable not in por_variable:
            continue
        vs = por_variable[variable]
        if tipo == "coeficiente" and variable == identidad and len(vs) > 1:
            filas.append({"variable": variable, "valor": None, "columnas": len(vs), "es_identidad": True,
                          "resumen": {"minimo": _r(min(vs)), "maximo": _r(max(vs)),
                                      "media_absoluta": _r(sum(abs(x) for x in vs) / len(vs))}})
            continue
        filas.append({"variable": variable, "valor": _r(sum(vs)), "columnas": len(vs), "es_identidad": variable == identidad})
    return {"estado": "disponible", "tipo": tipo, "descripcion": descripcion, "estimador": clase,
            "calibrado": calibrado, "valores": filas, "aviso": AVISO_IMPORTANCIAS}


# ---------------------------------------------------------------------------
# Metodo y cuerpo de la explicacion
# ---------------------------------------------------------------------------

def descripcion_del_metodo(cartera: dict, manifiesto: dict | None) -> dict:
    juego = cartera["juego"]
    linea = cartera["linea"]
    modelo = linea["modelo"]
    colores = juego == "COLORLOTO"
    fuente = cartera["fuente"]
    salida = {"modelo": modelo, "nombre": (cartera.get("modelo") or {}).get("nombre", modelo),
              "version_de_la_receta": str(linea["version"]), "perfil": linea.get("perfil", "predeterminado"),
              "salida": fuente["tipo"], "objetivo": fuente["objetivo"], "corte": fuente["calculado_hasta_sorteo"]}
    if modelo == ce.ID_ENSEMBLE:
        pesos = ((fuente.get("detalle") or {}).get("bloque_interno") or {}).get("numeradores")
        componentes = list(ce.COMPONENTES[juego])
        salida.update(familia="ensemble",
                      variables={"version": lv.VERSION_VARIABLES, "nombres": list(
                          (lv.NOMBRES_VARIABLES_COLORLOTO if colores else lv.NOMBRES_VARIABLES_NUMEROS)),
                          "descripcion": "las de sus componentes del laboratorio"},
                      transformacion={"tipo": "mezcla", "detalle": "media ponderada de las probabilidades de los "
                                      "componentes con pesos de la malla (numerador / 10)"},
                      pesos=None if pesos is None else [{"componente": c, "peso": _r(n / ce.PASOS_DE_MALLA)}
                                                        for c, n in zip(componentes, pesos)],
                      entrenamiento={"estimador": "componentes ajustados al generar la cartera; no se conservan",
                                     "detalle": fuente.get("detalle")})
    else:
        entrada = lm.CATALOGO[modelo]
        salida.update(familia=entrada.familia, tipo=entrada.tipo, variables=mr._variables(entrada, colores),
                      transformacion=mr._transformacion(entrada) if entrada.familia != "uniforme" else
                      {"tipo": "ninguna", "detalle": "probabilidad igual para todos los candidatos"},
                      parametros=lm.parametros_de(entrada, linea.get("perfil", "predeterminado")))
        if manifiesto is not None:
            ident = manifiesto["identidad"]
            salida["entrenamiento"] = {"estimador": "versión registrada congelada: se recargó sin reentrenar",
                                       "corte_de_entrenamiento": ident["corte"], "periodo": ident["periodo"],
                                       "parametros_ajustados": (manifiesto.get("modelo") or {}).get("parametros"),
                                       "detalle": ident["entrenamiento"]}
        else:
            salida["entrenamiento"] = {"estimador": ("ninguno: estrategia de conteos o referencia" if
                                                     entrada.familia == "uniforme" or modelo in RECETAS_DE_FRECUENCIA
                                                     else "ajustado al generar la cartera con todo el histórico hasta "
                                                          "el corte; no se conserva"),
                                       "detalle": (fuente.get("detalle") or {}).get("ajuste_final")}
    registrado = linea.get("registrado")
    if registrado:
        salida["registrado"] = {"clave": registrado["clave"], "numero": registrado["numero"],
                                "corte_de_entrenamiento": None if manifiesto is None else manifiesto["identidad"]["corte"],
                                "sha256_estimador": None if manifiesto is None else manifiesto["estimador"]["sha256"]}
    return salida


def importancias_sin_estimador(cartera: dict) -> dict:
    """Explicacion global cuando no hay un estimador persistido que leer."""
    modelo = cartera["linea"]["modelo"]
    if modelo == ce.ID_ENSEMBLE:
        return no_disponible("el modelo combinado no conserva sus componentes ajustados; su explicación global son los "
                             "pesos de la mezcla (ver método)")
    entrada = lm.CATALOGO.get(modelo)
    if entrada is not None and entrada.familia == "uniforme":
        return no_disponible("no aplica: la referencia uniforme asigna la misma probabilidad a todos los candidatos")
    if modelo in RECETAS_DE_FRECUENCIA:
        return no_disponible("no aplica: la receta cuenta frecuencias suavizadas; no hay un estimador con variables")
    return no_disponible("el estimador de esta cartera se ajustó al generarla y no se conserva (solo las versiones "
                         "registradas de la Fase 3 guardan su estimador); no se reajusta para explicar una predicción "
                         "ya emitida")


def cuerpo_de_explicacion(cartera: dict, importancias: dict, manifiesto: dict | None = None) -> dict:
    juego = cartera["juego"]
    instantanea = ca.instantanea_de(cartera)
    if instantanea.corte != cartera["fuente"]["calculado_hasta_sorteo"]:
        raise ValueError("la instantanea de la cartera no corresponde a su vector fuente")
    return {"esquema": ESQUEMA, "version": VERSION, "juego": juego, "estado_de_uso": ESTADO_DE_USO,
            "contexto": contexto(),
            "cartera": {"clave": cartera["clave_de_entrada"], "linea": cartera["linea"]["id"],
                        "objetivo": cartera["cartera"]["objetivo"], "corte": cartera["datos"]["corte"],
                        "sha256_historico": cartera["datos"]["sha256_historico"],
                        "sha256_fuente": huella(cartera["fuente"])},
            "metodo": descripcion_del_metodo(cartera, manifiesto),
            "rankings": rankings(cartera["fuente"], juego),
            "variables": variables_de_candidatos(instantanea, cartera["linea"]["modelo"]),
            "importancias": importancias,
            "avisos": [AVISO_RANKING, AVISO_IMPORTANCIAS,
                       "Una explicación describe cómo se obtuvo la clasificación con los datos hasta el corte; no "
                       "prueba que el modelo acierte."]}


def componer(cuerpo: dict, generacion: dict) -> dict:
    artefacto = {"clave": huella(cuerpo), **cuerpo, "generacion": generacion}
    return {**artefacto, "sello": huella(artefacto)}


def cuerpo_de(artefacto: dict) -> dict:
    return {k: v for k, v in artefacto.items() if k not in VOLATILES and k != "clave"}


def integro(artefacto: dict) -> bool:
    if artefacto.get("esquema") != ESQUEMA:
        return False
    sin_sello = {k: v for k, v in artefacto.items() if k != "sello"}
    return artefacto.get("sello") == huella(sin_sello) and artefacto.get("clave") == huella(cuerpo_de(artefacto))


def reproducir(artefacto: dict, cartera: dict) -> dict:
    """Recalcula (sin cargar estimadores) rankings y variables con la cartera
    guardada y los compara con la explicacion: deben coincidir exactamente."""
    if artefacto["cartera"]["sha256_fuente"] != huella(cartera["fuente"]):
        return {"exacta": False, "motivo": "el vector fuente de la cartera no es el de la explicación"}
    rk = rankings(cartera["fuente"], cartera["juego"])
    va = variables_de_candidatos(ca.instantanea_de(cartera), cartera["linea"]["modelo"])
    distintos = [n for n, a, b in (("rankings", artefacto["rankings"], rk), ("variables", artefacto["variables"], va))
                 if huella(a) != huella(b)]
    return {"exacta": not distintos, "distintos": distintos,
            "nota": "Las importancias del estimador persistido no se recalculan aquí: se comprueban con la huella "
                    "del artefacto."}


# ---------------------------------------------------------------------------
# Proyeccion a la tabla `predicciones` (solo lectura)
# ---------------------------------------------------------------------------

DECISION_TABLA = ("La tabla `predicciones` de la Fase 1 queda RESERVADA y no se escribe. La fuente canónica de cada "
                  "predicción es el almacén inmutable: la cartera de Producto 5 (vector fuente congelado y "
                  "combinaciones) y su explicación de la Fase 4. Escribir también en PostgreSQL dejaría dos "
                  "registros sin una transacción común; esta proyección muestra sus columnas sin escribirlas.")


def proyeccion_tabla(cartera: dict, explicacion: dict | None) -> dict:
    rk = (explicacion or {}).get("rankings") or rankings(cartera["fuente"], cartera["juego"])
    principal = rk.get("pares") or rk["numeros"]
    linea = cartera["linea"]
    registrado = linea.get("registrado")
    texto = (f"{(cartera.get('modelo') or {}).get('nombre', linea['modelo'])} v{linea['version']}"
             + (f", versión registrada {registrado['numero']}" if registrado else "")
             + f"; corte {cartera['datos']['corte']}, objetivo {cartera['cartera']['objetivo']}; "
             + f"{len(cartera['cartera']['combinaciones'])} combinaciones (semilla {linea['semilla']}, diversidad "
             + f"{linea['diversidad']}).")
    return {"tabla": "predicciones", "escrita": False, "decision": DECISION_TABLA, "columnas": {
        "juego_id": cartera["juego"], "modelo_id": None,
        "modelo": f"{linea['modelo']} v{linea['version']}" + (f" reg{registrado['numero']}" if registrado else ""),
        "fecha_generacion": (cartera.get("generacion") or {}).get("generado_en"),
        "sorteo_objetivo": cartera["cartera"]["objetivo"],
        "combinaciones": [{k: v for k, v in c.items() if k in ("numeros", "superbalota", "pares")}
                          for c in cartera["cartera"]["combinaciones"]],
        "numeros_fuertes": [f["candidato"] for f in principal["fuertes"]],
        "numeros_debiles": [f["candidato"] for f in principal["debiles"]],
        "probabilidades": {clave_de_candidato(f["candidato"]): f["probabilidad"] for f in principal["todos"]},
        "explicacion": texto + (" Explicación guardada " + explicacion["clave"][:12] + "." if explicacion else
                                " Sin explicación guardada todavía."),
        "nivel_confianza": None},
        "notas": {"juego_id": "código del juego; el UUID de la tabla `juegos` no se resuelve sin la base",
                  "modelo_id": "las tablas `modelos` y `metricas_modelo` no se escriben (Fase 3): la versión se "
                                "identifica por su clave",
                  "numeros_fuertes": ("pares número-color en ColorLoto" if lv.REGLAS[cartera["juego"]].colores else
                                      "números principales; la superbalota va aparte"
                                      if lv.REGLAS[cartera["juego"]].superbalota else "números principales"),
                  "nivel_confianza": "vacío a propósito: no se define un número único de confianza; la fiabilidad se "
                                     "presenta como rendimiento observado e incertidumbre por separado"}}


__all__ = ["ESQUEMA", "VERSION", "rankings", "combinaciones", "variables_de_candidatos", "importancias_globales",
           "importancias_sin_estimador", "descripcion_del_metodo", "cuerpo_de_explicacion", "componer", "integro",
           "reproducir", "proyeccion_tabla", "huella", "DECISION_TABLA", "clave_de_candidato"]

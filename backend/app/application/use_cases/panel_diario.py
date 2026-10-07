"""
Panel diario (Producto 3): estado de los cuatro juegos en una consulta de
solo lectura. Nunca sincroniza ni entrena.

Cada juego se construye por separado: un error en uno (base caida,
historico vacio, artefacto alterado) se muestra en su tarjeta sin ocultar
las demas.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import date

from app.application.estadisticas.motor.generales import detectar_huecos_serie_historica
from app.application.estadisticas.resumen_juego import evaluar_frescura
from app.application.interfaces.pronostico_experimental_store import PronosticoGuardado
from app.application.ml.resultados_observados import comparar_con_resultado
from app.application.use_cases.operacion_diaria import mensaje_legible, ultima_por_juego
from app.application.use_cases.pronostico_experimental import JUEGOS, ConsultarPronosticosExperimentales, _historicos

NOMBRES = {"BALOTO": "Baloto", "BALOTO_REVANCHA": "Baloto Revancha", "MILOTO": "MiLoto", "COLORLOTO": "ColorLoto"}
SLUGS = {"BALOTO": "baloto", "BALOTO_REVANCHA": "baloto-revancha", "MILOTO": "miloto", "COLORLOTO": "colorloto"}


def sugerencia(artefacto: dict) -> dict:
    p = artefacto["pronostico"]
    if "pares" in p:
        return {"pares": [[f["numero"], f["color"]] for f in p["pares"]]}
    sb = artefacto.get("superbalota")
    return {"numeros": list(p["numeros_sugeridos"]), "superbalota": sb["pronostico"]["sugerida"] if sb else None}


class ConsultarPanelDiario:
    def __init__(self, almacen, juego_repository, resultados_repository, operacion,
                 hoy: Callable[[], date] = date.today):
        self._almacen = almacen
        self._juegos = juego_repository
        self._resultados = resultados_repository
        self._operacion = operacion
        self._hoy = hoy

    def ejecutar(self) -> dict:
        try:
            recientes = self._operacion.recientes(50)
        except Exception as error:  # registro ilegible: el panel sigue
            recientes, aviso = [], mensaje_legible(error)
        else:
            aviso = None
        return {"juegos": [self._tarjeta(c, recientes) for c in JUEGOS],
                "ejecuciones_recientes": recientes[:10], "aviso_registro": aviso}

    def _tarjeta(self, codigo: str, recientes: list[dict]) -> dict:
        t = {"codigo": codigo, "nombre": NOMBRES[codigo], "slug": SLUGS[codigo], "estado": "ok", "atencion": [],
             "historico": None, "pronostico": None, "observado": None, "ultima_ejecucion": None,
             "activa": None, "ilegibles": 0, "temporales": 0, "error": None}
        try:
            t["activa"] = self._operacion.activa(codigo)
            ejecucion, resultado = ultima_por_juego(recientes, codigo)
            if ejecucion is not None:
                t["ultima_ejecucion"] = {"id": ejecucion["id"], "estado": ejecucion["estado"], "modo": ejecucion["modo"],
                                         "iniciada_en": ejecucion["iniciada_en"], "resultado": resultado}
                if resultado.get("estado") in ("fallo", "interrumpido") or ejecucion["estado"] == "interrumpida":
                    t["atencion"].append(resultado.get("mensaje") or "La ultima ejecucion no termino bien.")
                elif resultado.get("estado") == "datos_insuficientes":
                    t["atencion"].append(resultado.get("mensaje") or "Datos insuficientes.")
            consultar = ConsultarPronosticosExperimentales(self._almacen, self._juegos, self._resultados)
            resumen = consultar.resumen(codigo)
            t["ilegibles"] = len(resumen.ilegibles)
            t["temporales"] = len(getattr(self._almacen, "temporales", lambda _c: [])(codigo))
            if resumen.ilegibles:
                t["atencion"].append(f"{len(resumen.ilegibles)} artefacto(s) alterado(s) o ilegible(s) en el almacen.")
            try:
                _, completo = _historicos(self._juegos, self._resultados, codigo, None)
            except Exception as error:
                completo = None
                t["error"] = f"No se pudo leer el historico: {mensaje_legible(error)}"
            if completo is not None:
                ordenado = sorted(completo, key=lambda r: r.numero_sorteo)
                ultimo = ordenado[-1] if ordenado else None
                huecos = detectar_huecos_serie_historica([r.numero_sorteo for r in ordenado])
                t["historico"] = {"sorteos": len(ordenado), "ultimo_sorteo": ultimo.numero_sorteo if ultimo else None,
                                  "fecha": ultimo.fecha.isoformat() if ultimo else None,
                                  "frescura": evaluar_frescura(ultimo.fecha if ultimo else None, self._hoy()),
                                  "huecos": len(huecos.huecos), "cobertura": round(huecos.porcentaje_cobertura, 1)}
                if not ordenado:
                    t["atencion"].append("No hay sorteos cargados para este juego.")
                elif t["historico"]["frescura"]["estado"] == "desactualizado":
                    t["atencion"].append("Historico desactualizado: conviene «Actualizar datos y generar».")
            ultimo_pronostico = resumen.ultimo if isinstance(resumen.ultimo, PronosticoGuardado) else None
            if ultimo_pronostico is not None:
                a = ultimo_pronostico.artefacto
                t["pronostico"] = {"objetivo": a["pronostico"]["objetivo"], "corte": a["datos"]["corte"],
                                   "identificador": ultimo_pronostico.identificador,
                                   "version": ultimo_pronostico.version, "versiones": ultimo_pronostico.versiones,
                                   "generado_en": a["generacion"]["generado_en"], **sugerencia(a)}
                if completo is not None:
                    t["observado"] = comparar_con_resultado(a, completo)
                    if t["historico"] and t["historico"]["ultimo_sorteo"] and \
                            t["historico"]["ultimo_sorteo"] >= a["pronostico"]["objetivo"]:
                        t["atencion"].append("Hay un sorteo posterior al corte del ultimo pronostico: conviene "
                                             "generar el siguiente.")
        except Exception as error:  # una tarjeta con error no oculta las demas
            t["error"] = mensaje_legible(error)
        if t["error"]:
            t["estado"] = "error"
        elif t["activa"]:
            t["estado"] = "en_curso"
        elif t["atencion"]:
            t["estado"] = "atencion"
        return t

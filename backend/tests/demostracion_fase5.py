"""Demostración sintética de la Fase 5 (estadísticas descriptivas) en los cuatro juegos.

Recorre la aplicación real (rutas web y API) con históricos SINTÉTICOS de tamaño parecido al real:
panel de cada juego -> cada métrica nueva en pantalla y en JSON con los mismos valores -> corte
aplicado antes de calcular -> superbalota aparte -> multiplicidades de ColorLoto -> periodo sin sorteos
-> lo que no aplica responde 404 con motivo -> nada se escribe en la base.

Sin PostgreSQL ni Internet. Ninguna cifra corresponde a sorteos reales.

Uso (desde `backend`):

  python -m tests.demostracion_fase5

Sale con 0 si cada paso da lo esperado y con 1 si alguno no.
"""
from __future__ import annotations

import sys
import tempfile
from datetime import date, timedelta

from app.api import dependencies as dep
from app.api.web.navegacion_descriptivas import reglas_estaticas
from app.application.estadisticas import descriptivas as de
from app.application.use_cases.consultar_estadisticas_descriptivas import ConsultarEstadisticasDescriptivas
from app.infrastructure.storage.pronostico_experimental_file_store import PronosticoExperimentalFileStore
from tests.unit import fixtures_producto1 as fx

JUEGOS = {"baloto": "BALOTO", "baloto-revancha": "BALOTO_REVANCHA", "miloto": "MILOTO", "colorloto": "COLORLOTO"}


def _paso(numero: int, texto: str, correcto: bool) -> bool:
    print(f"[{'OK' if correcto else 'FALLO'}] {numero}. {texto}", flush=True)
    return correcto


def main() -> int:
    hoy = date.today()
    historicos = {"BALOTO": fx.historico_numerico("BALOTO", 639, inicio=hoy - timedelta(days=3 * 638 + 2)),
                  "BALOTO_REVANCHA": fx.historico_numerico("BALOTO_REVANCHA", 639, inicio=hoy - timedelta(days=3 * 638 + 2)),
                  "MILOTO": fx.historico_numerico("MILOTO", 89, primero=532, inicio=hoy - timedelta(days=3 * 88 + 1))}
    colorloto = fx.historico_colorloto(225, inicio=hoy - timedelta(days=3 * 224 + 1))
    juegos, resultados_repo, colores = fx.repositorios(historicos, colorloto=colorloto)
    with tempfile.TemporaryDirectory(prefix="f5-") as tmp:
        c = fx.cliente(juegos, resultados_repo, colores, PronosticoExperimentalFileStore(tmp))
        from app.main import app

        escrituras = []
        app.dependency_overrides[dep.get_consultar_estadisticas_descriptivas] = (
            lambda: ConsultarEstadisticasDescriptivas(juegos, resultados_repo, colores))
        app.dependency_overrides[dep.get_calcular_y_persistir_estadistica] = lambda: escrituras.append(1)
        resultados = []
        try:
            paneles = {s: c.get(f"/estadisticas/{s}/panel") for s in JUEGOS}
            api = {s: c.get(f"/api/estadisticas/{j}/panel").json() for s, j in JUEGOS.items()}
            total = sum(len(g["metricas"]) for a in api.values() for g in a["grupos"])
            resultados.append(_paso(1, f"Panel de los cuatro juegos ({total} entradas, con las que no aplican y su motivo)",
                                    all(r.status_code == 200 for r in paneles.values())))
            print("    Muestra de cada panel:", ", ".join(f"{s} {api[s]['muestra']['total_sorteos']} sorteos"
                                                     for s in JUEGOS))

            ok, n = True, 0
            for s, j in JUEGOS.items():
                for m in de.metricas_nuevas(reglas_estaticas(s)):
                    pagina = c.get(f"/estadisticas/{s}/{m.slug}")
                    datos = c.get(f"/api/estadisticas/{j}/descriptivas/{m.slug}").json()
                    n += 1
                    ok &= pagina.status_code == 200 and datos["metrica"]["estado"] == "ok" and m.titulo in pagina.text
            resultados.append(_paso(2, f"{n} páginas nuevas (18 Baloto, 18 Revancha, 11 MiLoto, 5 ColorLoto) en pantalla "
                                       "y en JSON", ok and n == 52))

            corte = c.get("/api/estadisticas/BALOTO/descriptivas/distribucion-sumas?hasta_numero_sorteo=2300").json()
            hist = next(t for t in corte["metrica"]["tablas"] if t["id"] == "histograma")
            resultados.append(_paso(3, f"Corte 2300 antes de calcular: {corte['muestra']['total_sorteos']} sorteos en la "
                                       "muestra y en el histograma",
                                    corte["muestra"]["periodo"]["ultimo_sorteo"] == 2300
                                    and sum(f["sorteos"] for f in hist["filas"]) == corte["muestra"]["total_sorteos"] == 220))

            unif = c.get("/api/estadisticas/BALOTO/descriptivas/pruebas-uniformidad").json()["metrica"]
            resumen = next(t for t in unif["tablas"] if t["id"] == "resumen")["filas"]
            print("    Uniformidad Baloto (chi²): " + "; ".join(
                f"{f['valor']} χ²={f['estadistico']:.2f} gl={f['grados_libertad']} p={f['p_value']:.4f}" for f in resumen))
            resultados.append(_paso(4, "Superbalota aparte de los números (uniformidad con 42 y 15 grados de libertad)",
                                    [f["grados_libertad"] for f in resumen] == [42, 15]))

            cl = c.get("/api/estadisticas/COLORLOTO/descriptivas/frecuencia-numeros-por-anio").json()["metrica"]
            filas = next(t for t in cl["tablas"] if t["id"] == "frecuencia")["filas"]
            sorteos = next(i["valor"] for i in cl["indicadores"] if i["etiqueta"] == "Sorteos en el periodo")
            resultados.append(_paso(5, f"ColorLoto cuenta balotas con repetición: {sum(f['apariciones'] for f in filas)} "
                                       f"balotas en {sorteos} sorteos de {cl['selector']['etiqueta']}",
                                    sum(f["apariciones"] for f in filas) == 6 * sorteos))

            vacio = c.get("/estadisticas/miloto/frecuencia-numeros-por-anio?anio=1999")
            resultados.append(_paso(6, "Un año sin sorteos se dice como tal (sin ceros inventados)",
                                    vacio.status_code == 200 and "No hay sorteos en 1999" in vacio.text))

            no_aplica = [c.get(u) for u in ("/estadisticas/miloto/atrasos-superbalota",
                                            "/estadisticas/colorloto/distribucion-decenas",
                                            "/estadisticas/colorloto/independencia-pares")]
            resultados.append(_paso(7, "Lo que no aplica responde 404 con su motivo (superbalota en MiLoto; decenas e "
                                       "independencia en ColorLoto)",
                                    all(r.status_code == 404 and r.json()["detail"] for r in no_aplica)))

            corr = c.get("/api/estadisticas/MILOTO/descriptivas/correlaciones").json()["metrica"]
            print("    Correlaciones MiLoto: " + "; ".join(
                f"{i['etiqueta']}={i['valor']:.3f}" for i in corr["indicadores"] if i["formato"] == "dec3"))
            resultados.append(_paso(8, "Nada se escribió en la base (sin caché de estadísticas)", not escrituras))
        finally:
            app.dependency_overrides = {}
    print("Datos sintéticos: ninguna cifra corresponde a sorteos reales. Las estadísticas son descriptivas; "
          "los pronósticos siguen experimental_no_acreditado y AUTORIZA_EVALUACION = False.")
    return 0 if all(resultados) else 1


if __name__ == "__main__":
    sys.exit(main())

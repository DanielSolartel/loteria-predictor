"""Fase 10 (E10.2): prepara una publicacion SINTETICA para la consulta privada (no es una prueba de pytest).

Antes de montar nada de solo lectura, y con escritura:
1. genera los almacenes de consulta con los productores REALES (laboratorio, modelos registrados con su
   estimador `.pkl`, carteras de Producto 5, predicciones y explicaciones de la Fase 4) sobre historicos
   sinteticos (`tests.fase94_api_sintetica`, estado `normal`);
2. guarda ESOS MISMOS historicos en un PostgreSQL DE PRUEBAS (`fixture_sintetica`) y publica una simulacion
   sintetica, para que la API, con su cableado predeterminado, lea base y almacenes coherentes;
   v2 (F1023-DAT-01): sobre ESE MISMO historico emite tambien con los productores reales las otras dos
   procedencias de Producto 6: la operacion diaria de Producto 3 (`storage/pronosticos`) y los pronosticos
   del laboratorio (`laboratorio/pronosticos`); despues llega el sorteo objetivo de esas emisiones, de modo
   que las tres procedencias (operacion, laboratorio y carteras) tienen emisiones y resultados observados;
3. copia a `<salida>/publicacion/` solo la clase «datos de consulta» de la matriz de datos (v2, 2.5):
   `laboratorio/{modelos,experimentos,pronosticos}`, `carteras/{carteras,configuraciones}`,
   `predicciones` y `pronosticos`, sin `operacion/`, temporales ni nada fuera de `<salida>`;
4. escribe `manifiesto-publicacion.json` (SHA-256 de cada archivo publicado) y `esperado-consultas.json`: lo
   que las consultas DEBEN devolver por juego (procedencias con sus emisiones y lineas, claves de modelos y de
   carteras), calculado con los mismos casos de uso en memoria antes de publicar. Una API que lea un almacen
   vacio o mal apuntado no coincide con ello aunque responda 200.

En la base desechable adelanta `vigente_desde` de la paleta sembrada de ColorLoto al 2024-08-01: los
sorteos sinteticos empiezan el 2024-08-06 y la paleta sembrada el 2024-08-15 (el caso A2 de
`postgres_fase8.py`). Es un ajuste de los datos SINTETICOS, nunca de una base operativa.

Se niega a correr si `DATABASE_URL` no apunta a una base con «prueba» en el nombre o si contiene sorteos que
no sean sinteticos. No imprime la URL ni secretos.

Uso (desde `backend/`, con el rol PROPIETARIO de la base de pruebas y la base ya migrada):
    python -m tests.e102_preparar_publicacion --salida <carpeta nueva>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

JUEGOS = ("BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO")
PUBLICAR = {"laboratorio": ("modelos", "experimentos", "pronosticos"), "carteras": ("carteras", "configuraciones"),
            "predicciones": None, "pronosticos": None}
PROCEDENCIAS = ("operacion", "laboratorio", "carteras")


def _emitir_operacion_y_laboratorio(e4) -> None:
    """Productores REALES de Producto 3 (operacion diaria) y del laboratorio sobre los repositorios de `e4`."""
    from app.application.ml import laboratorio_evaluacion as le
    from app.infrastructure.storage.pronostico_experimental_file_store import PronosticoExperimentalFileStore
    from tests.unit import fixtures_producto1 as fx1
    from tests.unit import fixtures_producto3 as fp3
    from tests.unit import fixtures_producto6 as fp6

    _, _, colores = fx1.repositorios({}, colorloto=[])
    historicos = {j: e4.cargados(j) for j in JUEGOS}
    operacion = fp3.Entorno(e4.juegos, e4.resultados, colores, PronosticoExperimentalFileStore(e4.raiz / "pronosticos"),
                            historicos, e4.raiz / "operacion-producto3")
    operacion.operacion().ejecutar_ahora(list(JUEGOS), "local", "prueba-e102")
    laboratorio = e4.laboratorio()
    for juego in JUEGOS:
        r = laboratorio.comparar_ahora([juego], le.Protocolo(bloques=1, perfil="reducido"))["juegos"][juego]
        laboratorio.generar(r["experimento"], fp6.MODELO_LABORATORIO[juego])
    for juego in JUEGOS:  # llega el sorteo objetivo de esas emisiones (y de la ultima cartera)
        e4.anadir(juego, e4.siguiente(juego, semilla=77))


def esperado(guardados, datos) -> dict:
    """Vista esperada de cada juego, con los MISMOS casos de uso que leera la API."""
    salida = {}
    for juego in JUEGOS:
        r = guardados.resultados(juego, None, None, "seguimiento", None, None, None, 1, 100)
        salida[juego] = {
            "procedencias": {n: {k: p[k] for k in ("estado", "lineas", "emisiones", "ilegibles")}
                             for n, p in r["procedencias"].items()},
            "lineas": sorted(l["clave"] for l in r["lineas"]),
            "por_procedencia": {n: sum(1 for l in r["lineas"] if l.get("procedencia") == n) for n in PROCEDENCIAS},
            "resumenes": {c: {"objetivos": s["objetivos"], "incluidos": s["incluidos"], "pendientes": s["pendientes"],
                              "aciertos": (s.get("aciertos") or {}).get("suma")} for c, s in r["resumenes"].items()},
            "modelos": sorted(m.identificador for m in datos["modelos"][juego]),
            "carteras": sorted(c.identificador for c in datos["carteras"][juego]),
        }
        observadas = {l["procedencia"] for l in r["lineas"] if r["resumenes"][l["clave"]]["incluidos"] > 0}
        faltan = [n for n in PROCEDENCIAS if not r["procedencias"][n]["emisiones"] or n not in observadas]
        if faltan:
            raise SystemExit(f"preparacion incompleta: {juego} sin emisiones o sin resultado observado en {faltan}")
    return salida
EXCLUIR = ("operacion",)


def _negarse(motivo: str) -> int:
    sys.stderr.write(f"NEGADO: {motivo}\n")
    return 2


def _copiar(origen: Path, destino: Path) -> None:
    def ignorar(_carpeta, nombres):
        return [n for n in nombres if n in EXCLUIR or n.startswith(".publicacion.") or n.endswith(".tmp")]
    shutil.copytree(origen, destino, ignore=ignorar)


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", required=True)
    args = p.parse_args(argv)
    salida = Path(args.salida)
    if salida.exists():
        return _negarse("la salida debe ser una carpeta nueva")
    salida.mkdir(parents=True)
    trabajo = Path(tempfile.mkdtemp(prefix="e102-trabajo-", dir=salida))
    for nombre in ("PRONOSTICOS_EXPERIMENTALES", "OPERACION", "LABORATORIO_MODELOS", "CARTERAS_MODELOS",
                   "RESULTADOS_MODELOS", "PREDICCIONES_MODELOS", "AUTOMATIZACION", "SIMULACIONES"):
        os.environ[f"DIRECTORIO_{nombre}"] = str(trabajo / "sin_publicar" / nombre.lower())

    from sqlalchemy import text

    from app.core.config import get_settings
    get_settings.cache_clear()
    from app.infrastructure.db import session as dbs

    if "prueba" not in (dbs.engine.url.database or "") or dbs.engine.dialect.name != "postgresql":
        return _negarse("DATABASE_URL debe apuntar a un PostgreSQL de pruebas (nombre con 'prueba')")
    with dbs.SessionLocal() as s:
        if s.execute(text("SELECT count(*) FROM sorteos")).scalar_one():
            return _negarse("la base de pruebas ya tiene sorteos: use una base nueva")

    from tests import fase94_api_sintetica as f94
    from tests.unit.simulaciones import fixtures_fase7 as f7

    datos = f94.preparar(trabajo / "generacion", estado="normal")
    e4 = datos["e4"]
    _emitir_operacion_y_laboratorio(e4)
    vista_esperada = esperado(datos["guardados"], datos)
    with dbs.SessionLocal() as s:
        s.execute(text("UPDATE colores SET vigente_desde = DATE '2024-08-01' WHERE vigente_desde = DATE '2024-08-15' "
                       "AND juego_id = (SELECT id FROM juegos WHERE codigo = 'COLORLOTO')"))
        for codigo in JUEGOS:
            f7.guardar_sorteos(s, codigo, e4.cargados(codigo))
        s.commit()
    from app.api import dependencies as dep
    dep.get_simulaciones().ahora("MILOTO", 100, 20261024, origen="prueba_e102")  # una fila sintetica que leer

    publicacion = salida / "publicacion"
    publicacion.mkdir()
    raiz = e4.raiz
    for almacen, partes in PUBLICAR.items():
        if partes is None:
            _copiar(raiz / almacen, publicacion / almacen)
            continue
        (publicacion / almacen).mkdir()
        for parte in partes:
            if (raiz / almacen / parte).is_dir():
                _copiar(raiz / almacen / parte, publicacion / almacen / parte)
    archivos = {p.relative_to(publicacion).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(publicacion.rglob("*")) if p.is_file()}
    with dbs.SessionLocal() as s:
        sorteos = {c: s.execute(text("SELECT count(*) FROM sorteos so JOIN juegos j ON j.id = so.juego_id "
                                     "WHERE j.codigo = :c"), {"c": c}).scalar_one() for c in JUEGOS}
        simulaciones = s.execute(text("SELECT count(*) FROM simulaciones")).scalar_one()
    resumen = {"escenario": "e102-publicacion-sintetica/2", "procedencias": {j: {n: v["procedencias"][n]["emisiones"] for n in PROCEDENCIAS} for j, v in vista_esperada.items()}, "sorteos": sorteos, "simulaciones": simulaciones,
               "modelos": {j: [m.identificador for m in datos["modelos"][j]] for j in JUEGOS},
               "carteras": {j: len(datos["carteras"][j]) for j in JUEGOS},
               "almacenes": sorted({k.split("/")[0] for k in archivos} | {"pronosticos"}),
               "archivos": len(archivos), "estimadores_pkl": sum(1 for k in archivos if k.endswith(".pkl")),
               "huellas": archivos}
    (salida / "esperado-consultas.json").write_text(json.dumps(vista_esperada, ensure_ascii=False, indent=1),
                                                    encoding="utf-8")
    (salida / "manifiesto-publicacion.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1),
                                                        encoding="utf-8")
    print(json.dumps({k: v for k, v in resumen.items() if k != "huellas"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

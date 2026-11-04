"""Coherencia cruzada de una captura (E10.4; F10-CAP-02 y requisito 4 de la enmienda 01).

Se recorren los almacenes publicables con SUS PROPIOS lectores (los mismos que usa la API: bytes canonicos,
sello, huella, clave, ubicacion y, en los modelos, los bytes del estimador `.pkl` rehasheados SIN
deserializarlos). Cada `Ilegible` se cuenta y se conserva tal cual: la captura no elimina ni filtra nada.

Para cada artefacto valido se comprueba lo que declara su contrato:
- HISTORICO DE ENTRADA (`datos.corte`, `datos.sha256_historico`, `datos.sorteos`; en las explicaciones, los
  de su cartera): el sorteo `corte` debe figurar en la instantanea de su juego y la instantanea debe tener al
  menos los sorteos hasta el corte que el artefacto declara haber usado. Si no, el artefacto exige sorteos
  ausentes de la captura: RECHAZO de la captura entera (C8), nunca un filtrado (C9). Si estan, se registra el
  mismo estado que muestra la aplicacion: `coincide`, `cambio` o `no_valido` (huella recalculada con la
  funcion del propio productor); un `cambio` es un estado legitimo de la aplicacion y se publica.
- OBJETIVO: se registra y NUNCA se limita por el ultimo sorteo (`objetivo = corte + 1` es el caso normal, C7).
- REFERENCIAS: explicacion -> su cartera (y la misma huella de historico); cartera -> su modelo registrado;
  pronostico del laboratorio y modelo registrado -> su experimento; modelo -> su estimador (lo comprueba su
  lector). Una referencia ausente o ilegible: RECHAZO.
"""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from pathlib import Path

_JUEGO = re.compile(r"^[A-Z][A-Z_]{1,29}$")
Historico = Callable[[str], list | None]


def _id(guardado) -> str:
    return getattr(guardado, "identificador", None) or guardado.clave


def _juegos(raiz: Path, adicionales) -> list[str]:
    nombres = set(adicionales)
    for carpeta in (raiz / "pronosticos", raiz / "laboratorio" / "experimentos", raiz / "laboratorio" / "pronosticos",
                    raiz / "laboratorio" / "modelos", raiz / "carteras" / "carteras", raiz / "carteras" / "comparaciones",
                    raiz / "carteras" / "simulaciones", raiz / "carteras" / "configuraciones",
                    raiz / "predicciones" / "explicaciones"):
        if carpeta.is_dir():
            nombres |= {p.name for p in carpeta.iterdir() if p.is_dir() and _JUEGO.fullmatch(p.name)}
    return sorted(nombres)


def _huella(familia: str, juego: str, hasta: list) -> str:
    from app.application.ml import laboratorio_variables as lv
    from app.application.ml import pronostico_colorloto as colorloto
    from app.application.ml.pronostico_experimental import huella_del_historico

    if familia == "pronostico_experimental":
        return colorloto.huella_del_historico(hasta) if juego == "COLORLOTO" else huella_del_historico(hasta)
    try:
        return lv.validar_instantanea(juego, hasta).huella()
    except lv.HistoricoNoValidoError:
        return "no_valido"


def _entrada_declarada(familia: str, a: dict) -> tuple[int, str, int | None] | None:
    if familia == "explicacion":
        c = a.get("cartera") or {}
        return (int(c["corte"]), c["sha256_historico"], None) if "corte" in c else None
    datos = a.get("datos") if isinstance(a.get("datos"), dict) and "corte" in a["datos"] else a.get("identidad")
    if not isinstance(datos, dict) or "corte" not in datos or "sha256_historico" not in datos:
        return None
    sorteos = datos.get("sorteos")
    return int(datos["corte"]), datos["sha256_historico"], int(sorteos) if isinstance(sorteos, int) else None


def _objetivo(a: dict):
    for camino in (("cartera", "objetivo"), ("pronostico", "objetivo"), ("cartera", "objetivo")):
        v = a
        for k in camino:
            v = v.get(k) if isinstance(v, dict) else None
        if isinstance(v, int):
            return v
    return None


def evaluar(raiz: Path, historico: Historico, juegos_de_la_base=()) -> dict:
    """`raiz` contiene `pronosticos/`, `laboratorio/`, `carteras/` y `predicciones/` (las copias de la captura o
    la generacion importada). `historico(juego)` devuelve los sorteos de la instantanea (o None si el juego no
    esta en la base). Devuelve el informe; `rechazos` vacio = coherente."""
    from app.infrastructure.storage.carteras_file_store import CarterasFileStore, Guardado as GC
    from app.infrastructure.storage.laboratorio_file_store import LaboratorioFileStore
    from app.application.interfaces.laboratorio_store import GuardadoLaboratorio, GuardadoModelo
    from app.infrastructure.storage.predicciones_file_store import PrediccionesFileStore
    from app.infrastructure.storage.pronostico_experimental_file_store import PronosticoExperimentalFileStore

    lab = LaboratorioFileStore(raiz / "laboratorio")
    car = CarterasFileStore(raiz / "carteras")
    pre = PrediccionesFileStore(raiz / "predicciones")
    pro = PronosticoExperimentalFileStore(raiz / "pronosticos")
    ilegibles, artefactos, rechazos = Counter(), [], []
    cache: dict[str, list | None] = {}

    def sorteos(juego):
        if juego not in cache:
            filas = historico(juego)
            cache[juego] = None if filas is None else sorted(filas, key=lambda r: r.numero_sorteo)
        return cache[juego]

    def validos(almacen, juego, elementos, valido_tipo):
        salida = []
        for e in elementos:
            if isinstance(e, valido_tipo):
                salida.append(e)
            else:
                ilegibles[f"{almacen}:{juego}:{getattr(e, 'motivo', 'ilegible')}"] += 1
        return salida

    juegos = _juegos(raiz, juegos_de_la_base)
    por_familia: dict[str, dict[str, list]] = {}
    for juego in juegos:
        f = por_familia.setdefault(juego, {})
        f["pronostico_experimental"] = validos("pronosticos", juego, pro.listar(juego), _tipo_pronostico())
        f["experimento"] = validos("laboratorio/experimentos", juego, lab.experimentos(juego), GuardadoLaboratorio)
        f["pronostico_laboratorio"] = [g for linea in lab.lineas(juego) for g in validos(
            "laboratorio/pronosticos", juego, lab.pronosticos(juego, linea), GuardadoLaboratorio)]
        f["modelo"] = validos("laboratorio/modelos", juego, lab.modelos(juego), GuardadoModelo)
        f["cartera"] = [g for linea in car.lineas(juego) for g in validos("carteras/carteras", juego,
                                                                          car.carteras(juego, linea), GC)]
        f["comparacion"] = validos("carteras/comparaciones", juego, car.comparaciones(juego), GC)
        f["simulacion_cartera"] = validos("carteras/simulaciones", juego, car.simulaciones(juego), GC)
        f["configuracion"] = validos("carteras/configuraciones", juego, car.configuraciones(juego), GC)
        f["explicacion"] = validos("predicciones", juego, pre.listar(juego), _tipo_explicacion())

    for juego, familias in por_familia.items():
        claves = {n: {_id(g) for g in gs} for n, gs in familias.items()}
        carteras = {_id(g): g.artefacto for g in familias["cartera"]}
        filas = sorteos(juego)
        for familia, guardados in familias.items():
            for g in guardados:
                a = g.artefacto
                ficha = {"familia": familia, "juego": juego, "clave": _id(g), "objetivo": _objetivo(a)}
                declarada = _entrada_declarada(familia, a)
                if declarada is not None:
                    corte, sha, usados = declarada
                    ficha["corte"] = corte
                    hasta = [r for r in (filas or []) if r.numero_sorteo <= corte]
                    disponible = filas is not None and any(r.numero_sorteo == corte for r in hasta) and \
                        (usados is None or len(hasta) >= usados)
                    if not disponible:
                        ficha["historico"] = "ausente"
                        rechazos.append({"motivo": "historico_de_entrada_ausente", "familia": familia, "juego": juego,
                                         "clave": _id(g), "corte": corte, "sorteos_declarados": usados,
                                         "sorteos_en_la_captura_hasta_el_corte": len(hasta)})
                    else:
                        actual = _huella(familia, juego, hasta)
                        ficha["historico"] = ("coincide" if actual == sha else
                                              "no_valido" if actual == "no_valido" else "cambio")
                for motivo, referido, conjunto in _referencias(familia, a, claves):
                    if referido not in conjunto:
                        rechazos.append({"motivo": motivo, "familia": familia, "juego": juego,
                                         "clave": _id(g), "referencia": referido})
                if familia == "explicacion":
                    c = carteras.get((a.get("cartera") or {}).get("clave"))
                    if c is not None and c["datos"]["sha256_historico"] != a["cartera"]["sha256_historico"]:
                        rechazos.append({"motivo": "explicacion_y_cartera_con_historico_distinto", "juego": juego,
                                         "familia": familia, "clave": _id(g)})
                artefactos.append(ficha)
    resumen = Counter((f["familia"], f.get("historico", "sin_historico")) for f in artefactos)
    return {"artefactos": sorted(artefactos, key=lambda f: (f["juego"], f["familia"], f["clave"])),
            "ilegibles": dict(sorted(ilegibles.items())), "rechazos": rechazos,
            "resumen": {"artefactos": len(artefactos),
                        "por_familia_y_historico": {f"{k[0]}:{k[1]}": v for k, v in sorted(resumen.items())},
                        "ilegibles": sum(ilegibles.values()), "rechazos": len(rechazos),
                        "objetivos_posteriores_al_ultimo_sorteo": sum(
                            1 for f in artefactos if f["objetivo"] is not None and sorteos(f["juego"]) and
                            f["objetivo"] > sorteos(f["juego"])[-1].numero_sorteo)}}


def _referencias(familia: str, a: dict, claves: dict[str, set]):
    if familia == "explicacion":
        yield "explicacion_sin_su_cartera", (a.get("cartera") or {}).get("clave"), claves["cartera"]
    if familia == "cartera":
        registrado = (((a.get("identidad") or {}).get("modelo") or {}).get("registrado") or {})
        if registrado:
            yield "cartera_sin_su_modelo_registrado", registrado.get("clave"), claves["modelo"]
    if familia == "pronostico_laboratorio":
        yield "pronostico_sin_su_experimento", a.get("experimento"), claves["experimento"]
    if familia == "modelo":
        experimento = (a.get("procedencia") or {}).get("experimento")
        if experimento:
            yield "modelo_sin_su_experimento", experimento, claves["experimento"]


def _tipo_pronostico():
    from app.application.interfaces.pronostico_experimental_store import PronosticoGuardado
    return PronosticoGuardado


def _tipo_explicacion():
    from app.application.interfaces.predicciones_store import ExplicacionGuardada
    return ExplicacionGuardada

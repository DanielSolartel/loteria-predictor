"""Registro y consulta de apuestas desde una cartera guardada en el visor local."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, UUID4
from sqlalchemy.orm import Session

from app.api import dependencies as dep
from app.api.publica import dependencias as lecturas
from app.api.publica.errores import ErrorPublico
from app.api.publica.seguridad import acceso
from app.application.ml.carteras_artefactos import evaluar_combinacion
from app.application.use_cases.carteras import CarterasError
from app.application.use_cases.obtener_sorteo_con_pareja import PAREJAS_DE_JUEGO
from app.domain.entities.juego import Juego
from app.domain.entities.sorteo import Sorteo
from app.infrastructure.storage.apuestas_sqlite import AlmacenApuestasError, ApuestasSQLite


RUTA_APUESTAS = "/api/v1/escritorio/apuestas"
_POR_PAGINA = 20
_MAX_SORTEO = 2_147_483_647
CodigoJuego = Literal["BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO"]


class RegistrarApuesta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    solicitud: UUID4
    cartera: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    linea: int = Field(ge=1, strict=True)
    sorteo: int = Field(ge=1, le=_MAX_SORTEO, strict=True)
    juegos: list[CodigoJuego] = Field(min_length=1, max_length=2)


def _combinacion(juego: str, linea: dict) -> dict:
    if juego == "COLORLOTO":
        return {"pares": linea["pares"]}
    return {"numeros": linea["numeros"], "superbalota": linea.get("superbalota")}


def _nueva_apuesta(solicitud: RegistrarApuesta) -> dict:
    try:
        guardada = dep.construir_carteras(consultar_actividad=False).cartera(solicitud.cartera)
    except CarterasError as error:
        if error.codigo == "no_encontrado":
            raise ErrorPublico(404, "cartera_no_encontrada", "La cartera guardada ya no está disponible.") from error
        raise ErrorPublico(409, "cartera_alterada", "La cartera guardada no supera la verificación de integridad.") from error
    juego = guardada.juego
    admitidos = {juego, PAREJAS_DE_JUEGO.get(juego)}
    if not set(solicitud.juegos) <= admitidos:
        raise ErrorPublico(422, "juego_no_admitido", "Elige un juego compatible con esta combinación.")
    artefacto = guardada.artefacto
    linea = next((c for c in artefacto["cartera"]["combinaciones"] if c["linea"] == solicitud.linea), None)
    if linea is None:
        raise ErrorPublico(422, "linea_no_encontrada", "Elige una línea de la cartera guardada.")
    modelo = artefacto["modelo"]
    return {"id": str(solicitud.solicitud), "registrada_en": datetime.now(timezone.utc).isoformat(),
            "origen": {"cartera": guardada.identificador, "linea": solicitud.linea, "juego": juego,
                       "sorteo": guardada.objetivo, "version_cartera": guardada.version,
                       "modelo": modelo.get("nombre") or modelo["id"], "modelo_id": modelo["id"],
                       "version_modelo": modelo.get("version")},
            "combinacion": _combinacion(juego, linea),
            "participaciones": [{"juego": j, "sorteo": solicitud.sorteo} for j in solicitud.juegos]}


def _confirmar_solicitud(guardada: dict, solicitud: RegistrarApuesta) -> dict:
    origen = guardada["origen"]
    destinos = {(p["juego"], p["sorteo"]) for p in guardada["participaciones"]}
    if (origen["cartera"] != solicitud.cartera or origen["linea"] != solicitud.linea
            or destinos != {(j, solicitud.sorteo) for j in solicitud.juegos}):
        raise ErrorPublico(409, "solicitud_ya_registrada", "La solicitud ya guardó otra apuesta. Abre de nuevo el formulario.")
    return {"id": guardada["id"]}


def _resultado_completo(juego: Juego, sorteo: Sorteo | None) -> dict | None:
    if sorteo is None:
        return None
    r = sorteo.resultado
    if juego.tiene_color:
        return {"pares": [(p.numero, p.color.codigo) for p in r.pares]} if len(r.pares) == juego.cantidad_numeros else None
    if len(r.numeros) != juego.cantidad_numeros or (juego.tiene_superbalota and r.superbalota is None):
        return None
    return {"numeros": r.numeros, "superbalota": r.superbalota}


def _con_resultados(apuestas: list[dict], db: Session) -> list[dict]:
    juegos = dep.get_juego_repository(db)
    sorteos = dep.get_sorteo_repository(db)
    codigos = {p["juego"] for a in apuestas for p in a["participaciones"]}
    referencias = {codigo: juegos.obtener_por_codigo(codigo) for codigo in codigos}
    resultados: dict[tuple[str, int], dict | None] = {}
    for apuesta in apuestas:
        for participacion in apuesta["participaciones"]:
            codigo, numero = participacion["juego"], participacion["sorteo"]
            clave = (codigo, numero)
            juego = referencias[codigo]
            if clave not in resultados:
                resultados[clave] = _resultado_completo(juego, sorteos.obtener_por_numero(juego.id, numero)) if juego else None
            resultado = resultados[clave]
            if resultado is None:
                participacion.update(estado="pendiente", resultado=None, aciertos=None,
                                     numeros_acertados=None, superbalota=None)
                continue
            participacion.update(estado="evaluada", resultado=resultado,
                                 **evaluar_combinacion(codigo, apuesta["combinacion"], resultado))
    return apuestas


def rutas_apuestas(archivo: Path, origen: str) -> APIRouter:
    router = APIRouter()
    almacen = ApuestasSQLite(archivo)

    @router.post(RUTA_APUESTAS, status_code=201)
    def registrar(solicitud: RegistrarApuesta, request: Request, _: str = Depends(acceso(2))):
        if request.headers.getlist("origin") != [origen]:
            raise ErrorPublico(403, "origen_no_permitido", "Abre el visor desde su lanzador.")
        if len(set(solicitud.juegos)) != len(solicitud.juegos):
            raise ErrorPublico(422, "juegos_repetidos", "Elige cada juego una sola vez.")
        try:
            guardada = almacen.buscar(str(solicitud.solicitud))
            if guardada is None:
                guardada = almacen.guardar(_nueva_apuesta(solicitud))
        except AlmacenApuestasError as error:
            raise ErrorPublico(503, "apuestas_no_disponibles", "No se pudo abrir el registro local de apuestas.") from error
        return _confirmar_solicitud(guardada, solicitud)

    @router.get(RUTA_APUESTAS)
    def listar(pagina: int = Query(1, ge=1, le=_MAX_SORTEO), _: str = Depends(acceso(2)),
               db: Session = Depends(lecturas.sesion_de_lectura)):
        try:
            apuestas, total = almacen.listar(pagina, _POR_PAGINA)
        except AlmacenApuestasError as error:
            raise ErrorPublico(503, "apuestas_no_disponibles", "No se pudo abrir el registro local de apuestas.") from error
        return {"apuestas": _con_resultados(apuestas, db), "pagina": pagina,
                "paginas": max(1, (total + _POR_PAGINA - 1) // _POR_PAGINA)}

    return router

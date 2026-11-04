"""Consultas autenticadas y proyectadas de modelos, carteras y resultados."""
from __future__ import annotations

from typing import Literal
from fastapi import APIRouter, Depends, Path, Query

from app.api.publica import dependencias as d
from app.api.publica import esquemas_guardados as e
from app.api.publica.esquemas import ErrorRespuesta
from app.api.publica.errores import ErrorPublico
from app.api.publica.recursos import costosa
from app.api.publica.seguridad import acceso
from app.application.use_cases.consultas_guardadas import ConsultaGuardadaError, ConsultasGuardadas
from app.application.use_cases.carteras import CarterasError
from app.application.use_cases.resultados import ResultadosError

router = APIRouter()
_CODIGOS = {"no_encontrado": (404, "Artefacto inexistente para este juego"),
            "no_valido": (422, "Filtros no válidos para esta consulta"),
            "alterado": (409, "Artefacto guardado alterado o incompleto"),
            "no_disponible": (503, "Datos guardados no disponibles")}
_ERRORES = {s: {"model": ErrorRespuesta}
            for s in (401, 404, 409, 422, 429, 503)}
_CODIGO = Path(description="BALOTO, BALOTO_REVANCHA, MILOTO o COLORLOTO")
_CLAVE = Path(pattern="^[0-9a-f]{64}$", description="Clave SHA-256 del artefacto guardado")
_FILTRO = "^[A-Za-z0-9_.:-]+$"


def _consultar(funcion, *args, **kw):
    try:
        return funcion(*args, **kw)
    except (ConsultaGuardadaError, CarterasError, ResultadosError) as error:
        estado, mensaje = _CODIGOS.get(error.codigo, (500, "Error interno al leer los datos"))
        raise ErrorPublico(estado, error.codigo if error.codigo in _CODIGOS else "error_interno", mensaje) from error
    except OSError as error:
        raise ErrorPublico(503, "no_disponible", "Datos guardados no disponibles") from error


@router.get("/juegos/{codigo}/modelos-guardados", response_model=e.ModelosGuardados, tags=["modelos guardados"],
            responses=_ERRORES, summary="Versiones registradas: metadatos sin cargar el estimador (coste 2)")
def modelos(codigo: str = _CODIGO, pagina: int = Query(1, ge=1, le=10_000),
            por_pagina: int = Query(20, ge=1, le=100),
            modelo: str | None = Query(None, pattern=_FILTRO, max_length=80),
            perfil: Literal["predeterminado", "reducido"] | None = None, _: str = Depends(acceso(2)),
            servicio: ConsultasGuardadas = Depends(d.consultas_guardadas)):
    return _consultar(servicio.modelos, codigo, pagina, por_pagina, modelo, perfil)


@router.get("/juegos/{codigo}/modelos-guardados/{clave}", response_model=e.FichaModeloGuardado, tags=["modelos guardados"],
            responses=_ERRORES, summary="Ficha de una versión registrada, sin deserializar ni ejecutar (coste 2)")
def modelo(codigo: str = _CODIGO, clave: str = _CLAVE, _: str = Depends(acceso(2)),
           servicio: ConsultasGuardadas = Depends(d.consultas_guardadas)):
    return _consultar(servicio.modelo, codigo, clave)


@router.get("/juegos/{codigo}/carteras-guardadas", response_model=e.CarterasGuardadas, tags=["carteras guardadas"],
            responses=_ERRORES, summary="Carteras guardadas de Producto 5 (coste 2)")
def carteras(codigo: str = _CODIGO, pagina: int = Query(1, ge=1, le=10_000),
             por_pagina: int = Query(20, ge=1, le=100),
             linea: str | None = Query(None, pattern=_FILTRO, max_length=160,
                                          description="Identidad de línea emitida por el lector existente"),
             desde: int | None = Query(None, ge=1), hasta: int | None = Query(None, ge=1),
             _: str = Depends(acceso(2)), servicio: ConsultasGuardadas = Depends(d.consultas_guardadas)):
    return _consultar(servicio.carteras, codigo, pagina, por_pagina, linea, desde, hasta)


@router.get("/juegos/{codigo}/carteras-guardadas/{clave}", response_model=e.FichaCarteraGuardada, tags=["carteras guardadas"],
            responses=_ERRORES, summary="Combinaciones y reproducción guardadas, sin generar ni reproducir (coste 2)")
def cartera(codigo: str = _CODIGO, clave: str = _CLAVE, _: str = Depends(acceso(2)),
            servicio: ConsultasGuardadas = Depends(d.consultas_guardadas)):
    return _consultar(servicio.cartera, codigo, clave)


@router.get("/juegos/{codigo}/resultados", response_model=e.ResultadosGuardados, tags=["resultados guardados"],
            responses=_ERRORES, summary="Emisiones y resultados de Producto 6: selección y agregados existentes (coste 5)",
            description="Desde/hasta filtran sorteos objetivo, no la disponibilidad de una emisión. "
                        "Pendientes y sin base no son cero aciertos. No se guardan informes ni se comparan modelos de nuevo.")
@costosa
def resultados(codigo: str = _CODIGO,
               procedencia: Literal["operacion", "laboratorio", "carteras"] | None = None,
               linea: str | None = Query(None, pattern=_FILTRO, max_length=160,
                                          description="Identidad de línea emitida por el lector existente"),
               tipo: Literal["seguimiento", "retrospectiva"] = "seguimiento",
               desde: int | None = Query(None, ge=1), hasta: int | None = Query(None, ge=1),
               objetivo: int | None = Query(None, ge=1), pagina: int = Query(1, ge=1, le=10_000),
               por_pagina: int = Query(20, ge=1, le=100), _: str = Depends(acceso(5)),
               servicio: ConsultasGuardadas = Depends(d.consultas_guardadas)):
    return _consultar(servicio.resultados, codigo, procedencia, linea, tipo, desde, hasta, objetivo, pagina, por_pagina)

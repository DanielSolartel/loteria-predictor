from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.dependencies import get_listar_juegos, get_resumen_sistema
from app.api.web.view_models import juego_a_vm
from app.application.use_cases.consultar_juegos import ListarJuegos
from app.application.use_cases.obtener_resumen_sistema import ObtenerResumenSistema
from app.infrastructure.db.session import get_db

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    listar_juegos: ListarJuegos = Depends(get_listar_juegos),
    resumen_sistema: ObtenerResumenSistema = Depends(get_resumen_sistema),
):
    db_conectada = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_conectada = False

    juegos: list[dict] = []
    total_sorteos = 0
    ultima_actualizacion = None

    if db_conectada:
        juegos = [juego_a_vm(j) for j in listar_juegos.ejecutar()]
        resumen = resumen_sistema.ejecutar()
        total_sorteos = resumen.total_sorteos
        ultima_actualizacion = (
            resumen.ultima_actualizacion.isoformat() if resumen.ultima_actualizacion else None
        )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "active_page": "dashboard",
            "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
            "db_conectada": db_conectada,
            "juegos": juegos,
            "total_sorteos": total_sorteos,
            "ultima_actualizacion": ultima_actualizacion,
        },
    )

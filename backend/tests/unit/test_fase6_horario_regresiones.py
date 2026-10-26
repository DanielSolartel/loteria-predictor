"""Regresiones del hallazgo de la auditoría sobre la base 9966a4bb (Fase 6, horario).

No importan los módulos nuevos: sobre la base fallan por el comportamiento señalado (tarea con
repetición PT5M sin duración e inicio de sesión incondicional; ciclo sin juego ni modo explícito
que el núcleo resuelve con sondeo fuera de franja), no por una importación ausente.
"""
from __future__ import annotations

import inspect
import re
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

from app.application.use_cases.operacion_automatica import OperacionAutomatica
from scripts.operacion_automatica import ejecutar

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/windows/fase6_tarea.ps1"


def _xml_de_la_tarea() -> str:
    """El XML que registra el controlador (su here-string), no las comprobaciones de la versión anterior."""
    texto = SCRIPT.read_text(encoding="utf-8")
    bloques = re.findall(r'\$Xml=@"\n(.*?)\n"@', texto, flags=re.S)
    assert len(bloques) == 1
    return bloques[0]


def test_la_tarea_no_repite_todo_el_dia_ni_dispara_al_iniciar_sesion():
    xml = _xml_de_la_tarea()
    assert "LogonTrigger" not in xml and "TimeTrigger" not in xml and "PT5M" not in xml
    assert "<StartWhenAvailable>false</StartWhenAvailable>" in xml


def test_la_accion_de_la_tarea_declara_la_invocacion_programada_con_su_plan():
    texto = SCRIPT.read_text(encoding="utf-8")
    assert re.search(r"\$ArgumentosV2=\$ArgumentosV1 \+ ' --programado --plan ' \+ \$PlanCargado\.Huella", texto)
    assert "<Arguments>$(Escape-Xml $ArgumentosV2)</Arguments>" in _xml_de_la_tarea()


class _Servicio:
    def __init__(self):
        self.ciclos = []

    def ciclo(self, **kw):
        self.ciclos.append(kw)
        return {"estado": "exito", "juegos": {}}


def test_un_ciclo_sin_modo_explicito_no_consulta(tmp_path):
    from app.core.config import Settings

    servicio = _Servicio()
    ajustes = Settings(_env_file=None, database_url="postgresql+psycopg://u:p@127.0.0.1:1/x",
                       directorio_automatizacion=str(tmp_path / "auto"))
    codigo = ejecutar(["--config", str(tmp_path / "c.json"), "ciclo"], ajustes=ajustes, backend=tmp_path,
                      servicio_factory=lambda **_: servicio, salida=StringIO(), errores=StringIO())
    assert codigo == 2 and servicio.ciclos == []


def test_el_nucleo_distingue_la_invocacion_programada():
    assert "programado" in inspect.signature(OperacionAutomatica.ciclo).parameters


def test_fuera_de_franja_la_invocacion_programada_no_abre_recursos(tmp_path):
    """Lunes 17:00 en Bogotá: sin franjas de ningún juego. La base consultaba los cuatro juegos."""
    from app.infrastructure.storage.automatizacion_file_store import AlmacenAutomatizacion

    class SinAcceso:
        abiertos = []

        def por_juego(self, codigo):
            self.abiertos.append(codigo)
            raise AssertionError("fuera de franja no se abren recursos")
    almacen = AlmacenAutomatizacion(tmp_path / "operacion")
    almacen.guardar_configuracion({"activada": True, "pausada": False})
    adaptador = SinAcceso()
    op = OperacionAutomatica(almacen, adaptador, reloj=lambda: datetime(2026, 10, 26, 22, tzinfo=timezone.utc))
    parametros = inspect.signature(op.ciclo).parameters
    assert "programado" in parametros, "la base no tiene invocación programada: su `ciclo` sondea siempre"
    from app.application import operacion_horario as h
    from app.application.use_cases.operacion_automatica import InvocacionProgramada
    almacen.actualizar_configuracion({"version": 2, "horario": h.como_dict(h.propuesta_inicial())})
    r = op.ciclo(programado=InvocacionProgramada(h.huella_plan(h.propuesta_inicial())))
    assert r["estado"] == "sin_consultas_debidas" and adaptador.abiertos == []

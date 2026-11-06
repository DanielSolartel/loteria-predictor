"""Informe de preparación: los ensayos no se convierten en autorización de producción."""
from __future__ import annotations

from datetime import datetime

from .observabilidad import evaluar

PENDIENTES = (
    "D1_proveedor_presupuesto_infraestructura", "D5_RPO_RTO", "D6_custodia_respaldos",
    "D7_monitor_externo", "D8_registro_y_secretos", "D10_captura_real", "D11_activacion_real",
    "ensayo_nativo_Docker_nginx_mTLS_drenaje_y_reversion",
    "restauracion_RL_en_destino", "restauracion_RW_Windows", "auditoria_SEC_DAT_del_destino",
    "programacion_y_verificacion_de_respaldos_en_destino", "revision_excepciones_Grype_2026-11-17",
    "coordinacion_selector_E104_importacion_y_activacion",
)


def informe(estado: dict, observacion: dict | None, ahora: datetime) -> dict:
    evaluacion = evaluar(observacion, ahora) if observacion is not None else None
    return {"formato": "preparacion-e107/1", "codigo": 3, "produccion_autorizada": False,
            "ensayo_con_servicio_verificado": bool(evaluacion and evaluacion["servicio_verificado"]),
            "transaccion_pendiente": estado["pendiente"] is not None,
            "acceso_registrado": estado["acceso"],
            "alertas": evaluacion["alertas"] if evaluacion else ["observacion_ausente"],
            "pendientes": list(PENDIENTES)}

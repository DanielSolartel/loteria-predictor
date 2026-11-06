"""Perfil E10.7 para un ensayo sintetico local, con permiso independiente del CI.

No convierte una aceptacion de vulnerabilidades ni un ensayo en autorizacion de
produccion. Los planes anteriores conservan su serializacion y su identidad.
"""
from __future__ import annotations

import re
import secrets
from dataclasses import dataclass

from .modelo import Plan, Rechazo, hexadecimal, huella

BASE = "4aaca446c5ea79975683220da0037e2569fbe28e"
FORMATO = "operacion-consulta-local/1"
ARCHIVO = "autorizacion-local.json"


@dataclass(frozen=True)
class PlanLocal(Plan):
    permiso_local: str = ""

    @classmethod
    def de(cls, valor: object) -> "PlanLocal":
        if not isinstance(valor, dict):
            raise Rechazo("plan_local_no_es_objeto")
        d = dict(valor)
        permiso = d.pop("permiso_local", None)
        if (d.get("formato") != FORMATO or d.get("modo") != "ensayo"
                or d.get("host") != "localhost" or not hexadecimal(permiso, 64)):
            raise Rechazo("perfil_local_no_valido")
        # Reusar TODAS las restricciones de redes, rutas, plazos y generacion de
        # E10.5. Solo este formato admite localhost e IDs de imagenes ya locales.
        normal = dict(d, formato="operacion-consulta/1", host="consulta.local.invalid")
        for nombre in ("imagen_api", "imagen_pasarela", "imagen_proxy"):
            imagen = d.get(nombre)
            if not isinstance(imagen, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", imagen):
                raise Rechazo("imagen_local_no_inmutable")
            normal[nombre] = "local.invalid/ensayo@" + imagen
        Plan.de(normal)
        try:
            return cls(**d, permiso_local=permiso)
        except TypeError as error:
            raise Rechazo("campos_del_plan_local") from error


def _sin_permiso(p: Plan) -> dict:
    d = p.objeto()
    d.pop("permiso_local", None)
    return d


def autorizar(almacen, datos: dict, *, confirmar: bool = False) -> PlanLocal:
    """Solo se llama tras --autorizar-ensayo-sintetico, en un control NUEVO.

    El permiso queda ligado al plan entero. Cambiar un montaje, imagen, puerto o
    generacion exige otro control y otro permiso; no se hereda el de E10.5/CI.
    """
    if confirmar is not True or not almacen.bloqueado:
        raise Rechazo("falta_autorizacion_local_explicita")
    if almacen.leer(ARCHIVO) is not None or almacen.leer("estado.json") is not None:
        raise Rechazo("autorizacion_requiere_control_nuevo")
    candidato = PlanLocal.de(dict(datos, permiso_local="0" * 64))
    registro = {"formato": "autorizacion-e107/1", "base_codigo": BASE,
                "destino": "pc_del_usuario", "alcance": "ensayo_sintetico",
                "exposicion": "127.0.0.1", "produccion_autorizada": False,
                "plan_sin_permiso_sha256": huella(_sin_permiso(candidato)),
                "nonce": secrets.token_hex(16)}
    plan = PlanLocal.de(dict(datos, permiso_local=huella(registro)))
    almacen.escribir(ARCHIVO, registro)
    return plan


def comprobar(almacen, plan: Plan) -> None:
    if plan.formato != FORMATO:
        return
    p = PlanLocal.de(plan.objeto())
    r = almacen.leer(ARCHIVO)
    campos = {"formato", "base_codigo", "destino", "alcance", "exposicion",
              "produccion_autorizada", "plan_sin_permiso_sha256", "nonce"}
    if (not isinstance(r, dict) or set(r) != campos or r["formato"] != "autorizacion-e107/1"
            or r["base_codigo"] != BASE or r["destino"] != "pc_del_usuario"
            or r["alcance"] != "ensayo_sintetico" or r["exposicion"] != "127.0.0.1"
            or r["produccion_autorizada"] is not False or not hexadecimal(r["nonce"], 32)
            or r["plan_sin_permiso_sha256"] != huella(_sin_permiso(p))
            or p.permiso_local != huella(r)):
        raise Rechazo("autorizacion_local_ausente_o_de_otro_plan")

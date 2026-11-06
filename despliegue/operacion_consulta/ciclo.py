"""Activación con drenaje, reversión y diario anterior a cada efecto.

El adaptador debe comprobar propiedad antes de cualquier efecto. Un fallo de
reversión conserva la transacción: nunca se presenta como activación correcta.
"""
from __future__ import annotations

import copy
import time
from datetime import datetime, timezone
from typing import Callable, Protocol

from .estado import Almacen
from .modelo import Plan, Rechazo


class Operaciones(Protocol):
    def preparar(self, plan: Plan, plazo: float): ...
    def arrancar(self, plan: Plan, plazo: float): ...
    def validar(self, plan: Plan, plazo: float): ...
    def mantenimiento(self, plan: Plan, cerrar: bool, plazo: float): ...
    def drenar(self, plan: Plan, plazo: float): ...
    def detener(self, plan: Plan, plazo: float): ...
    def publicar(self, plan: Plan, plazo: float): ...
    def sonda(self, plan: Plan, plazo: float): ...


class Motor:
    def __init__(self, almacen: Almacen, adaptador: Callable[[str], Operaciones], *,
                 reloj: Callable[[], float] = time.monotonic,
                 ahora: Callable[[], str] = lambda: datetime.now(timezone.utc).isoformat()):
        self.a, self.fabrica, self.reloj, self.ahora = almacen, adaptador, reloj, ahora

    def _evento(self, e: dict, tipo: str, *, fase: str | None = None):
        e["secuencia"] += 1
        e["eventos"].append({"n": e["secuencia"], "en": self.ahora(), "tipo": tipo, "fase": fase})
        e["eventos"] = e["eventos"][-100:]
        self.a.escribir("estado.json", e)

    def _fase(self, e: dict, nombre: str):
        e["pendiente"]["fase"] = nombre
        self._evento(e, "paso", fase=nombre)

    def _hacer(self, funcion, *args, plazo: float):
        if self.reloj() >= plazo:
            raise Rechazo("plazo_agotado")
        funcion(*args, plazo)
        if self.reloj() >= plazo:
            raise Rechazo("plazo_agotado")

    def activar(self, plan: Plan, *, activa_esperada: str | None = None) -> dict:
        with self.a.exclusivo():
            e = self.a.inicializar()
            if activa_esperada is not None and e["activa"] != activa_esperada:
                raise Rechazo("activa_cambio_desde_la_lectura")
            if e["pendiente"] is not None:
                raise Rechazo("recuperacion_pendiente")
            if e["activa"] == plan.id:
                # No confundir idempotencia con una comprobación de salud reciente.
                return {"codigo": 0, "resultado": "ya_registrada", "salud_comprobada": False}
            anterior = self.a.plan(e["activa"]) if e["activa"] else None
            if anterior is not None:
                if (anterior.host, anterior.puerto, anterior.red_datos) != (plan.host, plan.puerto, plan.red_datos):
                    raise Rechazo("otro_punto_de_entrada")
                if (anterior.red_interna in (plan.red_interna, plan.red_servicio)
                        or anterior.red_servicio in (plan.red_interna, plan.red_servicio)
                        or anterior.ip_datos_api == plan.ip_datos_api):
                    raise Rechazo("redes_de_generaciones_solapadas")
            self.a.guardar_plan(plan)
            op = self.fabrica(e["propietario"])
            e["pendiente"] = {"candidata": plan.id, "anterior": e["activa"],
                              "fase": "preparar", "corte_iniciado": False}
            self._evento(e, "activacion_iniciada")
            corte = None
            try:
                # Preparación fuera del corte; cada llamada sigue teniendo un plazo.
                for fase, metodo in (("preparar", op.preparar), ("arrancar", op.arrancar), ("validar", op.validar)):
                    self._fase(e, fase)
                    self._hacer(metodo, plan, plazo=self.reloj() + 90)
                corte = self.reloj()
                plazo = corte + plan.presupuesto_corte_s
                e["pendiente"]["corte_iniciado"] = True
                e["acceso"] = "sin_verificar"
                if anterior:
                    self._fase(e, "cerrar")
                    self._hacer(op.mantenimiento, anterior, True, plazo=plazo)
                    e["acceso"] = "mantenimiento"
                    self._fase(e, "drenar")
                    self._hacer(op.drenar, anterior, plazo=plazo)
                    self._fase(e, "detener")
                    self._hacer(op.detener, anterior, plazo=plazo)
                self._fase(e, "publicar")
                self._hacer(op.publicar, plan, plazo=plazo)
                self._fase(e, "abrir")
                self._hacer(op.mantenimiento, plan, False, plazo=plazo)
                self._fase(e, "sonda")
                self._hacer(op.sonda, plan, plazo=plazo)
                final = copy.deepcopy(e)
                final.update(activa=plan.id, anterior=e["activa"], pendiente=None, acceso="abierto")
                final["contadores"]["activadas"] += 1
                self._evento(final, "activacion_completada")
                return {"codigo": 0, "resultado": "activada", "generacion": plan.generacion,
                        "corte_s": round(self.reloj() - corte, 3)}
            except (Exception, KeyboardInterrupt):
                e["contadores"]["rechazadas"] += 1
                try:
                    self._evento(e, "activacion_fallida", fase=e["pendiente"]["fase"])
                except OSError:
                    pass  # el diario anterior al efecto sigue siendo recuperable
                salida = self._revertir(e, op)
                if corte is not None:
                    salida["corte_s"] = round(self.reloj() - corte, 3)
                    salida["presupuesto_excedido"] = self.reloj() - corte >= plan.presupuesto_corte_s
                return salida

    def _revertir(self, e: dict, op: Operaciones) -> dict:
        p = e["pendiente"]
        candidata = self.a.plan(p["candidata"])
        anterior = self.a.plan(p["anterior"]) if p["anterior"] else None
        plazo = self.reloj() + candidata.presupuesto_corte_s
        try:
            self._fase(e, "revertir")
        except OSError:
            pass  # no impedir la reversión por un disco lleno
        try:
            # Si no hay contenedores propios, detener es una operación vacía. El
            # adaptador verifica TODO el conjunto antes de detener uno solo.
            self._hacer(op.mantenimiento, candidata, True, plazo=plazo)
            if p["corte_iniciado"]:
                self._hacer(op.drenar, candidata, plazo=plazo)
            self._hacer(op.detener, candidata, plazo=plazo)
            if anterior and p["corte_iniciado"]:
                self._hacer(op.arrancar, anterior, plazo=plazo)
                self._hacer(op.validar, anterior, plazo=plazo)
                self._hacer(op.publicar, anterior, plazo=plazo)
                self._hacer(op.mantenimiento, anterior, False, plazo=plazo)
                self._hacer(op.sonda, anterior, plazo=plazo)
            final = copy.deepcopy(e)
            final["acceso"] = "abierto" if anterior else "cerrado"
            final["pendiente"] = None
            final["contadores"]["revertidas"] += 1
            self._evento(final, "activacion_revertida")
            return {"codigo": 1, "resultado": "revertida" if anterior else "cerrada_sin_generacion",
                    "salud_comprobada": bool(anterior and p["corte_iniciado"])}
        except (Exception, KeyboardInterrupt):
            # No se afirma mantenimiento si no se pudo comprobar. El diario y
            # ambas generaciones permanecen para una recuperación explícita.
            e["acceso"] = "sin_verificar"
            e["contadores"]["bloqueadas"] += 1
            try:
                self._evento(e, "recuperacion_pendiente", fase="revertir")
            except OSError:
                pass
            return {"codigo": 4, "resultado": "recuperacion_pendiente"}

    def recuperar(self) -> dict:
        with self.a.exclusivo():
            e = self.a.inicializar()
            if e["pendiente"] is None:
                return {"codigo": 0, "resultado": "sin_transaccion", "salud_comprobada": False}
            self._evento(e, "recuperacion_iniciada")
            resultado = self._revertir(e, self.fabrica(e["propietario"]))
            # Una recuperación completa sí es correcta; la activación original no lo fue.
            if resultado["codigo"] == 1:
                resultado["codigo"] = 0
            return resultado

    def revertir(self) -> dict:
        with self.a.exclusivo():
            e = self.a.inicializar()
            if e["pendiente"] or e["anterior"] is None:
                raise Rechazo("sin_anterior_reversible")
            plan, activa = self.a.plan(e["anterior"]), e["activa"]
        return self.activar(plan, activa_esperada=activa)

"""Muestras acotadas y alertas independientes de la API y de su contrato público."""
from __future__ import annotations

import math
from datetime import date, datetime, timezone

from .modelo import Rechazo, hexadecimal

JUEGOS = ("BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO")
REGLAS = {"captura_max_s": 129600, "contacto_max_s": 172800, "muestra_max_s": 120,
          "rechazos_consecutivos": 3}


def instante(valor: object) -> datetime:
    if not isinstance(valor, str) or len(valor) > 40:
        raise Rechazo("instante_no_valido")
    try:
        d = datetime.fromisoformat(valor)
        if d.tzinfo is None or d.utcoffset() is None:
            raise ValueError()
        return d.astimezone(timezone.utc)
    except ValueError as error:
        raise Rechazo("instante_no_valido") from error


def _numero(v, *, entero=False):
    if (type(v) not in ((int,) if entero else (int, float)) or not 0 <= v <= 10**15
            or not math.isfinite(v)):
        raise Rechazo("metrica_no_valida")
    return v


def reglas_de(valor: dict | None) -> dict:
    v = dict(REGLAS if valor is None else valor)
    if set(v) != set(REGLAS):
        raise Rechazo("reglas_no_validas")
    for n in v:
        _numero(v[n], entero=True)
        if v[n] < 1:
            raise Rechazo("reglas_no_validas")
    return v


def servicio_de(d: dict | None) -> dict:
    if d is None:
        return {"disponible": False, "solicitudes": None, "errores_4xx": None, "errores_5xx": None,
                "latencia_max_ms": None, "segundos_activo": None}
    if not isinstance(d, dict) or d.get("base") != "disponible":
        raise Rechazo("estado_del_servicio")
    clases = d.get("por_clase", {})
    rutas = d.get("rutas", [])
    if not isinstance(clases, dict) or not isinstance(rutas, list) or len(rutas) > 128:
        raise Rechazo("estado_del_servicio")
    return {"disponible": True, "solicitudes": _numero(d["solicitudes"], entero=True),
            "errores_4xx": _numero(clases.get("4xx", 0), entero=True),
            "errores_5xx": _numero(clases.get("5xx", 0), entero=True),
            "latencia_max_ms": max((_numero(r["latencia_maxima_ms"]) for r in rutas), default=0),
            "segundos_activo": _numero(d["segundos_activo"])}


def senales_iniciales() -> dict:
    return {"formato": "senales-e106/1", "pc_contacto_en": None, "rechazos_consecutivos": 0,
            "ultimo_rechazo_en": None, "captura_verificada_en": None, "calendario": {}}


def validar_senales(s: object) -> dict:
    if (not isinstance(s, dict) or set(s) != {"formato", "pc_contacto_en", "rechazos_consecutivos", "calendario",
                                            "ultimo_rechazo_en", "captura_verificada_en"}
            or s["formato"] != "senales-e106/1"):
        raise Rechazo("senales_no_validas")
    if s["pc_contacto_en"] is not None:
        instante(s["pc_contacto_en"])
    for n in ("ultimo_rechazo_en", "captura_verificada_en"):
        if s[n] is not None:
            instante(s[n])
    _numero(s["rechazos_consecutivos"], entero=True)
    if not isinstance(s["calendario"], dict) or not set(s["calendario"]) <= set(JUEGOS):
        raise Rechazo("calendario_no_valido")
    for v in s["calendario"].values():
        if not isinstance(v, dict) or set(v) != {"fecha_sorteo_esperado", "resultado_esperado_antes_de"}:
            raise Rechazo("calendario_no_valido")
        try:
            if date.fromisoformat(v["fecha_sorteo_esperado"]).isoformat() != v["fecha_sorteo_esperado"]:
                raise ValueError()
        except (ValueError, TypeError) as error:
            raise Rechazo("calendario_no_valido") from error
        instante(v["resultado_esperado_antes_de"])
    return s


def registrar(s: dict, tipo: str, en: str, *, ahora: datetime) -> dict:
    import copy
    r = copy.deepcopy(validar_senales(s))
    fecha = instante(en)
    if (fecha - ahora).total_seconds() > 30:
        raise Rechazo("senal_en_el_futuro")
    if tipo == "contacto_pc":
        if r["pc_contacto_en"] is not None and fecha < instante(r["pc_contacto_en"]):
            raise Rechazo("contacto_anterior_al_registrado")
        r["pc_contacto_en"] = fecha.isoformat()
    elif tipo == "captura_rechazada":
        if r["ultimo_rechazo_en"] is not None and fecha < instante(r["ultimo_rechazo_en"]):
            raise Rechazo("rechazo_anterior_al_registrado")
        r["rechazos_consecutivos"] += 1
        r["ultimo_rechazo_en"] = fecha.isoformat()
    elif tipo == "captura_verificada":
        # Solo lo usa el colector después de verificar una firma y los archivos.
        if r["captura_verificada_en"] is None or fecha > instante(r["captura_verificada_en"]):
            r["captura_verificada_en"] = fecha.isoformat()
        # Releer la generación anterior no oculta fallos posteriores de captura.
        if r["ultimo_rechazo_en"] is None or fecha >= instante(r["ultimo_rechazo_en"]):
            r["rechazos_consecutivos"] = 0
    else:
        raise Rechazo("tipo_de_senal")
    return r


def muestra(estado: dict, manifiesto: dict | None, servicio: dict | None, senales: dict,
            ahora: datetime, reglas: dict | None = None) -> dict:
    captura, fechas, gid = None, {}, None
    if manifiesto is not None:
        gid = manifiesto["id"]
        if not hexadecimal(gid, 32):
            raise Rechazo("generacion_no_valida")
        captura = instante(manifiesto["creada_en"]).isoformat()
        for j in JUEGOS:
            f = manifiesto.get("juegos", {}).get(j, {}).get("ultima_fecha")
            if f is not None:
                try:
                    if date.fromisoformat(f).isoformat() != f:
                        raise ValueError()
                except (ValueError, TypeError) as error:
                    raise Rechazo("fecha_de_sorteo_no_valida") from error
            fechas[j] = f
    terminales = {"activacion_completada", "activacion_revertida", "recuperacion_pendiente"}
    ultimo = next((v["tipo"] for v in reversed(estado["eventos"]) if v["tipo"] in terminales), None)
    r = {"formato": "observacion-e106/1", "observado_en": ahora.astimezone(timezone.utc).isoformat(),
         "generacion": gid, "captura_en": captura, "ultimos_sorteos": fechas,
         "acceso": estado["acceso"], "transaccion_pendiente": estado["pendiente"] is not None,
         "ultimo_resultado": ultimo, "contadores": dict(estado["contadores"]),
         "servicio": servicio_de(servicio), "senales": validar_senales(senales), "reglas": reglas_de(reglas)}
    validar_muestra(r)
    return r


def validar_muestra(v: object) -> dict:
    campos = {"formato", "observado_en", "generacion", "captura_en", "ultimos_sorteos", "acceso",
              "transaccion_pendiente", "ultimo_resultado", "contadores", "servicio", "senales", "reglas"}
    if not isinstance(v, dict) or set(v) != campos or v["formato"] != "observacion-e106/1":
        raise Rechazo("muestra_no_valida")
    instante(v["observado_en"])
    if v["generacion"] is not None and not hexadecimal(v["generacion"], 32):
        raise Rechazo("muestra_no_valida")
    if v["captura_en"] is not None:
        instante(v["captura_en"])
    if (v["generacion"] is None) != (v["captura_en"] is None):
        raise Rechazo("muestra_no_valida")
    if (v["acceso"] not in ("cerrado", "abierto", "mantenimiento", "sin_verificar")
            or type(v["transaccion_pendiente"]) is not bool
            or v["ultimo_resultado"] not in (None, "activacion_completada", "activacion_revertida", "recuperacion_pendiente")):
        raise Rechazo("muestra_no_valida")
    if (not isinstance(v["contadores"], dict)
            or set(v["contadores"]) != {"activadas", "rechazadas", "revertidas", "bloqueadas"}):
        raise Rechazo("muestra_no_valida")
    for n in v["contadores"].values():
        _numero(n, entero=True)
    servicio = v["servicio"]
    if (not isinstance(servicio, dict)
            or set(servicio) != {"disponible", "solicitudes", "errores_4xx", "errores_5xx", "latencia_max_ms", "segundos_activo"}
            or type(servicio["disponible"]) is not bool):
        raise Rechazo("muestra_no_valida")
    for k, n in servicio.items():
        if k != "disponible" and (n is not None or servicio["disponible"]):
            _numero(n, entero=k in ("solicitudes", "errores_4xx", "errores_5xx"))
    fechas = v["ultimos_sorteos"]
    if not isinstance(fechas, dict) or not set(fechas) <= set(JUEGOS):
        raise Rechazo("muestra_no_valida")
    for f in fechas.values():
        if f is not None:
            try:
                if date.fromisoformat(f).isoformat() != f:
                    raise ValueError()
            except (ValueError, TypeError) as error:
                raise Rechazo("muestra_no_valida") from error
    validar_senales(v["senales"])
    reglas_de(v["reglas"])
    return v


def evaluar(v: dict, ahora: datetime) -> dict:
    validar_muestra(v)
    alertas, edades = set(), {}
    reloj_futuro = False

    def edad(nombre, en):
        nonlocal reloj_futuro
        if en is None:
            edades[nombre] = None
        else:
            e = (ahora - instante(en)).total_seconds()
            reloj_futuro |= e < -30
            edades[nombre] = max(0, e)
        return edades[nombre]

    edad("muestra", v["observado_en"])
    edad("captura", v["captura_en"])
    edad("contacto_pc", v["senales"]["pc_contacto_en"])
    for n, limite, ausente, vencido in (
            ("muestra", "muestra_max_s", "observacion_ausente", "observacion_obsoleta"),
            ("captura", "captura_max_s", "captura_sin_verificar", "captura_antigua"),
            ("contacto_pc", "contacto_max_s", "contacto_pc_desconocido", "pc_silencioso")):
        if edades[n] is None:
            alertas.add(ausente)
        elif edades[n] > v["reglas"][limite]:
            alertas.add(vencido)
    if reloj_futuro:
        alertas.add("reloj_incoherente")
    if not v["servicio"]["disponible"]:
        alertas.add("servicio_no_disponible")
    if v["acceso"] != "abierto":
        alertas.add("acceso_no_verificado")
    if v["transaccion_pendiente"]:
        alertas.add("generacion_no_activada")
    if v["ultimo_resultado"] == "activacion_revertida":
        alertas.add("activacion_revertida")
    if v["senales"]["rechazos_consecutivos"] >= v["reglas"]["rechazos_consecutivos"]:
        alertas.add("captura_rechazada")
    calendario = v["senales"]["calendario"]
    atrasados = []
    for j in JUEGOS:
        c = calendario.get(j)
        if c is None:
            continue
        f = v["ultimos_sorteos"].get(j)
        if ahora > instante(c["resultado_esperado_antes_de"]) and (f is None or f < c["fecha_sorteo_esperado"]):
            atrasados.append(j)
    if atrasados:
        alertas.add("sorteo_pendiente_segun_calendario")
    if len(calendario) < len(JUEGOS):
        alertas.add("calendario_incompleto")
    sano = (edades["muestra"] <= v["reglas"]["muestra_max_s"] and not reloj_futuro
            and v["generacion"] is not None and v["servicio"]["disponible"]
            and v["acceso"] == "abierto" and not v["transaccion_pendiente"])
    return {"servicio_verificado": sano, "edades_s": edades, "alertas": sorted(alertas), "sorteos_atrasados": atrasados}


def metricas(v: dict, ahora: datetime) -> tuple[str, bool]:
    e = evaluar(v, ahora)
    lineas = ["# TYPE loteria_consulta_verificada gauge", "# TYPE loteria_antiguedad_segundos gauge",
              "# TYPE loteria_transiciones_total counter", "# TYPE loteria_alerta gauge",
              "loteria_consulta_verificada " + str(int(e["servicio_verificado"]))]
    for nombre, segundos in e["edades_s"].items():
        if segundos is not None:
            lineas.append('loteria_antiguedad_segundos{senal="%s"} %.3f' % (nombre, segundos))
    for nombre in sorted(v["contadores"]):
        lineas.append('loteria_transiciones_total{resultado="%s"} %d' % (nombre, v["contadores"][nombre]))
    for nombre, valor in v["servicio"].items():
        if nombre != "disponible" and valor is not None:
            # Son valores de /estado por proceso: gauges, porque reiniciar los pone a cero.
            lineas.append("# TYPE loteria_api_%s gauge" % nombre)
            lineas.append("loteria_api_%s %s" % (nombre, valor))
    for alerta in e["alertas"]:
        lineas.append('loteria_alerta{tipo="%s"} 1' % alerta)
    return "\n".join(lineas) + "\n", e["servicio_verificado"]

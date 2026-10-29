"""Consultas públicas de artefactos existentes, sin ejecutar ni reparar modelos.

Los lectores verifican los artefactos. Producto 6 conserva la selección, las
métricas y las agregaciones de su caso de uso; aquí solo se proyectan campos.
No se consulta configuración vigente para describir una emisión histórica.
"""
from __future__ import annotations

import re

from app.application.interfaces.carteras_store import GuardadoCarteras
from app.application.interfaces.laboratorio_store import GuardadoModelo
from app.application.ml import modelos_registrados as mr
from app.application.use_cases.resultados import Filtros

_CLAVE = re.compile(r"[0-9a-f]{64}")
_JUEGOS = ("BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO")
_NOTA_MODELOS = ("Son versiones realmente registradas, no el catálogo de candidatos. La lectura comprueba "
                 "manifiesto y huellas del estimador, sin deserializarlo ni comprobar su ejecución. "
                 "Compatible no acredita ventaja predictiva.")
_NOTA_CARTERAS = ("Carteras guardadas de Producto 5, distintas de las predicciones de Fase 9.3. "
                  "Se muestran combinaciones y parámetros guardados; no se generan ni reproducen.")
_NOTA_TEMPORAL = ("Corte de entrada y objetivo son distintos. El reloj local de emisión y un filtro por corte "
                  "no acreditan que la emisión estuviera disponible antes del sorteo real.")
_NOTA_RESULTADOS = ("Lectura y agregaciones de Producto 6. Solo las emisiones incluidas entran en métricas; "
                    "pendiente y sin base no son cero aciertos. Desde/hasta filtran sorteos objetivo y no "
                    "acreditan disponibilidad anterior de la emisión. No se guardan informes.")


class ConsultaGuardadaError(Exception):
    def __init__(self, codigo: str):
        self.codigo = codigo
        super().__init__(codigo)


def _validar(juego: str, clave: str | None = None) -> None:
    if juego not in _JUEGOS or (clave is not None and not _CLAVE.fullmatch(clave)):
        raise ConsultaGuardadaError("no_encontrado")


def _pagina(elementos: list, juego: str, pagina: int, por_pagina: int) -> dict:
    if not 1 <= pagina <= 10_000 or not 1 <= por_pagina <= 100:
        raise ConsultaGuardadaError("no_valido")
    total = len(elementos)
    paginas = max(1, -(-total // por_pagina))
    pagina = min(pagina, paginas)
    inicio = (pagina - 1) * por_pagina
    return {"juego": juego, "estado_de_uso": "experimental_no_acreditado", "pagina": pagina, "paginas": paginas,
            "por_pagina": por_pagina, "total": total, "elementos": elementos[inicio:inicio + por_pagina]}


def _clave_publica(clave: str) -> str:
    # Un nombre no admitido del almacén no se convierte en una ruta pública.
    return clave if _CLAVE.fullmatch(clave or "") else ""


def _motivo_resultado(motivo: str | None) -> str | None:
    if motivo is None:
        return None
    # Los códigos estables del motor son públicos. Mensajes de excepciones no.
    if re.fullmatch(r"[a-z0-9_:]+", motivo):
        return motivo
    return "emision_no_admitida; consulte los estados de integridad, histórico y resultado"


def _campos_tipados(datos: dict, tipos: dict, nulos: tuple[str, ...] = ()) -> None:
    """Tipos de los metadatos que se publican, sin coerciones ni ejecutar ML."""
    if not isinstance(datos, dict):
        raise ValueError("metadatos incompletos")
    for nombre, esperado in tipos.items():
        valor = datos[nombre]
        if valor is None and nombre in nulos:
            continue
        admitidos = esperado if isinstance(esperado, tuple) else (esperado,)
        if type(valor) not in admitidos:
            raise ValueError("tipo de metadato no admitido")


def _metadatos_de_modelo(a: dict) -> None:
    # No es un validador del estimador ni una receta nueva: limita la forma de
    # los campos necesarios para esta proyección. Los demás campos no se leen.
    i = a["identidad"]
    _campos_tipados(i["modelo"], {"familia": str})
    _campos_tipados(i, {"semilla": int, "hilos": int, "sha256_historico": str})
    _campos_tipados(i["periodo"], {"primer_sorteo": int, "ultimo_sorteo": int,
                                  "primera_fecha": str, "ultima_fecha": str, "sorteos": int})
    _campos_tipados(a, {"objetivo_estadistico": str, "contrato_de_inferencia": str})
    _campos_tipados(a["procedencia"], {"experimento": str})
    variables = i["variables"]["nombres"]
    if not isinstance(variables, list) or any(type(v) is not str for v in variables):
        raise ValueError("variables no reconocidas")


class _MetadatosCarteraError(ValueError):
    """Sólo una ausencia o tipo inválido del contenido que se va a publicar."""


_AUSENTE = object()


def _dato_cartera(objeto, campo, tipos, predeterminado=_AUSENTE):
    if type(objeto) is not dict:
        raise _MetadatosCarteraError("contenedor no acreditado")
    valor = objeto.get(campo, predeterminado)
    admitidos = tipos if isinstance(tipos, tuple) else (tipos,)
    if valor is _AUSENTE or type(valor) not in admitidos:
        raise _MetadatosCarteraError("metadato necesario ausente o de tipo no válido")
    return valor


def _cartera_alterada(e) -> dict:
    # La identidad procede del lector, no de la configuración ni de otro
    # artefacto. Los demás metadatos se mantienen ausentes en el contrato.
    return {"clave": _clave_publica(e.identificador), "juego": e.juego, "estado": "alterado",
            "motivo": "artefacto_alterado_o_incompleto", "linea": e.linea,
            "objetivo": e.objetivo if type(e.objetivo) is int else None}


def _proyeccion_cartera(e: GuardadoCarteras) -> tuple[dict, dict]:
    """Forma de los campos leídos, sin validar otra receta ni ejecutar nada.

    Se valida también el contexto necesario de la ficha para que el listado
    no anuncie como disponible una cartera cuya ficha no se puede acreditar.
    Sólo los campos opcionales admiten ausencia; bool no se coacciona a int.
    """
    a = e.artefacto
    identidad = _dato_cartera(a, "identidad", dict)
    modelo = _dato_cartera(identidad, "modelo", dict)
    datos = _dato_cartera(a, "datos", dict)
    generacion = _dato_cartera(a, "generacion", dict)
    parametros = _dato_cartera(identidad, "cartera", dict)
    tipos = {"cantidad": int, "semilla": int, "diversidad": str, "version": str,
             "algoritmo_rng": str, "presupuesto_de_intentos": int}
    parametros_publicos = {n: _dato_cartera(parametros, n, t) for n, t in tipos.items()}
    registrado = _dato_cartera(modelo, "registrado", (dict, type(None)), None)
    referencia = None if registrado is None else {
        "clave": _dato_cartera(registrado, "clave", str), "numero": _dato_cartera(registrado, "numero", int)}
    resumen = {"clave": e.identificador, "juego": e.juego, "estado": "disponible", "motivo": None,
               "linea": e.linea, "objetivo": e.objetivo, "corte": _dato_cartera(datos, "corte", int),
               "modelo": _dato_cartera(modelo, "id", str),
               "nombre": _dato_cartera(_dato_cartera(a, "modelo", dict), "nombre", (str, type(None)), None),
               "version_receta": str(_dato_cartera(modelo, "version", (str, int))),
               "perfil": _dato_cartera(identidad, "perfil", str), "version": e.version, "versiones": e.versiones,
               "cantidad": parametros_publicos["cantidad"],
               "generado_en": _dato_cartera(generacion, "generado_en", (str, type(None)), None),
               "registrado": referencia}
    combinaciones = []
    for c in _dato_cartera(_dato_cartera(a, "cartera", dict), "combinaciones", list):
        numeros = _dato_cartera(c, "numeros", list, [])
        if any(type(n) is not int for n in numeros):
            raise _MetadatosCarteraError("números no acreditados")
        pares = _dato_cartera(c, "pares", list, [])
        if any(type(p) is not list or len(p) != 2 or type(p[0]) is not int or type(p[1]) is not str for p in pares):
            raise _MetadatosCarteraError("pares no acreditados")
        combinaciones.append({"linea": _dato_cartera(c, "linea", int), "origen": _dato_cartera(c, "origen", str),
                              "numeros": numeros, "superbalota": _dato_cartera(c, "superbalota", (int, type(None)), None),
                              "pares": [{"numero": p[0], "color": p[1]} for p in pares]})
    temporal = _dato_cartera(generacion, "clasificacion_temporal", (dict, type(None)), None)
    detalle = {"combinaciones": combinaciones, "parametros": parametros_publicos,
               "sha256_historico": _dato_cartera(datos, "sha256_historico", str),
               "clasificacion_temporal": None if temporal is None else _dato_cartera(temporal, "tipo", (str, type(None)), None)}
    return resumen, detalle


class ConsultasGuardadas:
    def __init__(self, modelos, carteras, resultados):
        self._modelos = modelos
        self._carteras = carteras
        self._resultados = resultados

    @staticmethod
    def _modelo(e) -> dict:
        try:
            return ConsultasGuardadas._proyectar_modelo(e)
        except (AttributeError, KeyError, TypeError, ValueError):
            # El lector acredita canon, reserva y bytes del estimador. Un
            # manifiesto puede aun carecer de los metadatos de esta ficha;
            # no se completan con el catálogo ni se ejecuta para reconstruirlos.
            return {"clave": _clave_publica(e.identificador), "juego": e.juego, "estado": "alterado",
                    "motivo": "artefacto_alterado_o_incompleto"}

    @staticmethod
    def _proyectar_modelo(e) -> dict:
        if not isinstance(e, GuardadoModelo):
            return {"clave": _clave_publica(e.identificador), "juego": e.juego, "estado": "alterado",
                    "motivo": "artefacto_alterado_o_incompleto", "modelo": e.modelo, "numero": e.numero}
        a = e.artefacto
        _metadatos_de_modelo(a)
        resumen = mr.resumen(a)
        _campos_tipados(resumen, {"modelo": str, "nombre": str, "perfil": str,
                                  "version_de_la_receta": (str, int), "numero": int,
                                  "corte": int, "sorteos": int, "entrenado_en": str, "linea": str},
                         nulos=("entrenado_en",))
        compat = mr.compatibilidad(a)
        return {"clave": e.identificador, "juego": e.juego,
                "estado": "disponible" if compat["compatible"] else "incompatible",
                "motivo": None if compat["compatible"] else "receta_o_entorno_no_compatible",
                "modelo": resumen["modelo"], "nombre": resumen["nombre"], "familia": a["identidad"]["modelo"]["familia"],
                "perfil": resumen["perfil"], "version_receta": str(resumen["version_de_la_receta"]),
                "numero": resumen["numero"], "corte": resumen["corte"], "sorteos": resumen["sorteos"],
                "entrenado_en": resumen["entrenado_en"], "linea": resumen["linea"]}

    def modelos(self, juego: str, pagina: int = 1, por_pagina: int = 20, modelo: str | None = None,
                perfil: str | None = None) -> dict:
        _validar(juego)
        filas = [self._modelo(e) for e in self._modelos.modelos(juego)]
        filas = [e for e in filas if (modelo is None or e.get("modelo") == modelo)
                 and (perfil is None or e.get("perfil") == perfil)]
        return {**_pagina(filas, juego, pagina, por_pagina), "modelo": modelo, "perfil": perfil,
                "nota": _NOTA_MODELOS}

    def modelo(self, juego: str, clave: str) -> dict:
        _validar(juego, clave)
        e = self._modelos.obtener_modelo(clave)
        if e is None or e.juego != juego:
            raise ConsultaGuardadaError("no_encontrado")
        if not isinstance(e, GuardadoModelo):
            raise ConsultaGuardadaError("alterado")
        try:
            return self._ficha_modelo(e)
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            raise ConsultaGuardadaError("alterado") from error

    def _ficha_modelo(self, e: GuardadoModelo) -> dict:
        modelo = self._modelo(e)
        if modelo["estado"] == "alterado":
            raise ConsultaGuardadaError("alterado")
        juego = e.juego
        a, i = e.artefacto, e.artefacto["identidad"]
        evaluacion = a["procedencia"]["evaluacion"]
        agregado = evaluacion.get("agregado") or {}
        ficha = {"juego": juego, "estado_de_uso": "experimental_no_acreditado", "modelo": modelo,
                "periodo": i["periodo"], "sha256_historico": i["sha256_historico"], "variables": i["variables"]["nombres"],
                "semilla": i["semilla"], "hilos": i["hilos"], "objetivo_estadistico": a["objetivo_estadistico"],
                "contrato_de_inferencia": a["contrato_de_inferencia"], "experimento": a["procedencia"]["experimento"],
                "evaluacion": {"estado": evaluacion.get("estado"), "veredicto": evaluacion.get("veredicto"),
                               "corte": evaluacion.get("corte"), "objetivos": evaluacion.get("objetivos"),
                               "muestra_pequena": evaluacion.get("muestra_pequena"), "log_loss": agregado.get("log_loss"),
                               "log_loss_uniforme": (agregado.get("uniforme") or {}).get("log_loss"),
                               "nota": mr.NOTA_EVALUACION}, "nota": _NOTA_MODELOS}
        _campos_tipados(ficha["evaluacion"], {"estado": str, "veredicto": str, "corte": int,
                                             "objetivos": int, "muestra_pequena": bool,
                                             "log_loss": (int, float), "log_loss_uniforme": (int, float)},
                         nulos=("estado", "veredicto", "corte", "objetivos", "muestra_pequena", "log_loss",
                                "log_loss_uniforme"))
        return ficha

    @staticmethod
    def _cartera(e) -> dict:
        if not isinstance(e, GuardadoCarteras):
            return _cartera_alterada(e)
        try:
            return _proyeccion_cartera(e)[0]
        except _MetadatosCarteraError:
            return _cartera_alterada(e)

    def carteras(self, juego: str, pagina: int = 1, por_pagina: int = 20, linea: str | None = None,
                 desde: int | None = None, hasta: int | None = None) -> dict:
        _validar(juego)
        if desde is not None and hasta is not None and desde > hasta:
            raise ConsultaGuardadaError("no_valido")
        lineas = self._carteras.lineas(juego)
        if linea is not None and linea not in lineas:
            raise ConsultaGuardadaError("no_valido")
        filas = [self._cartera(e) for nombre in lineas if linea is None or nombre == linea
                 for e in self._carteras.carteras_de_linea(juego, nombre)]
        sin_objetivo = sum(1 for e in filas if e.get("objetivo") is None)
        filas = [e for e in filas if e.get("objetivo") is None or (
            (desde is None or e["objetivo"] >= desde) and (hasta is None or e["objetivo"] <= hasta))]
        filas.sort(key=lambda e: (-(e.get("objetivo") or 0), e.get("linea") or "", -(e.get("version") or 0), e["clave"]))
        return {**_pagina(filas, juego, pagina, por_pagina), "lineas": lineas, "linea": linea,
                "desde": desde, "hasta": hasta, "incidencias_sin_objetivo": sin_objetivo,
                "nota": _NOTA_CARTERAS + " Desde/hasta filtran el objetivo, no la fecha de disponibilidad."}

    def cartera(self, juego: str, clave: str) -> dict:
        _validar(juego, clave)
        # Comprobar juego antes de devolver el contenido, incluso para ilegibles.
        e = self._carteras._almacen.obtener_cartera(clave)
        if e is None or e.juego != juego:
            raise ConsultaGuardadaError("no_encontrado")
        if not isinstance(e, GuardadoCarteras):
            raise ConsultaGuardadaError("alterado")
        try:
            resumen, detalle = _proyeccion_cartera(e)
        except _MetadatosCarteraError as error:
            raise ConsultaGuardadaError("alterado") from error
        return {"juego": juego, "estado_de_uso": "experimental_no_acreditado", "cartera": resumen, **detalle,
                "nota_temporal": _NOTA_TEMPORAL, "nota": _NOTA_CARTERAS}

    def resultados(self, juego: str, procedencia: str | None = None, linea: str | None = None,
                   tipo: str = "seguimiento", desde: int | None = None, hasta: int | None = None,
                   objetivo: int | None = None, pagina: int = 1, por_pagina: int = 20) -> dict:
        _validar(juego)
        filtros = Filtros(procedencias=(procedencia,) if procedencia else Filtros().procedencias,
                          lineas=(linea,) if linea else (), tipo=tipo, desde=desde, hasta=hasta, objetivo=objetivo).validar()
        consulta = self._resultados.consultar(juego, filtros, pagina=pagina, por_pagina=por_pagina)
        base = {**consulta["base"], "motivo": ("Base de datos no disponible" if consulta["base"]["estado"] == "no_disponible"
                                             else consulta["base"].get("motivo"))}
        procedencias = {k: {**v, "error": None if v["error"] is None else "No se pudo leer esta procedencia"}
                       for k, v in consulta["procedencias"].items()}
        lineas = []
        for l in consulta["lineas"]:
            meta = l["metadatos"]
            registrado = meta.get("registrado")
            lineas.append({k: l[k] for k in ("clave", "procedencia", "linea", "nombre")} | {
                "modelo": meta.get("modelo"), "version": None if meta.get("version") is None else str(meta["version"]),
                "perfil": meta.get("perfil"), "registrado": None if registrado is None else {
                    "clave": registrado["clave"], "numero": registrado["numero"]}})
        historial = {**consulta["historial"], "filas": []}
        campos = ("juego", "procedencia", "linea", "clave_linea", "objetivo", "tipo", "identificador", "versiones",
                  "integridad", "historico", "resultado_estado", "estado", "fecha_sorteo", "aciertos", "de",
                  "metricas", "superbalota")
        for f in consulta["historial"]["filas"]:
            resultado = f.get("resultado")
            publico = {k: f[k] for k in campos}
            publico["motivo"] = _motivo_resultado(f.get("motivo"))
            publico["resultado"] = None if resultado is None else {
                "numeros": resultado.get("numeros", []), "superbalota": resultado.get("superbalota"),
                "pares": [{"numero": p[0], "color": p[1]} for p in resultado.get("pares", [])]}
            historial["filas"].append(publico)
        return {"juego": juego, "estado_de_uso": "experimental_no_acreditado",
                "filtros": {"procedencia": procedencia, "linea": linea, "tipo": tipo, "desde": desde,
                            "hasta": hasta, "objetivo": objetivo}, "base": base, "procedencias": procedencias,
                "lineas": lineas, "seleccion": consulta["seleccion"], "resumenes": consulta["resumenes"],
                "comparacion": consulta["comparacion"], "historial": historial,
                **{k: consulta[k] for k in ("sin_resultados_de_seguimiento", "politica", "nota_seguimiento", "signo", "unidades")},
                "nota": _NOTA_RESULTADOS}

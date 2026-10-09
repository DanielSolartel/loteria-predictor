"""
Producto 6: centro de resultados y evaluacion continua de modelos.

Caso de uso UNICO para HTML, API y comando: los mismos filtros, estados,
objetivos y valores. Consultar es lectura pura: no entrena, no importa, no
inicia trabajadores y no escribe en ningun almacen. Solo «guardar informe» y
«usar esta configuracion» escriben, y solo cuando se piden explicitamente.

- Procedencias (ver `resultados_procedencias`): operacion diaria (Productos
  1-3), laboratorio (Producto 4) y vector fuente de las carteras (Producto 5),
  cada una con su politica de primera emision sellada. Si una procedencia no
  se puede leer, las demas se siguen consultando.
- Una lectura del historico por juego; si la base no responde, las emisiones
  quedan `sin_base` (no son cero aciertos ni pendientes confirmados) y no se
  inventa un ultimo resultado.
- Tipo inicial `seguimiento`; si no tiene resultados se dice y se puede elegir
  `retrospectiva` (nunca se cambia de tipo automaticamente). Seguimiento y
  retrospectiva no se mezclan; simulaciones y walk-forward no entran.
- Seleccion por defecto: una linea por procedencia (la de mas objetivos
  admitidos del tipo; empate por nombre). Se puede elegir cualquier conjunto.
- Exportaciones CSV y JSON del conjunto filtrado completo (no solo la pagina).
"""
from __future__ import annotations

import csv
import io
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from app.application.ml import resultados_calibracion as rc
from app.application.ml import resultados_evaluacion as re_
from app.application.ml import resultados_informes as ri
from app.application.ml import resultados_procedencias as rp
from app.application.use_cases.carteras import CarterasError
from app.application.use_cases.laboratorio import JUEGOS, NOMBRES, SLUGS, leer_historico
from app.application.use_cases.operacion_diaria import mensaje_legible

POR_PAGINA = 25
MAXIMO_POR_PAGINA = 200
POLITICA = ("Una emisión por procedencia, línea y objetivo: la primera según el orden sellado de su procedencia "
            "(nunca la fecha, el nombre del archivo ni la versión con más aciertos). Si la primera no es evaluable, "
            "el objetivo se excluye sin sustituirla por otra versión.")
UNIDADES = {
    "log_loss": "Log Loss media por objetivo (números: binaria por número candidato; ColorLoto: por balota); menor es mejor",
    "brier": "Brier medio por objetivo (mismas filas que el Log Loss); menor es mejor",
    "log_loss_multiconjunto": "Log Loss del multiconjunto de 6 pares de ColorLoto (aparte del Log Loss por balota)",
    "diferencia": "pérdida del modelo − pérdida de la uniforme del mismo artefacto y objetivo (negativa = menor pérdida)",
    "aciertos": "números (0-5) o pares con multiplicidad (0-6) de la sugerencia de la emisión; el vector fuente de "
                "Producto 5 no tiene sugerencia propia (ver carteras)",
    "superbalota": "Log Loss y Brier multiclase de la superbalota, aparte; nunca se suma a los números",
    "denominador": "objetivos incluidos de la línea (o de la muestra común en la comparación directa)",
}
COLUMNAS_CSV = ("juego", "procedencia", "linea", "nombre_linea", "objetivo", "tipo", "integridad",
                "historico_hasta_el_corte", "resultado_observado", "estado", "motivo", "fecha_sorteo", "identificador",
                "aciertos", "de", "log_loss", "log_loss_uniforme", "diferencia_log_loss", "brier", "brier_uniforme",
                "log_loss_multiconjunto", "log_loss_multiconjunto_uniforme", "superbalota_acierto",
                "superbalota_log_loss", "superbalota_log_loss_uniforme", "universo", "carteras_que_usan_el_vector")


class ResultadosError(Exception):
    def __init__(self, codigo: str, mensaje: str):
        super().__init__(mensaje)
        self.codigo = codigo


@dataclass(frozen=True)
class Filtros:
    procedencias: tuple[str, ...] = rp.PROCEDENCIAS
    lineas: tuple[str, ...] = ()
    tipo: str = "seguimiento"
    desde: int | None = None
    hasta: int | None = None
    objetivo: int | None = None
    carteras: tuple[str, ...] = field(default_factory=tuple)

    def validar(self) -> "Filtros":
        procedencias = tuple(p for p in rp.PROCEDENCIAS if p in self.procedencias)
        if not procedencias or set(self.procedencias) - set(rp.PROCEDENCIAS):
            raise ResultadosError("no_valido", "procedencias admitidas: " + ", ".join(rp.PROCEDENCIAS))
        if self.tipo not in rp.TIPOS:
            raise ResultadosError("no_valido", "tipo admitido: seguimiento o retrospectiva")
        for valor in (self.desde, self.hasta, self.objetivo):
            if valor is not None and (not isinstance(valor, int) or isinstance(valor, bool) or valor < 1):
                raise ResultadosError("no_valido", "los objetivos son numeros de sorteo positivos")
        if self.desde is not None and self.hasta is not None and self.desde > self.hasta:
            raise ResultadosError("no_valido", "el intervalo de objetivos esta invertido (desde > hasta)")
        return Filtros(procedencias, tuple(dict.fromkeys(self.lineas)), self.tipo, self.desde, self.hasta,
                       self.objetivo, tuple(dict.fromkeys(self.carteras)))

    def como_dict(self) -> dict:
        d = asdict(self)
        return {k: list(v) if isinstance(v, tuple) else v for k, v in d.items()}

    @staticmethod
    def desde_dict(d: dict) -> "Filtros":
        return Filtros(tuple(d.get("procedencias") or rp.PROCEDENCIAS), tuple(d.get("lineas") or ()),
                       d.get("tipo", "seguimiento"), d.get("desde"), d.get("hasta"), d.get("objetivo"),
                       tuple(d.get("carteras") or ())).validar()

    def admite_objetivo(self, objetivo: int) -> bool:
        if self.objetivo is not None:
            return objetivo == self.objetivo
        return (self.desde is None or objetivo >= self.desde) and (self.hasta is None or objetivo <= self.hasta)


def _validar_juego(juego: str) -> None:
    if juego not in JUEGOS:
        raise ResultadosError("no_valido", f"juego no admitido: {juego!r}; admitidos: {', '.join(JUEGOS)}")


def _sin_congelado(fila: dict) -> dict:
    return {k: v for k, v in fila.items() if k != "congelado"}


class CentroDeResultados:
    def __init__(self, pronosticos, laboratorio, carteras, informes, abrir, *, carteras_servicio=None, reloj=None):
        """`carteras_servicio`: fabrica (sin argumentos) del caso de uso de
        Producto 5; solo se usa para «usar esta configuracion»."""
        self._pronosticos = pronosticos
        self._laboratorio = laboratorio
        self._carteras = carteras
        self._informes = informes
        self._abrir = abrir
        self._carteras_servicio = carteras_servicio
        self._reloj = reloj or (lambda: datetime.now(timezone.utc).replace(microsecond=0))

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------

    def _leer_base(self, juego: str):
        try:
            with self._abrir() as lectura:
                completo = list(leer_historico(lectura, juego))
        except Exception as error:  # base no disponible: lo guardado se sigue consultando
            return None, {"estado": "no_disponible", "motivo": mensaje_legible(error), "ultimo_sorteo": None,
                          "fecha": None, "sorteos": None}
        if not completo:
            return completo, {"estado": "consultada", "motivo": "no hay sorteos cargados", "ultimo_sorteo": None,
                              "fecha": None, "sorteos": 0}
        ultimo = max(completo, key=lambda r: r.numero_sorteo)
        return completo, {"estado": "consultada", "motivo": None, "ultimo_sorteo": ultimo.numero_sorteo,
                          "fecha": ultimo.fecha.isoformat(), "sorteos": len(completo)}

    def _reunir(self, juego: str, completo, procedencias=rp.PROCEDENCIAS):
        slug = SLUGS[juego]
        lineas: dict[str, dict] = {}
        filas: list[dict] = []
        info: dict[str, dict] = {}
        carteras: dict = {}
        for p in rp.PROCEDENCIAS:
            info[p] = {"nombre": rp.NOMBRES_DE_PROCEDENCIA[p], "elegida": p in procedencias, "estado": "no_elegida",
                       "lineas": 0, "emisiones": 0, "ilegibles": 0, "error": None}
            if p not in procedencias:
                continue
            try:
                if p == "operacion":
                    elementos = self._pronosticos.listar(juego)
                    objetivos = getattr(self._pronosticos, "objetivos_de_archivos", lambda _c: {})(juego)
                    metas, propias = rp.emisiones_operacion(juego, elementos, objetivos, completo, slug)
                    info[p]["ilegibles"] = sum(1 for e in elementos if not hasattr(e, "artefacto"))
                    flujo = f"/pronosticos/{slug}"
                elif p == "laboratorio":
                    por_linea = {nombre: self._laboratorio.pronosticos(juego, nombre)
                                 for nombre in self._laboratorio.lineas(juego)}
                    metas, propias = rp.emisiones_laboratorio(juego, por_linea, completo)
                    info[p]["ilegibles"] = sum(1 for v in por_linea.values() for e in v if not hasattr(e, "artefacto"))
                    flujo = f"/laboratorio/{slug}"
                else:
                    por_linea = {nombre: self._carteras.carteras(juego, nombre)
                                 for nombre in self._carteras.lineas(juego)}
                    seguimientos = rp.seguimientos_de_carteras(por_linea, completo)
                    metas, propias = rp.emisiones_carteras(juego, seguimientos, completo)
                    carteras = rp.carteras_de_juego(seguimientos)
                    info[p]["ilegibles"] = sum(1 for v in por_linea.values() for e in v if not hasattr(e, "artefacto"))
                    flujo = f"/carteras/{slug}"
            except (OSError, ValueError, KeyError) as error:
                info[p].update(estado="error", error=f"no se pudo leer: {mensaje_legible(error)}")
                continue
            for nombre, meta in metas.items():
                clave = rp.clave_de_linea(p, nombre)
                lineas[clave] = {"clave": clave, "procedencia": p, "linea": nombre,
                                 "nombre": meta.get("nombre", nombre), "metadatos": meta, "enlace_flujo": flujo}
            filas.extend(propias)
            info[p].update(estado="con_lineas" if metas else "sin_artefactos", lineas=len(metas),
                           emisiones=len(propias))
        return lineas, filas, info, carteras

    # ------------------------------------------------------------------
    # Indice
    # ------------------------------------------------------------------

    def indice(self) -> dict:
        juegos = []
        for juego in JUEGOS:
            completo, base = self._leer_base(juego)
            _, filas, info, _ = self._reunir(juego, completo)
            de_seguimiento = [f for f in filas if f["tipo"] == "seguimiento"]
            juegos.append({
                "juego": juego, "nombre": NOMBRES[juego], "slug": SLUGS[juego], "base": base,
                "seguimiento": {estado: sum(1 for f in de_seguimiento if f["estado"] == estado)
                                for estado in ("incluido", "pendiente", "excluido", "sin_base")},
                "objetivos_de_seguimiento": len({f["objetivo"] for f in de_seguimiento}),
                "procedencias": info})
        return {"juegos": juegos, "estado_de_uso": ri.ESTADO_DE_USO, "nota_seguimiento": rp.NOTA_SEGUIMIENTO,
                "nota": "Cifras de la consulta actual: cambian al cargar sorteos o al emitir nuevos artefactos."}

    # ------------------------------------------------------------------
    # Consulta
    # ------------------------------------------------------------------

    def consultar(self, juego: str, filtros: Filtros | None = None, pagina: int = 1, por_pagina: int = POR_PAGINA,
                  completa: bool = False) -> dict:
        _validar_juego(juego)
        filtros = (filtros or Filtros()).validar()
        if pagina < 1 or not 1 <= por_pagina <= MAXIMO_POR_PAGINA:
            raise ResultadosError("no_valido", f"pagina >= 1 y por_pagina entre 1 y {MAXIMO_POR_PAGINA}")
        completo, base = self._leer_base(juego)
        lineas, filas, info, carteras = self._reunir(juego, completo, filtros.procedencias)
        fuera = [c for c in filtros.lineas if c.split(":", 1)[0] in rp.PROCEDENCIAS
                 and c.split(":", 1)[0] not in filtros.procedencias]
        if fuera:
            raise ResultadosError("no_valido", "lineas de una procedencia no elegida (marca su procedencia o quita la "
                                               "linea): " + ", ".join(fuera))
        desconocidas = [c for c in filtros.lineas if c not in lineas]
        if desconocidas:
            raise ResultadosError("no_valido", "lineas desconocidas para este juego: " + ", ".join(desconocidas))
        vista = [f for f in filas if rp.de_tipo(f, filtros.tipo) and filtros.admite_objetivo(f["objetivo"])]
        por_linea: dict[str, list] = {clave: [] for clave in lineas}
        for f in vista:
            por_linea.setdefault(f["clave_linea"], []).append(f)
        resumenes = {clave: re_.agregado(v, juego) for clave, v in por_linea.items()}
        seleccion = list(filtros.lineas) or self._seleccion_por_defecto(lineas, resumenes)
        comparacion = re_.comparar(seleccion, por_linea, juego, filtros.tipo)
        evolucion = {clave: a["serie"] for clave, a in comparacion["por_linea"].items()}
        calibracion = {clave: rc.diagnostico(por_linea.get(clave, [])) for clave in seleccion}
        orden = {p: i for i, p in enumerate(rp.PROCEDENCIAS)}
        de_la_seleccion = sorted((f for clave in seleccion for f in por_linea.get(clave, [])),
                                 key=lambda f: (-f["objetivo"], orden[f["procedencia"]], f["clave_linea"]))
        total = len(de_la_seleccion)
        paginas = max(1, -(-total // por_pagina))
        pagina = min(pagina, paginas)
        inicio = (pagina - 1) * por_pagina
        sin_seguimiento = (filtros.tipo == "seguimiento"
                           and not any(f["estado"] == "incluido" for f in vista))
        salida = {
            "juego": juego, "nombre": NOMBRES[juego], "slug": SLUGS[juego], "estado_de_uso": ri.ESTADO_DE_USO,
            "contexto": ri.contexto(), "filtros": filtros.como_dict(), "base": base, "procedencias": info,
            "politica": POLITICA, "nota_seguimiento": rp.NOTA_SEGUIMIENTO, "signo": re_.SIGNO, "unidades": UNIDADES,
            "lineas": sorted(lineas.values(), key=lambda m: (orden[m["procedencia"]], m["nombre"], m["clave"])),
            "seleccion": seleccion, "resumenes": resumenes, "comparacion": comparacion, "evolucion": evolucion,
            "calibracion": calibracion,
            "historial": {"filas": [_sin_congelado(f) for f in de_la_seleccion[inicio:inicio + por_pagina]],
                          "total": total, "pagina": pagina, "paginas": paginas, "por_pagina": por_pagina},
            "carteras": (self._seccion_de_carteras(carteras, filtros, completa) if "carteras" in filtros.procedencias
                         else None),
            "sin_resultados_de_seguimiento": sin_seguimiento,
        }
        if completa:
            salida["emisiones_de_la_seleccion"] = de_la_seleccion
        return salida

    @staticmethod
    def _seleccion_por_defecto(lineas: dict, resumenes: dict) -> list[str]:
        seleccion = []
        for p in rp.PROCEDENCIAS:
            propias = [c for c, m in lineas.items() if m["procedencia"] == p]
            if propias:
                seleccion.append(min(propias, key=lambda c: (-resumenes[c]["incluidos"], c)))
        return seleccion

    @staticmethod
    def _seccion_de_carteras(carteras: dict, filtros: Filtros, completa: bool = False) -> dict:
        """`completa`: conserva en cada fila incluida las combinaciones congeladas (para el informe)."""
        elegidas = list(filtros.carteras) or sorted(carteras)
        desconocidas = [c for c in elegidas if c not in carteras]
        if desconocidas:
            raise ResultadosError("no_valido", "carteras desconocidas para este juego: " + ", ".join(desconocidas))
        lineas = {}
        for nombre in elegidas:
            c = carteras[nombre]
            filas = [f if completa else _sin_congelado(f) for f in c["filas"]
                     if f.get("tipo") in (filtros.tipo, *rp.SIN_TIPO) and filtros.admite_objetivo(f["objetivo"])]
            lineas[nombre] = {"linea": nombre, "metadatos": c["metadatos"], "filas": filas,
                              "resumen": re_.resumen_de_cartera(filas)}
        relacion: dict[str, list] = {}
        for nombre, c in carteras.items():
            meta = c["metadatos"]
            if meta:
                sufijo = "" if meta["perfil"] == "predeterminado" else f"-{meta['perfil']}"
                relacion.setdefault(f"{meta['modelo']}-v{meta['version']}{sufijo}", []).append(nombre)
        return {"lineas": lineas, "disponibles": sorted(carteras),
                "comparacion": re_.comparar_carteras(lineas, list(lineas), filtros.tipo),
                "relacion_modelo_carteras": {k: sorted(v) for k, v in sorted(relacion.items())},
                "nota": ("Aciertos observados de las combinaciones: máximo por cartera, superbalota aparte y "
                         "multiplicidades en ColorLoto. No se mezclan con el Log Loss del vector ni con "
                         "frecuencias simuladas.")}

    # ------------------------------------------------------------------
    # Exportaciones (conjunto filtrado completo)
    # ------------------------------------------------------------------

    def exportar_json(self, juego: str, filtros: Filtros | None = None) -> dict:
        vista = self.consultar(juego, filtros, completa=True)
        emisiones = [_sin_congelado(f) for f in vista.pop("emisiones_de_la_seleccion")]
        vista.pop("historial")
        if vista["carteras"]:
            for c in vista["carteras"]["lineas"].values():
                c["filas"] = [_sin_congelado(f) for f in c["filas"]]
        return {**vista, "emisiones": emisiones,
                "nota_exportacion": "Todas las emisiones de las líneas elegidas con los filtros aplicados (no solo "
                                    "la página visible)."}

    def exportar_csv(self, juego: str, filtros: Filtros | None = None) -> str:
        vista = self.consultar(juego, filtros, completa=True)
        nombres = {m["clave"]: m["nombre"] for m in vista["lineas"]}
        salida = io.StringIO()
        escritor = csv.writer(salida, lineterminator="\r\n")
        escritor.writerow(COLUMNAS_CSV)
        for f in vista["emisiones_de_la_seleccion"]:
            m = f["metricas"] or {}
            sb = f["superbalota"] or {}
            escritor.writerow([
                _texto(f["juego"]), _texto(f["procedencia"]), _texto(f["clave_linea"]), _texto(nombres.get(f["clave_linea"])),
                f["objetivo"], _texto(f["tipo"]), _texto(f["integridad"]), _texto(f["historico"]),
                _texto(f["resultado_estado"]), _texto(f["estado"]), _texto(f["motivo"]), _texto(f["fecha_sorteo"]),
                _texto(f["identificador"]), _numero(f["aciertos"]), _numero(f["de"]), _numero(m.get("log_loss")),
                _numero(m.get("log_loss_uniforme")),
                _numero(m["log_loss"] - m["log_loss_uniforme"] if m else None), _numero(m.get("brier")),
                _numero(m.get("brier_uniforme")), _numero(m.get("log_loss_multiconjunto")),
                _numero(m.get("log_loss_multiconjunto_uniforme")),
                _texto(None if not sb else ("si" if sb.get("acierto") else "no")), _numero(sb.get("log_loss")),
                _numero(sb.get("log_loss_uniforme")), _texto((f["universo"] or {}).get("descripcion")),
                _texto(";".join(u["linea"] for u in f["carteras"] or []))])
        return salida.getvalue()

    # ------------------------------------------------------------------
    # Informes guardados
    # ------------------------------------------------------------------

    def guardar_informe(self, juego: str, filtros: Filtros | None = None, origen: str = "web") -> dict:
        vista = self.consultar(juego, filtros, completa=True)
        cuerpo = ri.cuerpo_de_informe(vista)
        artefacto = ri.componer(cuerpo, {"guardado_en": self._reloj().isoformat(), "origen": origen,
                                         "nota": "fecha del reloj local; no prueba anterioridad"})
        try:
            guardado = self._informes.guardar(artefacto)
        except FileExistsError as error:
            raise ResultadosError("alterado", str(error)) from error
        return {"clave": guardado.clave, "juego": juego, "reutilizado": guardado.reutilizado,
                "estado": guardado.artefacto["estado"], "limitaciones": guardado.artefacto["limitaciones"]}

    def informes(self, juego: str) -> list[dict]:
        _validar_juego(juego)
        salida = []
        for e in self._informes.listar(juego):
            if hasattr(e, "artefacto"):
                a = e.artefacto
                salida.append({"clave": e.clave, "estado": a["estado"], "tipo": a["filtros"]["tipo"],
                               "lineas": len(a["seleccion"]), "guardado_en": a["guardado"]["guardado_en"],
                               "integridad": "correcta"})
            else:
                salida.append({"clave": e.clave, "estado": "ilegible", "integridad": e.motivo})
        return salida

    def informe(self, clave: str) -> dict:
        e = self._informes.obtener(clave)
        if e is None:
            raise ResultadosError("no_encontrado", "No hay un informe con esa clave")
        if not hasattr(e, "artefacto"):
            raise ResultadosError("alterado", f"El informe {clave} no supera la comprobacion de integridad: {e.motivo}")
        return e.artefacto

    def verificar_informe(self, clave: str) -> dict:
        e = self._informes.obtener(clave)
        if e is None:
            raise ResultadosError("no_encontrado", "No hay un informe con esa clave")
        if not hasattr(e, "artefacto"):
            return {"clave": clave, "integridad": "alterado", "motivo": e.motivo,
                    "reproduccion": {"exacta": None, "motivo": "no se evalua un archivo alterado"},
                    "base_actual": {"estado": "no_evaluado", "motivo": "no se evalua un archivo alterado"}}
        a = e.artefacto
        reproduccion = ri.reproducir(a)
        try:
            actual = self.consultar(a["juego"], Filtros.desde_dict(a["filtros"]), completa=True)
        except ResultadosError as error:
            base = {"estado": "no_comparable", "motivo": str(error), "diferencias": []}
        else:
            base = ri.comparar_con_consulta(a, actual)
        return {"clave": clave, "juego": a["juego"], "integridad": "correcta", "reproduccion": reproduccion,
                "base_actual": base,
                "nota": "Integridad, reproducción del cálculo congelado y coincidencia con la consulta actual son "
                        "comprobaciones distintas; una huella local no es una firma externa."}

    # ------------------------------------------------------------------
    # Usar esta configuracion (Producto 5)
    # ------------------------------------------------------------------

    def propuesta_de_configuracion(self, juego: str, linea_cartera: str, _servicio=None) -> dict:
        """Vista previa (lectura): parametros de la cartera, compatibilidad con
        la receta actual y configuracion vigente. No escribe."""
        _validar_juego(juego)
        if linea_cartera not in self._carteras.lineas(juego):
            raise ResultadosError("no_encontrado", f"No hay carteras de la linea {linea_cartera}")
        artefacto = next((e.artefacto for e in self._carteras.carteras(juego, linea_cartera)
                          if hasattr(e, "artefacto")), None)
        if artefacto is None:
            raise ResultadosError("alterado", "La linea solo tiene carteras ilegibles: no se propone su configuracion")
        from app.application.ml import carteras_artefactos as ca

        l = artefacto["linea"]
        propuesta = {"juego": juego, "modelo": l["modelo"], "version_del_modelo": str(l["version"]),
                     "perfil": l.get("perfil", "predeterminado"), "cantidad": l["cantidad"],
                     "diversidad": l["diversidad"], "semilla": l["semilla"], "linea": l["id"],
                     "nombre": (artefacto.get("modelo") or {}).get("nombre", l["modelo"])}
        try:
            receta = ca.receta_del_modelo(juego, l["modelo"], propuesta["perfil"])
        except (KeyError, ValueError) as error:
            return {"propuesta": propuesta, "compatible": False, "motivo": f"modelo no disponible: {error}",
                    "vigente": None, "ya_vigente": False}
        compatible = str(receta["version"]) == propuesta["version_del_modelo"]
        vigente = None
        servicio = _servicio or (self._carteras_servicio() if self._carteras_servicio else None)
        if servicio is not None:
            try:
                g = servicio.configuracion_vigente(juego)
            except CarterasError as error:
                raise ResultadosError(error.codigo, str(error)) from error
            vigente = None if g is None else {
                "version_de_configuracion": g.artefacto["version"], "modelo": g.artefacto["modelo"]["id"],
                "version_del_modelo": str(g.artefacto["modelo"]["version"]),
                **{k: g.artefacto[k] for k in ("perfil", "cantidad", "diversidad", "semilla", "linea")}}
        ya_vigente = vigente is not None and vigente["linea"] == propuesta["linea"]
        return {"propuesta": propuesta, "compatible": compatible, "vigente": vigente, "ya_vigente": ya_vigente,
                "motivo": None if compatible else
                ("la versión del modelo de esa cartera ya no es la actual: se configuraría otra línea")}

    def usar_configuracion(self, juego: str, linea_cartera: str, origen: str = "web") -> dict:
        if self._carteras_servicio is None:
            raise ResultadosError("no_disponible", "el servicio de carteras no esta disponible")
        servicio = self._carteras_servicio()
        datos = self.propuesta_de_configuracion(juego, linea_cartera, servicio)
        if not datos["compatible"]:
            raise ResultadosError("no_valido", datos["motivo"])
        if datos["ya_vigente"]:
            return {"estado": "ya_vigente", "version": datos["vigente"]["version_de_configuracion"],
                    "linea": datos["vigente"]["linea"]}
        p = datos["propuesta"]
        try:
            g = servicio.configurar(juego, p["modelo"], p["cantidad"], p["diversidad"], p["semilla"], p["perfil"],
                                    origen)
        except CarterasError as error:
            raise ResultadosError(error.codigo, str(error)) from error
        return {"estado": "guardada", "version": g.artefacto["version"], "linea": g.artefacto["linea"]}


def _texto(valor) -> str:
    """Texto de archivos o almacenes: nunca empieza como una formula de hoja de calculo."""
    texto = "" if valor is None else str(valor)
    return "'" + texto if texto[:1] in ("=", "+", "-", "@", "\t", "\r") else texto


def _numero(valor) -> str:
    return "" if valor is None else repr(valor) if isinstance(valor, float) else str(valor)


__all__ = ["CentroDeResultados", "Filtros", "ResultadosError", "JUEGOS", "NOMBRES", "SLUGS", "POR_PAGINA"]

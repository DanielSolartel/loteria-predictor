"""
Fase 4: centro de predicciones de los cuatro juegos — el caso de uso comun
`GenerarPredicciones` para la web, la API y el comando
`python -m scripts.predicciones`.

COORDINA, NO DUPLICA:
- la ELECCION del operador es la configuracion vigente de Producto 5 (modelo,
  version de la receta, version registrada, perfil, cantidad, diversidad y
  semilla). El centro nunca cambia de modelo porque otro haya ganado una
  evaluacion, ni guarda configuraciones;
- GENERAR es un trabajo `cartera` del caso de uso de Producto 5 con los
  parametros de esa configuracion (mismo cerrojo por juego, mismo registro de
  progreso, misma identidad y misma reutilizacion). Una version registrada se
  recarga con las comprobaciones de integridad y compatibilidad de la Fase 3,
  sin reentrenar. «Cinco combinaciones» es una peticion explicita aparte: usa
  la misma configuracion con cantidad 5 y no la sobrescribe;
- EXPLICAR anade a la cartera publicada una explicacion versionada e inmutable
  (rankings, variables de los candidatos y, si hay estimador persistido, sus
  importancias globales, calculadas en el proceso trabajador del laboratorio
  con la carga restringida). Nunca reajusta un estimador;
- la FIABILIDAD lee las emisiones congeladas de Producto 6 y los informes del
  laboratorio con el contrato de `predicciones_fiabilidad`.

LECTURA PURA en `indice`, `consultar`, `fiabilidad` y `ejecucion`: no
entrenan, no importan, no generan, no inician trabajadores ni escriben. Solo
`iniciar`/`ejecutar`/`ahora` (generar) y `explicar` escriben, y solo cuando se
piden explicitamente.

RECUPERACION. Cada generacion toma su propio cerrojo de ejecucion (el mismo
mecanismo que Productos 3 y 5) desde `iniciar` hasta que `ejecutar` termina,
incluida la explicacion: que Carteras haya terminado y soltado sus cerrojos
no significa que la generacion haya muerto. Si Carteras lanza una excepcion
(p. ej. no pudo registrar su progreso tras publicar la cartera), el registro
propio se cierra como `fallo` con su motivo, y lo ya publicado se busca y se
valida en el almacen de Carteras (solo lectura). Una generacion registrada
«en curso» cuyo cerrojo nadie tiene no tiene trabajador: `ejecucion` la
muestra interrumpida, con los juegos de Carteras que quedaron a medias como
interrumpidos y su cartera, si se publico y se verifica, sin escribir nada.
Repetir la misma entrada reutiliza esa cartera (identidad de Producto 5) y
completa la explicacion, sin reentrenar.

Siguen `experimental_no_acreditado`, el NO-GO de AE-39 y
`AUTORIZA_EVALUACION = False`.
"""
from __future__ import annotations

import errno
import copy
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.application.interfaces.ejecutor_laboratorio import TrabajadorFallidoError
from app.application.interfaces.laboratorio_store import GuardadoModelo
from app.application.interfaces.predicciones_store import ExplicacionGuardada
from app.application.ml import carteras_artefactos as ca
from app.application.ml import modelos_registrados as mr
from app.application.ml import predicciones_explicacion as pe
from app.application.ml import predicciones_fiabilidad as pf
from app.application.ml import resultados_procedencias as rp
from app.application.use_cases.carteras import JUEGOS, NOMBRES, SLUGS, CarterasDeModelos, CarterasError, Inicio
from app.application.use_cases.operacion_diaria import mensaje_legible

CANTIDADES = ("configuracion", "cinco")
ESTADO_DE_USO = "experimental_no_acreditado"
AVISO = ("Predicciones experimentales: describen lo que el modelo elegido estima con los sorteos hasta el corte. No "
         "son resultados garantizados ni una recomendación de apuesta, y no acreditan ventaja frente al azar.")
__all__ = ["CentroDePredicciones", "PrediccionesError", "InicioPrediccion", "JUEGOS", "NOMBRES", "SLUGS", "CANTIDADES"]


class PrediccionesError(Exception):
    """Error esperado con un codigo estable (`no_valido`, `no_encontrado`,
    `sin_configuracion`, `alterado`, `incompatible`, `no_disponible`,
    `fallo_del_trabajador`)."""

    def __init__(self, codigo: str, mensaje: str):
        self.codigo = codigo
        super().__init__(mensaje)


@dataclass
class InicioPrediccion:
    cartera: Inicio
    juego: str
    solicitud: dict = field(default_factory=dict)
    cerrojo: object | None = None  # cerrojo de ejecucion del centro (hasta el final de `ejecutar`)

    @property
    def identificador(self) -> str:
        return self.cartera.ejecucion["id"]


def _ahora() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _validar_juego(juego: str) -> None:
    if juego not in JUEGOS:
        raise PrediccionesError("no_valido", f"juego no admitido: {juego!r}; admitidos: {', '.join(JUEGOS)}")


def linea_de_modelo(configuracion: dict) -> str:
    """Linea de MODELO de Producto 6 (vector fuente) de una configuracion."""
    perfil = configuracion["perfil"]
    registrado = configuracion["modelo"].get("registrado")
    reg = "" if not registrado else f"-reg{registrado['numero']}"
    sufijo = "" if perfil == "predeterminado" else f"-{perfil}"
    return f"{configuracion['modelo']['id']}-v{configuracion['modelo']['version']}{reg}{sufijo}"


class CentroDePredicciones:
    def __init__(self, carteras: CarterasDeModelos, resultados, almacen, modelos, ejecutor, registro, *, cerrojo,
                 reloj: Callable[[], datetime] = _ahora):
        """`carteras`: caso de uso de Producto 5 (genera y lee carteras y
        configuraciones). `resultados`: centro de Producto 6 (solo lectura).
        `almacen`: explicaciones de la Fase 4. `modelos`: almacen del
        laboratorio (manifiestos, estimadores e informes; solo lectura).
        `ejecutor`: proceso trabajador del laboratorio (importancias con la
        carga restringida). `registro`: pasos de cada generacion del centro.
        `cerrojo`: cerrojos de ejecucion del centro (`CerrojoPorJuego` de su
        carpeta de operacion): dicen si una generacion tiene trabajador."""
        self._carteras = carteras
        self._resultados = resultados
        self._almacen = almacen
        self._modelos = modelos
        self._ejecutor = ejecutor
        self._registro = registro
        self._cerrojo = cerrojo
        self._reloj = reloj

    # ------------------------------------------------------------------
    # Configuracion del operador (lectura)
    # ------------------------------------------------------------------

    def _configuracion(self, juego: str) -> dict:
        try:
            g = self._carteras.configuracion_vigente(juego)
        except CarterasError as error:
            return {"estado": "alterada", "mensaje": str(error), "artefacto": None}
        if g is None:
            return {"estado": "sin_configuracion", "artefacto": None,
                    "mensaje": f"{NOMBRES[juego]} no tiene una configuración guardada: elígela en /carteras/{SLUGS[juego]}"}
        return {"estado": "vigente", "artefacto": g.artefacto, "mensaje": None}

    def _registrado(self, configuracion: dict | None) -> dict | None:
        """Version registrada de la configuracion: manifiesto y compatibilidad
        (sin deserializar el estimador)."""
        ref = ((configuracion or {}).get("modelo") or {}).get("registrado")
        if not ref:
            return None
        guardado = self._modelos.obtener_modelo(ref["clave"]) if self._modelos is not None else None
        if guardado is None:
            return {**ref, "estado": "no_encontrado", "motivo": "el almacén del laboratorio no tiene esa versión"}
        if not isinstance(guardado, GuardadoModelo):
            return {**ref, "estado": "alterado", "motivo": guardado.motivo}
        compat = mr.compatibilidad(guardado.artefacto)
        return {**ref, "estado": "compatible" if compat["compatible"] else "incompatible", "motivos": compat["motivos"],
                "resumen": mr.resumen(guardado.artefacto), "linea_de_laboratorio": mr.linea_registrada(guardado.artefacto)["id"],
                "experimento": guardado.artefacto["procedencia"]["experimento"]}

    @staticmethod
    def _parametros(configuracion: dict, cantidad: str) -> dict:
        if cantidad not in CANTIDADES:
            raise PrediccionesError("no_valido", f"cantidad admitida: {', '.join(CANTIDADES)}")
        c = configuracion
        p = {"modelo": c["modelo"]["id"], "perfil": c["perfil"], "cantidad": c["cantidad"],
             "diversidad": c["diversidad"], "semilla": c["semilla"]}
        if c["modelo"].get("registrado"):
            p["registrado"] = c["modelo"]["registrado"]["clave"]
        if cantidad == "cinco" and c["cantidad"] != 5:
            p["cantidad"] = 5
        else:
            p["configuracion"] = {"version": c["version"], "linea": c["linea"]}
        return p

    def lineas_del_centro(self, configuracion: dict) -> dict:
        """Lineas de cartera del centro: la de la configuracion y, si pide otra
        cantidad, la variante de cinco combinaciones (misma receta)."""
        c = configuracion
        registrado = c["modelo"].get("registrado")
        cinco = ca.linea_de(c["juego"], c["modelo"]["id"], c["perfil"], 5, c["diversidad"], c["semilla"],
                            registrado)["id"]
        return {"configuracion": c["linea"], "cinco": cinco}

    # ------------------------------------------------------------------
    # Generar (escribe: cartera de Producto 5 y explicacion)
    # ------------------------------------------------------------------

    def iniciar(self, juego: str, cantidad: str = "configuracion", origen: str = "web", *,
                configuracion_congelada: dict | None = None,
                guardia_publicacion: Callable[[], None] | None = None) -> InicioPrediccion:
        _validar_juego(juego)
        if configuracion_congelada is None:
            conf = self._configuracion(juego)
        else:
            # Se admite una version elegida y guardada anteriormente aunque el
            # usuario haya seleccionado otra despues de iniciar el ciclo.
            congelada = copy.deepcopy(configuracion_congelada)
            if congelada.get("juego") != juego or not ca.integro(congelada):
                raise PrediccionesError("alterado", "La configuracion congelada no es integra o pertenece a otro juego")
            versiones = self._carteras.configuraciones(juego)
            coincide = any(getattr(g, "artefacto", None) == congelada for g in versiones)
            if not coincide:
                raise PrediccionesError("alterado", "La configuracion congelada no coincide con una version guardada")
            conf = {"estado": "vigente", "artefacto": congelada, "mensaje": None}
        if conf["estado"] != "vigente":
            raise PrediccionesError("sin_configuracion" if conf["estado"] == "sin_configuracion" else "alterado",
                                    conf["mensaje"])
        parametros = self._parametros(conf["artefacto"], cantidad)
        try:
            if guardia_publicacion is None:
                inicio = self._carteras.iniciar("cartera", [juego], parametros, origen)
            else:
                inicio = self._carteras.iniciar("cartera", [juego], parametros, origen,
                                                guardia_publicacion=guardia_publicacion)
        except CarterasError as error:
            raise PrediccionesError(error.codigo, str(error)) from error
        try:
            cerrojo = self._cerrojo.adquirir((), inicio.ejecucion["id"])  # solo el de la ejecucion
            if isinstance(cerrojo, dict):  # sin juegos no hay contencion; por si acaso
                raise OSError(errno.EBUSY, f"el cerrojo de la generacion {inicio.ejecucion['id']} ya esta tomado")
        except BaseException:
            self._carteras.abortar(inicio, "no se pudo tomar el cerrojo de la prediccion")
            raise
        solicitud = {"cantidad": cantidad, "combinaciones": parametros["cantidad"],
                     "configuracion": {"version": conf["artefacto"]["version"], "linea": conf["artefacto"]["linea"],
                                       "cantidad": conf["artefacto"]["cantidad"]}}
        registro = {"id": inicio.ejecucion["id"], "tipo": "prediccion", "juego": juego, "origen": origen,
                    "estado": "en_curso", "fase": "cartera", "iniciada_en": self._reloj().isoformat(),
                    "finalizada_en": None, "solicitud": solicitud, "cartera": None, "explicacion": None}
        try:
            self._registro.guardar(registro)
        except BaseException:
            cerrojo.liberar()
            self._carteras.abortar(inicio, "no se pudo registrar la prediccion")
            raise
        return InicioPrediccion(inicio, juego, solicitud, cerrojo)

    def abortar(self, inicio: InicioPrediccion, motivo: str) -> None:
        """El trabajo no llego a lanzarse (p. ej. no se pudo crear el hilo): libera
        los cerrojos de Producto 5 y cierra tambien el registro propio con un
        estado terminal, su motivo y su fecha (nunca queda «en curso»)."""
        try:
            self._carteras.abortar(inicio.cartera, motivo)
        finally:
            try:
                registro = self._registro.obtener(inicio.identificador) or {"id": inicio.identificador,
                                                                            "juego": inicio.juego}
                registro.update(estado="interrumpida", fase="interrumpida", finalizada_en=self._reloj().isoformat(),
                                mensaje=f"No se pudo iniciar el trabajo: {mensaje_legible(motivo)}")
                try:
                    self._registro.guardar(registro)
                except OSError:  # sin cerrojo, `ejecucion` la muestra interrumpida igualmente
                    pass
            finally:
                if inicio.cerrojo is not None:
                    inicio.cerrojo.liberar()

    def ejecutar(self, inicio: InicioPrediccion) -> dict:
        """Genera la cartera con Producto 5 y la explica. Mantiene el cerrojo
        de la generacion hasta el final; cualquier excepcion cierra el registro
        propio como `fallo` (si ese cierre tambien falla, el error se propaga y
        la generacion, ya sin cerrojo, se muestra interrumpida)."""
        try:
            try:
                ejecucion = self._carteras.ejecutar(inicio.cartera)  # libera los cerrojos al terminar
            except Exception as error:
                inicio.cartera.cerrojos.liberar()  # idempotente: Producto 5 ya los suelta en su `finally`
                return self._cerrar_con_fallo(inicio, error)
            try:
                return self._explicar_generada(inicio, ejecucion)
            except Exception as error:
                return self._cerrar_con_fallo(inicio, error, ejecucion)
        finally:
            if inicio.cerrojo is not None:
                inicio.cerrojo.liberar()

    def _explicar_generada(self, inicio: InicioPrediccion, ejecucion: dict) -> dict:
        r = ejecucion["juegos"][inicio.juego]
        registro = self._registro.obtener(inicio.identificador) or {"id": inicio.identificador, "juego": inicio.juego}
        registro.update(fase="explicacion", cartera={"estado": r["estado"], "clave": r.get("resultado"),
                                                     "mensaje": r.get("mensaje"), "linea": r.get("linea"),
                                                     "objetivo": r.get("objetivo")})
        if r["estado"] in ("terminado", "reutilizado"):
            self._registro.guardar(registro)
            try:
                e = self.explicar(r["resultado"], ejecucion.get("origen", "web"))
                registro["explicacion"] = {"estado": "reutilizada" if e["reutilizado"] else "guardada",
                                           "clave": e["clave"]}
            except PrediccionesError as error:
                registro["explicacion"] = {"estado": "fallo", "codigo": error.codigo, "motivo": str(error)}
            except Exception as error:  # p. ej. disco lleno: el registro nunca queda «en curso»
                registro["explicacion"] = {"estado": "fallo", "codigo": "fallo_inesperado",
                                           "motivo": mensaje_legible(error)}
        else:
            registro["explicacion"] = {"estado": "no_aplica",
                                       "motivo": f"la cartera terminó en «{r['estado']}»: no hay predicción que explicar"}
        bien = r["estado"] in ("terminado", "reutilizado") and registro["explicacion"]["estado"] != "fallo"
        registro.update(estado="exito" if bien else ("parcial" if r["estado"] in ("terminado", "reutilizado") else "fallo"),
                        fase="terminado", finalizada_en=self._reloj().isoformat())
        self._registro.guardar(registro)
        return {**ejecucion, "prediccion": registro}

    def _cerrar_con_fallo(self, inicio: InicioPrediccion, error: Exception, ejecucion: dict | None = None) -> dict:
        """Cierra el registro propio tras una excepcion. Lo ya publicado se
        busca y se valida en el almacen de Carteras (nunca se promociona un
        temporal ni se reescribe nada de Producto 5)."""
        almacen = isinstance(error, OSError)
        cartera = self._cartera_publicada(inicio.identificador, inicio.juego)
        cartera.update(estado="fallo", mensaje=f"{type(error).__name__}: {mensaje_legible(error)}")
        guardado = self._registro.obtener(inicio.identificador)
        registro = guardado if guardado and guardado.get("estado") != "ilegible" else {
            "id": inicio.identificador, "tipo": "prediccion", "juego": inicio.juego, "solicitud": inicio.solicitud}
        consejo = ("Lo ya publicado se conserva; repetir la misma entrada reutiliza la cartera y completa la explicación."
                   if cartera["publicada"] else "Repetir la misma entrada vuelve a intentarlo.")
        registro.update(estado="fallo", fase="terminado", finalizada_en=self._reloj().isoformat(),
                        codigo="almacen_no_disponible" if almacen else "fallo_inesperado", cartera=cartera,
                        explicacion=registro.get("explicacion") or {
                            "estado": "no_aplica", "motivo": "la generación se detuvo antes de explicar la cartera"},
                        mensaje=(f"La generación se detuvo: {cartera['mensaje']}. "
                                 + ("Fallo de almacenamiento (archivo bloqueado o no disponible). " if almacen else "")
                                 + consejo))
        self._registro.guardar(registro)
        base = ejecucion or {"id": inicio.identificador, "tipo": "cartera", "estado": "fallo", "juegos": {}}
        return {**base, "prediccion": registro}

    def _cartera_publicada(self, identificador: str, juego: str) -> dict:
        """Cartera que Producto 5 anoto para `juego` en la ejecucion (lectura)."""
        r = ((self._carteras.consultar_ejecucion(identificador) or {}).get("juegos") or {}).get(juego) or {}
        return self._cartera_anotada(r, juego)

    def _cartera_anotada(self, r: dict, juego: str) -> dict:
        """La cartera anotada en el progreso de un juego cuenta como publicada
        solo si existe en el almacen de Carteras, se verifica y es de ese juego."""
        clave = r.get("resultado")
        if r.get("tipo", "cartera") == "cartera" and isinstance(clave, str) and clave:
            try:
                g = self._carteras.cartera(clave)
            except CarterasError:
                g = None
            if g is not None and g.juego == juego:
                return {"publicada": True, "clave": clave, "linea": g.linea, "objetivo": g.objetivo}
        return {"publicada": False, "clave": None, "linea": r.get("linea"), "objetivo": r.get("objetivo")}

    def ahora(self, juego: str, cantidad: str = "configuracion", origen: str = "comando") -> dict:
        return self.ejecutar(self.iniciar(juego, cantidad, origen))

    def explicar(self, clave_cartera: str, origen: str = "web", juego: str | None = None) -> dict:
        """Publica (o reutiliza) la explicacion de una cartera guardada. Con una
        version registrada, sus importancias se leen del estimador persistido
        en el proceso trabajador; nunca se reajusta nada. `juego`: si se
        indica, la cartera debe ser de ese juego (se comprueba antes de
        escribir)."""
        try:
            guardada = self._carteras.cartera(clave_cartera)
        except CarterasError as error:
            raise PrediccionesError(error.codigo, str(error)) from error
        if juego is not None and guardada.juego != juego:
            raise PrediccionesError("no_valido", f"la cartera {clave_cartera[:12]} es de {guardada.juego}, no de {juego}")
        cartera = guardada.artefacto
        manifiesto = None
        ref = cartera["linea"].get("registrado")
        if ref:
            manifiesto, importancias = self._importancias_registradas(cartera, ref)
        else:
            importancias = pe.importancias_sin_estimador(cartera)
        try:
            cuerpo = pe.cuerpo_de_explicacion(cartera, importancias, manifiesto)
        except (KeyError, ValueError) as error:
            raise PrediccionesError("alterado", f"no se pudo construir la explicacion: {error}") from error
        artefacto = pe.componer(cuerpo, {"generado_en": self._reloj().isoformat(), "origen": origen,
                                         "nota": "reloj local de quien la generó; no prueba anterioridad"})
        try:
            guardado = self._almacen.guardar(artefacto)
        except FileExistsError as error:
            raise PrediccionesError("alterado", str(error)) from error
        return {"clave": guardado.clave, "cartera": clave_cartera, "juego": guardado.juego,
                "reutilizado": guardado.reutilizado, "importancias": guardado.artefacto["importancias"]["estado"]}

    def _importancias_registradas(self, cartera: dict, ref: dict) -> tuple[dict | None, dict]:
        guardado = self._modelos.obtener_modelo(ref["clave"]) if self._modelos is not None else None
        if not isinstance(guardado, GuardadoModelo):
            motivo = "no encontrada" if guardado is None else f"alterada o incompleta ({guardado.motivo})"
            return None, pe.no_disponible(f"la versión registrada {ref['clave'][:12]} está {motivo}: no se carga")
        manifiesto = guardado.artefacto
        esperado = ((cartera.get("identidad") or {}).get("modelo") or {}).get("registrado", {}).get("sha256_estimador")
        if esperado and esperado != manifiesto["estimador"]["sha256"]:
            raise PrediccionesError("alterado", "el estimador registrado no es el que usó la cartera")
        compat = mr.compatibilidad(manifiesto)
        if not compat["compatible"]:
            return manifiesto, pe.no_disponible("la versión registrada no se puede cargar en este entorno: "
                                                + "; ".join(compat["motivos"]))
        try:
            estimador = self._modelos.leer_estimador(guardado)
            return manifiesto, self._ejecutor.explicacion_registrada(manifiesto, estimador)
        except mr.ModeloRegistradoError as error:
            return manifiesto, pe.no_disponible(f"carga restringida rechazada ({error.estado}): {error.motivo}")
        except (TrabajadorFallidoError, OSError) as error:
            raise PrediccionesError("fallo_del_trabajador", f"no se pudieron leer las importancias: "
                                                            f"{mensaje_legible(error)}") from error

    # ------------------------------------------------------------------
    # Consulta (lectura pura)
    # ------------------------------------------------------------------

    def indice(self) -> dict:
        juegos = []
        for juego in JUEGOS:
            conf = self._configuracion(juego)
            diag = self._carteras.diagnostico(juego)
            ultima = None
            if conf["estado"] == "vigente":
                lineas = self.lineas_del_centro(conf["artefacto"])
                ultima = self._ultima(juego, lineas)
            juegos.append({"juego": juego, "nombre": NOMBRES[juego], "slug": SLUGS[juego], "configuracion": conf,
                           "registrado": self._registrado(conf["artefacto"]), "base": _base_de(diag),
                           "activa": diag.get("activa"), "ultima": ultima})
        return {"juegos": juegos, "aviso": AVISO, "estado_de_uso": ESTADO_DE_USO, "contexto": pe.contexto()}

    def _carteras_de(self, juego: str, linea: str) -> list:
        try:
            return self._carteras.carteras_de_linea(juego, linea)
        except CarterasError:
            return []

    def _ultima(self, juego: str, lineas: dict) -> dict | None:
        for nombre, linea in lineas.items():
            for e in self._carteras_de(juego, linea):
                if hasattr(e, "artefacto"):
                    return {**self._resumen_de_cartera(e), "linea_del_centro": nombre}
        return None

    def _resumen_de_cartera(self, guardada) -> dict:
        a = guardada.artefacto
        explicaciones = [x for x in self._almacen.de_cartera(a["juego"], guardada.identificador)
                         if isinstance(x, ExplicacionGuardada)]
        return {"clave": guardada.identificador, "linea": guardada.linea, "objetivo": a["cartera"]["objetivo"],
                "corte": a["datos"]["corte"], "combinaciones": len(a["cartera"]["combinaciones"]),
                "generado_en": (a.get("generacion") or {}).get("generado_en"),
                "tipo": ((a.get("generacion") or {}).get("clasificacion_temporal") or {}).get("tipo"),
                "version": guardada.version, "versiones": guardada.versiones,
                "explicacion": explicaciones[-1].clave if explicaciones else None}

    def consultar(self, juego: str, clave: str | None = None) -> dict:
        _validar_juego(juego)
        conf = self._configuracion(juego)
        diag = self._carteras.diagnostico(juego)
        registrado = self._registrado(conf["artefacto"])
        salida = {"juego": juego, "nombre": NOMBRES[juego], "slug": SLUGS[juego], "configuracion": conf,
                  "registrado": registrado, "base": _base_de(diag), "activa": diag.get("activa"), "aviso": AVISO,
                  "estado_de_uso": ESTADO_DE_USO, "contexto": pe.contexto(), "prediccion": None, "historial": [],
                  "lineas": None, "decision_tabla": pe.DECISION_TABLA}
        if conf["estado"] == "vigente":
            lineas = self.lineas_del_centro(conf["artefacto"])
            salida["lineas"] = lineas
            for nombre, linea in lineas.items():
                for e in self._carteras_de(juego, linea):
                    salida["historial"].append(
                        {**self._resumen_de_cartera(e), "linea_del_centro": nombre} if hasattr(e, "artefacto") else
                        {"clave": e.identificador, "linea": linea, "linea_del_centro": nombre, "ilegible": e.motivo,
                         "objetivo": getattr(e, "objetivo", None)})
        if clave is None:
            clave = next((h["clave"] for h in salida["historial"] if not h.get("ilegible")), None)
        if clave is None:
            return salida
        try:
            guardada = self._carteras.cartera(clave)
        except CarterasError as error:
            raise PrediccionesError(error.codigo, str(error)) from error
        if guardada.juego != juego:
            raise PrediccionesError("no_valido", f"la cartera {clave[:12]} es de {guardada.juego}, no de {juego}")
        salida["prediccion"] = self._detalle(guardada, conf)
        return salida

    def _explicacion_de(self, juego: str, clave: str) -> tuple[dict | None, list[dict]]:
        elementos = self._almacen.de_cartera(juego, clave)
        ilegibles = [{"clave": e.clave, "motivo": e.motivo} for e in elementos if not isinstance(e, ExplicacionGuardada)]
        vigentes = [e for e in elementos if isinstance(e, ExplicacionGuardada) and e.artefacto["version"] == pe.VERSION]
        return (vigentes[-1].artefacto if vigentes else None), ilegibles

    def _detalle(self, guardada, conf: dict) -> dict:
        a = guardada.artefacto
        juego = a["juego"]
        explicacion, ilegibles = self._explicacion_de(juego, guardada.identificador)
        linea_modelo = rp.linea_de_modelo_de_cartera(a)
        c = conf["artefacto"]
        de_la_configuracion = c is not None and guardada.linea == c["linea"]
        es_cinco = c is not None and guardada.linea == self.lineas_del_centro(c)["cinco"] and not de_la_configuracion
        return {"clave": guardada.identificador, "integridad": "correcta", "linea": guardada.linea,
                "version_en_el_objetivo": guardada.version, "versiones_en_el_objetivo": guardada.versiones,
                "de_la_configuracion": de_la_configuracion, "peticion_de_cinco": es_cinco,
                "modelo": a["modelo"], "linea_del_artefacto": a["linea"], "datos": a["datos"],
                "objetivo": a["cartera"]["objetivo"], "generacion": a.get("generacion"),
                "parametros": a["cartera"]["parametros"], "construccion": {
                    k: a["cartera"].get(k) for k in ("estado", "solicitadas", "obtenidas", "intentos",
                                                     "presupuesto_de_intentos", "rechazos", "primera_combinacion",
                                                     "nota", "aviso")},
                "combinaciones": pe.combinaciones(a),
                "rankings": (explicacion or {}).get("rankings") or pe.rankings(a["fuente"], juego),
                "explicacion": explicacion, "explicaciones_ilegibles": ilegibles,
                "reproduccion": pe.reproducir(explicacion, a) if explicacion else None,
                "frente_a_la_base": self._carteras.estado_frente_a_la_base(a),
                "observado": self._carteras.observado_de_cartera(a),
                "proyeccion": pe.proyeccion_tabla(a, explicacion),
                "linea_de_modelo": linea_modelo,
                "enlaces": {"cartera": f"/carteras/guardadas/{guardada.identificador}",
                            "seguimiento_carteras": f"/carteras/{SLUGS[juego]}/seguimiento",
                            "resultados": (f"/resultados/{SLUGS[juego]}?procedencias=carteras&lineas=carteras:"
                                           f"{linea_modelo['id']}"),
                            "modelo_registrado": (f"/laboratorio/modelo/{a['linea']['registrado']['clave']}"
                                                  if a["linea"].get("registrado") else None),
                            "configuracion": f"/carteras/{SLUGS[juego]}"}}

    # ------------------------------------------------------------------
    # Fiabilidad (lectura pura)
    # ------------------------------------------------------------------

    def fiabilidad(self, juego: str, linea: str | None = None, hasta: int | None = None) -> dict:
        """Evaluaciones de la linea de la configuracion (vector fuente de las
        carteras), de la linea de laboratorio de su version registrada y de la
        receta en su informe, por separado. `linea`: otra linea de Producto 6
        de este juego (`procedencia:linea`). `hasta`: solo objetivos <= hasta."""
        _validar_juego(juego)
        if hasta is not None and (not isinstance(hasta, int) or isinstance(hasta, bool) or hasta < 1):
            raise PrediccionesError("no_valido", "hasta debe ser un número de sorteo positivo")
        conf = self._configuracion(juego)
        c = conf["artefacto"]
        registrado = self._registrado(c)
        datos = self._resultados.emisiones(juego)
        por_linea: dict[str, list] = {}
        for f in datos["filas"]:
            por_linea.setdefault(f["clave_linea"], []).append(f)
        elegidas: list[tuple[str, str]] = []
        if c is not None:
            elegidas.append((rp.clave_de_linea("carteras", linea_de_modelo(c)),
                             "vector fuente del modelo de la configuración (carteras de Producto 5)"))
            if registrado and registrado.get("linea_de_laboratorio"):
                elegidas.append((rp.clave_de_linea("laboratorio", registrado["linea_de_laboratorio"]),
                                 "pronósticos del estimador congelado de la versión registrada (laboratorio)"))
        if linea:
            if linea not in datos["lineas"]:
                raise PrediccionesError("no_valido", f"línea desconocida para {juego}: {linea}")
            if linea not in [x for x, _ in elegidas]:
                elegidas.append((linea, "línea elegida en la consulta"))
        evaluaciones = []
        for clave, papel in elegidas:
            meta = datos["lineas"].get(clave)
            evaluaciones.append({
                "linea": clave, "papel": papel, "nombre": meta["nombre"] if meta else clave.split(":", 1)[1],
                "estimador": _estimador_de(clave),
                "evaluaciones": [pf.evaluar_emisiones(por_linea.get(clave, []), tipo, (juego, clave), hasta)
                                 for tipo in rp.TIPOS]})
        receta = self._evaluacion_de_receta(juego, c, registrado, hasta)
        return {"juego": juego, "nombre": NOMBRES[juego], "slug": SLUGS[juego], "configuracion": conf,
                "registrado": registrado, "base": datos["base"], "hasta": hasta, "metodo": pf.METODO,
                "lineas": evaluaciones, "receta": receta, "linea_consultada": linea or None,
                "lineas_disponibles": sorted(datos["lineas"]), "contexto": pe.contexto(),
                "aviso": ("Probabilidad emitida, rendimiento observado e incertidumbre se presentan por separado. "
                          "Ninguna cifra es un nivel de confianza ni acredita ventaja futura.")}

    def _evaluacion_de_receta(self, juego: str, c: dict | None, registrado: dict | None, hasta: int | None) -> dict:
        if c is None:
            return {"estado": "sin_datos", "motivo": "sin configuración vigente", "tipo": "evaluacion_de_receta"}
        modelo = c["modelo"]["id"]
        informe = None
        if registrado and registrado.get("experimento"):
            e = self._modelos.obtener_experimento(registrado["experimento"])
            informe = e.artefacto if hasattr(e, "artefacto") else None
            origen = "informe de procedencia de la versión registrada"
        else:
            origen = "informe más reciente del laboratorio que evalúa la receta con el mismo perfil"
            for e in self._modelos.experimentos(juego) if self._modelos is not None else []:
                a = getattr(e, "artefacto", None)
                if a and a["identidad"]["protocolo"]["perfil"] == c["perfil"] and any(
                        x["id"] == modelo and str(x.get("version")) == str(c["modelo"]["version"])
                        for x in a["candidatos"]):
                    informe = a
                    break
        if informe is None:
            return {"estado": "sin_datos", "tipo": "evaluacion_de_receta", "origen": origen,
                    "motivo": "no hay un informe legible del laboratorio con esta receta"}
        return {**pf.evaluar_informe(informe, modelo, (juego, informe["clave"], modelo), hasta), "origen": origen}

    # ------------------------------------------------------------------
    # Ejecuciones (lectura)
    # ------------------------------------------------------------------

    def ejecucion(self, identificador: str) -> dict | None:
        """Estado de una generacion (lectura pura). Una generacion «en curso»
        sin cerrojo no tiene trabajador y se muestra interrumpida; los juegos
        de Carteras que quedaron a medias tambien, con su cartera solo si esta
        publicada y se verifica."""
        cartera = self._carteras.consultar_ejecucion(identificador)
        propia = self._registro.obtener(identificador)
        if cartera is None and propia is None:
            return None
        if propia and propia.get("estado") == "en_curso" and not self._cerrojo.ejecucion_viva(identificador):
            # El trabajador guarda su cierre ANTES de soltar el cerrojo: si acaba de terminar, la relectura lo ve
            propia = self._registro.obtener(identificador) or propia
            if propia.get("estado") == "en_curso":
                propia = {**propia, "estado": "interrumpida", "fase": "interrumpida", "derivado": True,
                          "mensaje": "El proceso que coordinaba esta generación terminó antes de acabar. Lo ya publicado "
                                     "se conserva; repetir la misma entrada lo reutiliza y completa la explicación."}
        if cartera and cartera.get("estado") != "en_curso":
            juegos = {}
            for juego, r in (cartera.get("juegos") or {}).items():
                if r.get("estado") in ("pendiente", "en_curso"):
                    publicada = self._cartera_anotada(r, juego)
                    r = {**r, "estado": "interrumpido", "fase": "interrumpido",
                         "cartera_verificada": publicada["publicada"]}
                juegos[juego] = r
            cartera = {**cartera, "juegos": juegos}
        return {"cartera": cartera, "prediccion": propia}


def _base_de(diagnostico: dict) -> dict:
    datos = diagnostico.get("datos") or {}
    return {"estado": diagnostico.get("estado"), "mensaje": diagnostico.get("mensaje"),
            "corte": datos.get("corte"), "sorteos": datos.get("sorteos"), "ultima_fecha": datos.get("ultima_fecha"),
            "objetivo": diagnostico.get("objetivo"), "frescura": diagnostico.get("frescura")}


def _estimador_de(clave_linea: str) -> str:
    procedencia, linea = clave_linea.split(":", 1)
    if "-reg" in linea:
        return "estimador congelado (versión registrada, sin reajustes)"
    if procedencia == "operacion":
        return "receta reajustada en cada emisión de la operación diaria"
    return "receta reajustada al generar cada emisión con el histórico hasta su corte"

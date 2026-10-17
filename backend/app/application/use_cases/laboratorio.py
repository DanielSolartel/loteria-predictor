"""
Casos de uso del laboratorio de modelos (Producto 4), comunes a la web, la
API y el comando `python -m scripts.laboratorio_modelos`.

- `diagnostico`/`panel`: muestra, corte, frescura y disponibilidad de los
  candidatos de cada juego (solo lectura).
- `iniciar_comparacion` + `ejecutar_comparacion`: compara los candidatos de
  uno o varios juegos. Reutiliza las primitivas de Producto 3: cerrojo del
  sistema operativo por juego (en la carpeta del laboratorio, asi que no
  bloquea la operacion diaria), cerrojo propio de la ejecucion (para
  reconocer una ejecucion interrumpida) y registro de progreso persistente.
  Por juego: fase `obteniendo_datos` (una sola lectura del historico en una
  transaccion de solo lectura; la sesion se cierra antes de entrenar),
  `modelo` (candidato y bloque en curso) y `terminado`. Si ya existe un
  informe con la misma identidad, se reutiliza sin reentrenar.
- `generar`: pronostico con un candidato de un experimento, usando su
  instantanea congelada; el objetivo se clasifica segun la base actual.
  Misma entrada -> el mismo pronostico guardado.
- `verificar_experimento` / `verificar_pronostico`: integridad, reproduccion
  con la instantanea guardada y coincidencia con la base actual, por
  separado. Reentrenan, sin guardar nada.
- `seguimiento`: resultados observados por linea de modelo.
- Fase 3, MODELOS REGISTRADOS: `iniciar_entrenamiento` + `ejecutar_entrenamiento`
  (o `entrenar_ahora`) entrena un candidato de un informe con su instantanea
  (corte explicito del informe) en el proceso trabajador y publica la version
  (manifiesto + estimador) con progreso persistente; misma entrada -> la misma
  version. `modelos`/`modelo`/`ficha_del_modelo` consultan las versiones;
  `verificar_modelo` comprueba integridad, compatibilidad, carga restringida y
  el pronostico de control; `generar_con_modelo` recarga la version y
  pronostica el sorteo siguiente a un corte de entrada (>= el de entrenamiento)
  SIN reentrenar, en una linea propia de la version (`<modelo>-v<receta>-reg<n>`).
  Elegir una version para la operacion diaria es una configuracion explicita
  de Producto 5; comparar o entrenar nunca la cambia.

Solo se lee PostgreSQL. Comparar y generar escriben unicamente en el almacen
del laboratorio. Nada de esto importa sorteos ni cambia la operacion diaria,
el NO-GO de AE-39 o `AUTORIZA_EVALUACION`.
"""
from __future__ import annotations

import time
from collections import Counter
from collections.abc import Callable, Iterable
from contextlib import AbstractContextManager
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Any

from app.application.estadisticas.resumen_juego import evaluar_frescura
from app.application.exceptions import JuegoNoEncontradoError
from app.application.interfaces.ejecutor_laboratorio import (
    EjecutorDeLaboratorio,
    TiempoAgotadoError,
    TrabajadorFallidoError,
)
from app.application.interfaces.laboratorio_store import GuardadoLaboratorio, GuardadoModelo, IlegibleModelo
from app.application.ml import laboratorio_artefactos as la
from app.application.ml import laboratorio_evaluacion as le
from app.application.ml import laboratorio_modelos as lm
from app.application.ml import laboratorio_variables as lv
from app.application.ml import modelos_registrados as mr
from app.application.ml import resultados_observados as ro
from app.application.use_cases.operacion_diaria import EjecucionActivaError, mensaje_legible, nuevo_identificador

JUEGOS = lv.JUEGOS
NOMBRES = {"BALOTO": "Baloto", "BALOTO_REVANCHA": "Baloto Revancha", "MILOTO": "MiLoto", "COLORLOTO": "ColorLoto"}
SLUGS = {"BALOTO": "baloto", "BALOTO_REVANCHA": "baloto-revancha", "MILOTO": "miloto", "COLORLOTO": "colorloto"}


class LaboratorioError(Exception):
    """Error esperado con un codigo estable (`no_encontrado`, `no_valido`,
    `muestra_insuficiente`, `alterado`, `no_disponible`, `base_no_disponible`;
    Fase 3: `incompatible`, `corte_no_valido`, `estimador_no_admitido`,
    `no_registrable`, `tiempo_agotado`)."""

    def __init__(self, codigo: str, mensaje: str):
        self.codigo = codigo
        super().__init__(mensaje)


@dataclass
class Lectura:
    juego_repository: Any
    resultados_repository: Any


@dataclass
class Inicio:
    ejecucion: dict
    cerrojos: Any
    juegos: tuple[str, ...] = field(default_factory=tuple)
    protocolo: le.Protocolo = field(default_factory=le.Protocolo)


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def leer_historico(lectura: Lectura, juego: str, hasta: int | None = None) -> list:
    entidad = lectura.juego_repository.obtener_por_codigo(juego)
    if entidad is None:
        raise JuegoNoEncontradoError(juego)
    listar = (lectura.resultados_repository.listar_resultados_colorloto if juego == "COLORLOTO"
              else lectura.resultados_repository.listar_resultados_numericos)
    return listar(entidad.id) if hasta is None else listar(entidad.id, hasta_numero_sorteo=hasta)


class EjecutorEnEsteProceso(EjecutorDeLaboratorio):
    """Entrena en el proceso que llama. SOLO PARA PRUEBAS: no limita hilos ni
    aisla nada; la aplicacion usa `EjecutorEnProceso` (infraestructura)."""

    def evaluar(self, instantanea, entradas, protocolo, avance=None):
        return le.evaluar(instantanea, entradas, protocolo, avance=avance)

    def pronostico(self, informe, entrada):
        return la.cuerpo_del_pronostico(informe, entrada)

    def entrenar(self, informe, entrada, avance=None):
        return mr.entrenar(informe, entrada)

    def control_registrado(self, artefacto, estimador, informe):
        return mr.control_recargado(artefacto, estimador, informe)

    def pronostico_registrado(self, artefacto, estimador, sorteos):
        recargado = mr.deserializar_estimador(estimador, artefacto["estimador"]["sha256"],
                                              artefacto["estimador"]["bytes"])
        return mr.cuerpo_del_pronostico_registrado(artefacto, recargado,
                                                   lv.instantanea_desde_canonicos(artefacto["juego"], sorteos))

    def explicacion_registrada(self, artefacto, estimador):
        from app.application.ml import predicciones_explicacion as pe

        recargado = mr.deserializar_estimador(estimador, artefacto["estimador"]["sha256"],
                                              artefacto["estimador"]["bytes"])
        return pe.importancias_globales(recargado, artefacto["identidad"]["variables"]["nombres"])


class LaboratorioDeModelos:
    def __init__(self, almacen, registro, cerrojo, abrir_lectura: Callable[[], AbstractContextManager[Lectura]],
                 *, ejecutor: EjecutorDeLaboratorio, reloj: Callable[[], datetime] = _ahora,
                 generador_de_identificador: Callable[[datetime], str] = nuevo_identificador):
        """`ejecutor` decide donde se entrena: la aplicacion pasa el proceso
        trabajador dedicado; la lectura de la base termina antes de entrenar."""
        self._ejecutor = ejecutor
        self._almacen = almacen
        self._registro = registro
        self._cerrojo = cerrojo
        self._abrir = abrir_lectura
        self._reloj = reloj
        self._nuevo_identificador = generador_de_identificador

    # ------------------------------------------------------------------
    # Lectura de la base (cada llamada abre y cierra su propia sesion)
    # ------------------------------------------------------------------

    def _historico(self, juego: str, hasta: int | None = None) -> list:
        with self._abrir() as lectura:
            return list(leer_historico(lectura, juego, hasta))

    def _historico_o_none(self, juego: str) -> list | None:
        try:
            return self._historico(juego)
        except Exception:  # base no disponible: las consultas de lo guardado siguen funcionando
            return None

    # ------------------------------------------------------------------
    # Catalogo y diagnostico
    # ------------------------------------------------------------------

    @staticmethod
    def catalogo(perfil: str = "predeterminado") -> dict:
        return {"juegos": {j: [{**e.como_dict(perfil), "registrable": lm.registrable(e)}
                               for e in lm.candidatos_del_juego(j)] for j in JUEGOS},
                "variables": lv.VERSION_VARIABLES, "protocolo": le.Protocolo(perfil=perfil).como_dict(),
                "implementacion": la.VERSION_IMPLEMENTACION, "registro": mr.VERSION_REGISTRO,
                "familias_futuras": dict(lm.FAMILIAS_FUTURAS)}

    def diagnostico(self, juego: str, protocolo: le.Protocolo | None = None) -> dict:
        _validar_juego(juego)
        protocolo = protocolo or le.Protocolo()
        salida = {"juego": juego, "nombre": NOMBRES[juego], "activa": self._cerrojo.activa(juego),
                  "experimentos": [_resumen_de_experimento(e) for e in self._almacen.experimentos(juego)[:10]],
                  "lineas": self._almacen.lineas(juego)}
        try:
            historico = self._historico(juego)
        except Exception as error:
            return {**salida, "estado": "base_no_disponible", "mensaje": mensaje_legible(error)}
        if not historico:
            return {**salida, "estado": "sin_datos", "mensaje": "No hay sorteos cargados para este juego."}
        try:
            instantanea = lv.validar_instantanea(juego, historico)
        except lv.HistoricoNoValidoError as error:
            return {**salida, "estado": "historico_no_valido", "mensaje": str(error)}
        salida.update({"datos": instantanea.procedencia(), "paleta": list(instantanea.paleta()),
                       "frescura": evaluar_frescura(instantanea.sorteos[-1].fecha, self._reloj().date())})
        try:
            muestra = le.muestra_comun(instantanea, protocolo)
        except le.MuestraInsuficienteError as error:
            return {**salida, "estado": "muestra_insuficiente", "mensaje": str(error),
                    "candidatos": [{**e.como_dict(protocolo.perfil), "disponibilidad": "no_disponible"}
                                   for e in lm.candidatos_del_juego(juego)]}
        salida.update({"estado": "disponible", "muestra": {
            "objetivos": muestra["objetivos"], "bloques": len(muestra["bloques"]), "excluidos": muestra["excluidos"],
            "muestra_pequena": le.es_muestra_pequena(len(muestra["objetivos"]), protocolo)},
            "candidatos": [{**e.como_dict(protocolo.perfil),
                            "disponibilidad": _disponibilidad(e, muestra["bloques"])}
                           for e in lm.candidatos_del_juego(juego)]})
        return salida

    def panel(self) -> list[dict]:
        return [self.diagnostico(j) for j in JUEGOS]

    # ------------------------------------------------------------------
    # Comparacion en segundo plano
    # ------------------------------------------------------------------

    def iniciar_comparacion(self, juegos: Iterable[str], protocolo: le.Protocolo | None = None,
                            origen: str = "web", corte: int | None = None) -> Inicio:
        juegos = tuple(dict.fromkeys(juegos))
        if not juegos or any(j not in JUEGOS for j in juegos):
            raise LaboratorioError("no_valido", f"juegos admitidos: {', '.join(JUEGOS)}")
        if corte is not None and len(juegos) != 1:
            raise LaboratorioError("no_valido", "un corte explicito solo se admite para un juego")
        protocolo = protocolo or le.Protocolo()
        ahora = self._reloj()
        identificador = self._nuevo_identificador(ahora)
        cerrojos = self._cerrojo.adquirir(juegos, identificador)
        if isinstance(cerrojos, dict):
            raise EjecucionActivaError(cerrojos)
        ejecucion = {"id": identificador, "tipo": "comparacion", "origen": origen, "estado": "en_curso",
                     "fase": "inicio", "iniciada_en": ahora.isoformat(), "finalizada_en": None, "orden": list(juegos),
                     "corte": corte, "protocolo": protocolo.como_dict(),
                     "juegos": {j: {"juego": j, "estado": "pendiente", "fase": "inicio"} for j in juegos}}
        try:
            self._registro.guardar(ejecucion)
        except BaseException:
            cerrojos.liberar()
            raise
        return Inicio(ejecucion, cerrojos, juegos, protocolo)

    def ejecutar_comparacion(self, inicio: Inicio) -> dict:
        ejecucion = inicio.ejecucion
        try:
            for juego in inicio.juegos:
                ejecucion["fase"] = "modelo"
                ejecucion["juegos"][juego] = self._comparar_juego(ejecucion, juego, inicio.protocolo)
                inicio.cerrojos.liberar(juego)
                self._registro.guardar(ejecucion)
            estados = Counter(r["estado"] for r in ejecucion["juegos"].values())
            ejecucion["estado"] = ("exito" if estados["terminado"] + estados["reutilizado"] == len(inicio.juegos)
                                   else "fallo" if not (estados["terminado"] or estados["reutilizado"]
                                                        or estados["parcial"]) else "parcial")
            ejecucion["fase"] = "terminado"
            ejecucion["finalizada_en"] = self._reloj().isoformat()
            self._registro.guardar(ejecucion)
            return ejecucion
        finally:
            inicio.cerrojos.liberar()

    def comparar_ahora(self, juegos: Iterable[str], protocolo: le.Protocolo | None = None, origen: str = "comando",
                       corte: int | None = None) -> dict:
        return self.ejecutar_comparacion(self.iniciar_comparacion(juegos, protocolo, origen, corte))

    def _avance(self, ejecucion: dict, r: dict, fase: str, **datos) -> None:
        r.update({"fase": fase, **datos})
        ejecucion["juegos"][r["juego"]] = r
        self._registro.guardar(ejecucion)

    def _comparar_juego(self, ejecucion: dict, juego: str, protocolo: le.Protocolo) -> dict:
        r = {"juego": juego, "estado": "en_curso", "fase": "obteniendo_datos", "inicio": self._reloj().isoformat(),
             "fin": None, "experimento": None, "mensaje": None}
        self._avance(ejecucion, r, "obteniendo_datos")
        try:
            try:
                historico = self._historico(juego, ejecucion.get("corte"))
            except Exception as error:  # una sola lectura; sin ella no se entrena nada
                return self._cerrar(r, "base_no_disponible", mensaje_legible(error))
            if ejecucion.get("corte") is not None and ejecucion["corte"] not in {s.numero_sorteo for s in historico}:
                raise LaboratorioError("no_valido", f"el corte {ejecucion['corte']} no es un sorteo cargado")
            instantanea = lv.validar_instantanea(juego, historico, ejecucion.get("corte"))
            entradas = lm.candidatos_del_juego(juego)
            identidad = la.identidad_del_experimento(instantanea, entradas, protocolo)
            clave = la.clave_del_experimento(identidad)
            r.update({"corte": instantanea.corte, "sorteos": len(instantanea), "experimento": clave})
            existente = self._almacen.obtener_experimento(clave)
            if existente is not None:
                return self._cerrar_con_existente(r, existente)
            iniciado = self._reloj().isoformat()
            evaluacion, tiempos = self._ejecutor.evaluar(
                instantanea, entradas, protocolo, avance=lambda fase, **d: self._avance(ejecucion, r, fase, **d))
            informe = la.componer(la.cuerpo_del_experimento(instantanea, identidad, evaluacion), "ejecucion",
                                  {"iniciado_en": iniciado, "terminado_en": self._reloj().isoformat(),
                                   "segundos_por_candidato": tiempos, "origen": ejecucion["origen"],
                                   "ejecucion": ejecucion["id"],
                                   "nota": "datos volatiles: no forman parte de la huella de reproduccion"})
            try:
                guardado = self._almacen.guardar_experimento(informe)
            except FileExistsError:  # otra ejecucion publico la misma identidad mientras tanto
                return self._cerrar_con_existente(r, self._almacen.obtener_experimento(clave))
            return self._cerrar_con_informe(r, guardado.artefacto, reutilizado=False)
        except le.MuestraInsuficienteError as error:
            return self._cerrar(r, "muestra_insuficiente", str(error))
        except (lv.HistoricoNoValidoError, LaboratorioError, JuegoNoEncontradoError) as error:
            return self._cerrar(r, "fallo", mensaje_legible(error))
        except TrabajadorFallidoError as error:  # el proceso trabajador murio: nada se publico
            return self._cerrar(r, "fallo", f"Fallo del proceso de entrenamiento: {mensaje_legible(error)}")
        except Exception as error:  # base caida u otro fallo: el juego falla, los demas siguen
            return self._cerrar(r, "fallo", mensaje_legible(error))

    def _cerrar(self, r: dict, estado: str, mensaje: str | None = None) -> dict:
        r.update({"estado": estado, "fase": "terminado", "fin": self._reloj().isoformat(), "mensaje": mensaje})
        r.pop("candidato", None)
        r.pop("bloque", None)
        return r

    def _cerrar_con_existente(self, r: dict, existente) -> dict:
        if not isinstance(existente, GuardadoLaboratorio):
            return self._cerrar(r, "fallo", "ya existe un informe con la misma entrada pero esta alterado o ilegible; "
                                            "no se sobrescribe")
        return self._cerrar_con_informe(r, existente.artefacto, reutilizado=True)

    def _cerrar_con_informe(self, r: dict, informe: dict, reutilizado: bool) -> dict:
        completos = all(c["estado"] == "completo" for c in informe["candidatos"])
        r["resumen"] = informe["resumen"]["estado"]
        r["incompletos"] = [c["id"] for c in informe["candidatos"] if c["estado"] != "completo"]
        estado = "reutilizado" if reutilizado else ("terminado" if completos else "parcial")
        mensaje = None if completos else "candidatos sin evaluacion completa: " + ", ".join(r["incompletos"])
        return self._cerrar(r, estado, mensaje)

    def consultar_ejecucion(self, identificador: str) -> dict | None:
        return self._derivar(self._registro.obtener(identificador))

    def recientes(self, limite: int = 20) -> list[dict]:
        return [self._derivar(e) for e in self._registro.listar(limite)]

    def _derivar(self, ejecucion: dict | None) -> dict | None:
        """En curso sin trabajador vivo (cerrojo de la ejecucion libre) -> interrumpida.
        Solo lectura."""
        if ejecucion is None or ejecucion.get("estado") != "en_curso":
            return ejecucion
        if not self._cerrojo.ejecucion_viva(ejecucion["id"]):
            return {**ejecucion, "estado": "interrumpida", "fase": "interrumpida",
                    "mensaje": "El proceso que la ejecutaba termino antes de acabar. Los informes ya publicados se "
                               "conservan; una comparacion identica los reutiliza."}
        return ejecucion

    def abortar(self, inicio: Inicio, motivo: str) -> None:
        inicio.cerrojos.liberar()
        try:
            self._registro.guardar({**inicio.ejecucion, "estado": "interrumpida", "fase": "interrumpida",
                                    "finalizada_en": self._reloj().isoformat(),
                                    "mensaje": f"No se pudo iniciar el trabajo: {mensaje_legible(motivo)}"})
        except OSError:
            pass

    def recuperar(self) -> list[str]:
        marcadas = []
        for e in self._registro.listar(200):
            if e.get("tipo") not in ("comparacion", "entrenamiento"):
                continue
            derivada = self._derivar(e)
            if derivada is not e and derivada.get("estado") == "interrumpida":
                derivada = {**derivada, "juegos": {j: dict(r) for j, r in derivada.get("juegos", {}).items()},
                            "finalizada_en": self._reloj().isoformat()}
                for r in derivada["juegos"].values():
                    if r.get("estado") in ("pendiente", "en_curso"):
                        r["estado"] = "interrumpido"
                self._registro.guardar(derivada)
                marcadas.append(derivada["id"])
        return marcadas

    # ------------------------------------------------------------------
    # Experimentos guardados
    # ------------------------------------------------------------------

    def experimentos(self, juego: str) -> list:
        _validar_juego(juego)
        return self._almacen.experimentos(juego)

    def lineas(self, juego: str) -> list[str]:
        _validar_juego(juego)
        return self._almacen.lineas(juego)

    def experimento(self, clave: str):
        guardado = self._almacen.obtener_experimento(clave)
        if guardado is None:
            raise LaboratorioError("no_encontrado", f"No existe el experimento {clave}")
        if not isinstance(guardado, GuardadoLaboratorio):
            raise LaboratorioError("alterado", f"El informe {clave} esta alterado o ilegible ({guardado.motivo})")
        return guardado

    def estado_frente_a_la_base(self, informe: dict) -> dict:
        """Compara la instantanea del experimento con la base actual (lectura)."""
        completo = self._historico_o_none(informe["juego"])
        if completo is None:
            return {"estado": "base_no_disponible"}
        corte = informe["datos"]["corte"]
        hasta = [r for r in completo if r.numero_sorteo <= corte]
        try:
            actual = lv.validar_instantanea(informe["juego"], hasta).huella() if hasta else None
        except lv.HistoricoNoValidoError:
            actual = "no_valido"
        ultimo = max((r.numero_sorteo for r in completo), default=None)
        coincide = ("no_disponible" if actual is None else
                    "coincide" if actual == informe["datos"]["sha256_historico"] else "cambio")
        return {"estado": "disponible", "historico_hasta_el_corte": coincide, "ultimo_sorteo_actual": ultimo,
                "base_avanzo": ultimo is not None and ultimo > corte,
                "nuevos_desde_el_corte": sum(1 for r in completo if r.numero_sorteo > corte)}

    # ------------------------------------------------------------------
    # Pronosticos
    # ------------------------------------------------------------------

    def _entrada_del_informe(self, informe: dict, modelo: str) -> lm.EntradaCatalogo:
        if modelo not in {c["id"] for c in informe["candidatos"]}:
            raise LaboratorioError("no_valido", f"el experimento no incluye el modelo {modelo!r}")
        try:
            entradas = {e.id: e for e in la.entradas_del_experimento(informe)}
        except la.ArtefactoLaboratorioError as error:
            raise LaboratorioError("no_disponible", str(error)) from error
        entrada = entradas[modelo]
        if not entrada.genera_pronostico:
            raise LaboratorioError("no_valido", f"{entrada.nombre} es una referencia sin pronostico propio")
        return entrada

    def generar(self, clave_experimento: str, modelo: str):
        informe = self.experimento(clave_experimento).artefacto
        entrada = self._entrada_del_informe(informe, modelo)
        clave = la.huella(la.identidad_del_pronostico(informe, entrada))
        existente = self._almacen.obtener_pronostico(clave)
        if existente is not None:
            if not isinstance(existente, GuardadoLaboratorio):
                raise LaboratorioError("alterado", "ya existe un pronostico con la misma entrada pero esta alterado; "
                                                   "no se sobrescribe")
            return replace(existente, reutilizado=True)
        try:
            cuerpo = self._ejecutor.pronostico(informe, entrada)
        except lm.CandidatoNoDisponible as error:
            raise LaboratorioError(error.estado, f"El modelo no se pudo ajustar: {error.motivo}") from error
        except TrabajadorFallidoError as error:
            raise LaboratorioError("fallo_del_trabajador", f"Fallo del proceso de entrenamiento: {error}") from error
        ahora = self._reloj()
        completo = self._historico_o_none(informe["juego"])
        generacion = {"generado_en": ahora.isoformat(),
                      "nota": "reloj local de quien genero; no prueba anterioridad frente al sorteo real",
                      "clasificacion_temporal": None, "frescura": None,
                      "base": "no_disponible" if completo is None else "consultada"}
        if completo:
            sb = (cuerpo["superbalota"] or {}).get("pronostico", {}).get("sugerida")
            generacion["clasificacion_temporal"] = ro.clasificar_objetivo(informe["juego"], cuerpo["pronostico"], sb,
                                                                          completo)
            ultima = max(completo, key=lambda r: r.numero_sorteo).fecha
            generacion["frescura"] = evaluar_frescura(ultima, ahora.date())
        artefacto = la.componer(cuerpo, "generacion", generacion)
        try:
            return self._almacen.guardar_pronostico(artefacto)
        except FileExistsError:
            existente = self._almacen.obtener_pronostico(clave)
            if not isinstance(existente, GuardadoLaboratorio):
                raise
            return replace(existente, reutilizado=True)

    def pronostico(self, clave: str):
        guardado = self._almacen.obtener_pronostico(clave)
        if guardado is None:
            raise LaboratorioError("no_encontrado", f"No existe el pronostico {clave}")
        if not isinstance(guardado, GuardadoLaboratorio):
            raise LaboratorioError("alterado", f"El pronostico {clave} esta alterado o ilegible ({guardado.motivo})")
        return guardado

    def estado_del_pronostico(self, artefacto: dict) -> dict | None:
        """Comparacion con el resultado observado en la base actual (lectura)."""
        completo = self._historico_o_none(artefacto["juego"])
        return None if completo is None else ro.comparar_con_resultado(artefacto, completo)

    # ------------------------------------------------------------------
    # Verificacion
    # ------------------------------------------------------------------

    def verificar_experimento(self, clave: str) -> dict:
        guardado = self._almacen.obtener_experimento(clave)
        if guardado is None:
            raise LaboratorioError("no_encontrado", f"No existe el experimento {clave}")
        if not isinstance(guardado, GuardadoLaboratorio):
            return {"experimento": clave, "integridad": "alterado", "motivo": guardado.motivo,
                    "reproduccion": None, "base_actual": None}
        informe = guardado.artefacto
        salida = {"experimento": clave, "integridad": "correcta", "entorno_guardado": informe["identidad"]["entorno"],
                  "entorno_actual": la.entorno()}
        salida["mismo_entorno"] = salida["entorno_guardado"] == salida["entorno_actual"]
        try:
            instantanea = la.instantanea_del_experimento(informe)
            entradas = la.entradas_del_experimento(informe)
            inicio = time.perf_counter()
            evaluacion, _ = self._ejecutor.evaluar(instantanea, entradas, la.protocolo_del_experimento(informe))
            recalculado = la.cuerpo_del_experimento(instantanea, informe["identidad"], evaluacion)
            salida["reproduccion"] = {**la.comparar_reproduccion(informe, recalculado),
                                      "segundos": round(time.perf_counter() - inicio, 3)}
        except (la.ArtefactoLaboratorioError, lv.HistoricoNoValidoError, le.MuestraInsuficienteError,
                TrabajadorFallidoError) as error:
            salida["reproduccion"] = {"estado": "no_reproducible", "motivo": str(error)}
        salida["base_actual"] = self.estado_frente_a_la_base(informe)
        return salida

    def verificar_pronostico(self, clave: str) -> dict:
        guardado = self._almacen.obtener_pronostico(clave)
        if guardado is None:
            raise LaboratorioError("no_encontrado", f"No existe el pronostico {clave}")
        if not isinstance(guardado, GuardadoLaboratorio):
            return {"pronostico": clave, "integridad": "alterado", "motivo": guardado.motivo,
                    "reproduccion": None, "base_actual": None}
        artefacto = guardado.artefacto
        salida = {"pronostico": clave, "integridad": "correcta",
                  "mismo_entorno": artefacto["identidad"]["entorno"] == la.entorno()}
        if "modelo_registrado" in artefacto["identidad"]:
            salida["reproduccion"] = self._reproducir_pronostico_registrado(artefacto)
            completo = self._historico_o_none(artefacto["juego"])
            salida["base_actual"] = (None if completo is None
                                     else ro.comparar_con_resultado(artefacto, completo)["historico_hasta_el_corte"])
            return salida
        try:
            informe = self.experimento(artefacto["experimento"]).artefacto
            entrada = self._entrada_del_informe(informe, artefacto["modelo"]["id"])
            salida["reproduccion"] = la.comparar_pronostico(artefacto, self._ejecutor.pronostico(informe, entrada))
        except (LaboratorioError, la.ArtefactoLaboratorioError, lm.CandidatoNoDisponible,
                TrabajadorFallidoError) as error:
            salida["reproduccion"] = {"estado": "no_reproducible", "motivo": str(error)}
        completo = self._historico_o_none(artefacto["juego"])
        salida["base_actual"] = (None if completo is None
                                 else ro.comparar_con_resultado(artefacto, completo)["historico_hasta_el_corte"])
        return salida

    # ------------------------------------------------------------------
    # Seguimiento
    # ------------------------------------------------------------------

    def seguimiento(self, juego: str, linea: str | None = None, tipo: str = "seguimiento") -> dict:
        _validar_juego(juego)
        if tipo not in ("seguimiento", "retrospectiva"):
            raise LaboratorioError("no_valido", "tipo admitido: seguimiento o retrospectiva")
        lineas = self._almacen.lineas(juego)
        if linea is not None:
            if linea not in lineas:
                raise LaboratorioError("no_encontrado", f"No hay pronosticos de la linea {linea}")
            lineas = [linea]
        completo = self._historico_o_none(juego)
        por_linea = {}
        for nombre in lineas:
            elementos = []
            experimentos = {}
            for e in self._almacen.pronosticos(juego, nombre):
                if isinstance(e, GuardadoLaboratorio):
                    elementos.append({"objetivo": e.objetivo, "secuencia": e.secuencia,
                                      "identificador": e.identificador, "artefacto": e.artefacto})
                    experimentos.setdefault(e.artefacto["experimento"], e.artefacto["evaluacion_del_experimento"])
                else:
                    elementos.append({"objetivo": e.objetivo, "secuencia": None, "identificador": e.identificador,
                                      "artefacto": None, "ilegible": e.motivo})
            por_linea[nombre] = {**la.seguimiento_de_linea(elementos, completo),
                                 "evaluacion_retrospectiva_de_los_experimentos": experimentos}
        return {"juego": juego, "base": "no_disponible" if completo is None else "consultada", "lineas": por_linea,
                "comparacion": la.comparacion_entre_lineas(por_linea, tipo) if len(por_linea) > 1 else None,
                "nota": la.NOTA_SEGUIMIENTO}


    # ------------------------------------------------------------------
    # Fase 3: modelos registrados
    # ------------------------------------------------------------------

    def _entrada_registrable(self, informe: dict, modelo: str) -> lm.EntradaCatalogo:
        entrada = self._entrada_del_informe(informe, modelo)
        if not lm.registrable(entrada):
            raise LaboratorioError("no_registrable", f"{entrada.nombre} no tiene un estimador que guardar: se "
                                                     "recalcula en cada pronostico")
        return entrada

    def iniciar_entrenamiento(self, clave_experimento: str, modelo: str, origen: str = "web") -> Inicio:
        informe = self.experimento(clave_experimento).artefacto
        self._entrada_registrable(informe, modelo)
        juego = informe["juego"]
        ahora = self._reloj()
        identificador = self._nuevo_identificador(ahora)
        cerrojos = self._cerrojo.adquirir((juego,), identificador)
        if isinstance(cerrojos, dict):
            raise EjecucionActivaError(cerrojos)
        ejecucion = {"id": identificador, "tipo": "entrenamiento", "origen": origen, "estado": "en_curso",
                     "fase": "inicio", "iniciada_en": ahora.isoformat(), "finalizada_en": None, "orden": [juego],
                     "experimento": clave_experimento, "modelo": modelo, "corte": informe["datos"]["corte"],
                     "juegos": {juego: {"juego": juego, "estado": "pendiente", "fase": "inicio"}}}
        try:
            self._registro.guardar(ejecucion)
        except BaseException:
            cerrojos.liberar()
            raise
        return Inicio(ejecucion, cerrojos, (juego,))

    def ejecutar_entrenamiento(self, inicio: Inicio) -> dict:
        ejecucion = inicio.ejecucion
        juego = inicio.juegos[0]
        try:
            ejecucion["fase"] = "entrenando"
            r = self._entrenar(ejecucion, juego)
            ejecucion["juegos"][juego] = r
            ejecucion["estado"] = "exito" if r["estado"] in ("terminado", "reutilizado") else "fallo"
            ejecucion["fase"] = "terminado"
            ejecucion["finalizada_en"] = self._reloj().isoformat()
            self._registro.guardar(ejecucion)
            return ejecucion
        finally:
            inicio.cerrojos.liberar()

    def entrenar_ahora(self, clave_experimento: str, modelo: str, origen: str = "comando") -> dict:
        return self.ejecutar_entrenamiento(self.iniciar_entrenamiento(clave_experimento, modelo, origen))

    def _entrenar(self, ejecucion: dict, juego: str) -> dict:
        r = {"juego": juego, "estado": "en_curso", "fase": "leyendo_informe", "inicio": self._reloj().isoformat(),
             "fin": None, "modelo": ejecucion["modelo"], "experimento": ejecucion["experimento"],
             "modelo_registrado": None, "numero": None, "mensaje": None}
        self._avance(ejecucion, r, "leyendo_informe")
        try:
            informe = self.experimento(ejecucion["experimento"]).artefacto
            entrada = self._entrada_registrable(informe, ejecucion["modelo"])
            identidad = mr.identidad_del_modelo(informe, entrada)
            clave = mr.huella(identidad)
            r.update({"modelo_registrado": clave, "corte": informe["datos"]["corte"],
                      "sorteos": informe["datos"]["sorteos"]})
            existente = self._almacen.obtener_modelo(clave)
            if existente is not None:
                return self._cerrar_con_modelo(r, existente, reutilizado=True)
            iniciado = self._reloj().isoformat()
            self._avance(ejecucion, r, "entrenando")
            inicio = time.perf_counter()
            entrenado = self._ejecutor.entrenar(informe, entrada,
                                                avance=lambda fase, **d: self._avance(ejecucion, r, fase, **d))
            self._avance(ejecucion, r, "publicando")
            cuerpo = mr.cuerpo_del_modelo(informe, entrada, identidad,
                                          {k: v for k, v in entrenado.items() if k != "contenido"})
            artefacto = mr.componer(cuerpo, {"iniciado_en": iniciado, "terminado_en": self._reloj().isoformat(),
                                             "segundos": round(time.perf_counter() - inicio, 3),
                                             "origen": ejecucion["origen"], "ejecucion": ejecucion["id"],
                                             "nota": "datos de publicacion: fuera de la huella de reproduccion"})
            try:
                guardado = self._almacen.guardar_modelo(artefacto, entrenado["contenido"])
            except FileExistsError:  # otro proceso publico la misma entrada mientras tanto
                return self._cerrar_con_modelo(r, self._almacen.obtener_modelo(clave), reutilizado=True)
            return self._cerrar_con_modelo(r, guardado, reutilizado=False)
        except LaboratorioError as error:
            return self._cerrar(r, error.codigo if error.codigo in ("no_registrable", "alterado") else "fallo",
                                str(error))
        except mr.ModeloRegistradoError as error:
            return self._cerrar(r, error.estado, error.motivo)
        except lm.CandidatoNoDisponible as error:
            return self._cerrar(r, error.estado, f"El modelo no se pudo ajustar: {error.motivo}")
        except TiempoAgotadoError as error:
            return self._cerrar(r, "tiempo_agotado", f"Tiempo agotado: {mensaje_legible(error)}")
        except TrabajadorFallidoError as error:  # el proceso trabajador murio: nada se publico
            return self._cerrar(r, "fallo", f"Fallo del proceso de entrenamiento: {mensaje_legible(error)}")
        except Exception as error:
            return self._cerrar(r, "fallo", mensaje_legible(error))

    def _cerrar_con_modelo(self, r: dict, guardado, reutilizado: bool) -> dict:
        if not isinstance(guardado, GuardadoModelo):
            motivo = getattr(guardado, "motivo", "no encontrado")
            return self._cerrar(r, "alterado", f"ya existe una version con la misma entrada pero esta alterada o "
                                               f"incompleta ({motivo}); no se sobrescribe")
        r["numero"] = guardado.numero
        return self._cerrar(r, "reutilizado" if reutilizado else "terminado", None)

    def modelos(self, juego: str) -> dict:
        """Versiones registradas del juego (solo lectura), con su
        compatibilidad con este entorno, y las incidencias del almacen."""
        _validar_juego(juego)
        versiones, ilegibles = [], []
        for e in self._almacen.modelos(juego):
            if isinstance(e, GuardadoModelo):
                compat = mr.compatibilidad(e.artefacto)
                versiones.append({**mr.resumen(e.artefacto), "compatible": compat["compatible"],
                                  "motivos": compat["motivos"]})
            else:
                ilegibles.append({"clave": e.identificador, "motivo": e.motivo, "modelo": e.modelo,
                                  "numero": e.numero})
        return {"juego": juego, "nombre": NOMBRES[juego], "versiones": versiones, "ilegibles": ilegibles,
                "reservas_sin_modelo": [asdict(x) for x in self._almacen.reservas_sin_modelo(juego)],
                "registrables": [{"id": e.id, "nombre": e.nombre, "familia": e.familia}
                                 for e in lm.candidatos_del_juego(juego) if lm.registrable(e)],
                "activa": self._cerrojo.activa(juego)}

    def modelo(self, clave: str) -> GuardadoModelo:
        guardado = self._almacen.obtener_modelo(clave)
        if guardado is None:
            raise LaboratorioError("no_encontrado", f"No existe el modelo registrado {clave}")
        if not isinstance(guardado, GuardadoModelo):
            raise LaboratorioError("alterado", f"El modelo {clave} esta alterado o incompleto ({guardado.motivo}); "
                                               "no se carga")
        return guardado

    def ficha_del_modelo(self, clave: str) -> dict:
        """Ficha de solo lectura: manifiesto, compatibilidad (sin deserializar),
        proyeccion a las tablas de la Fase 1 y pronosticos de su linea."""
        guardado = self.modelo(clave)
        artefacto = guardado.artefacto
        linea = mr.linea_registrada(artefacto)["id"]
        pronosticos = [{"clave": e.identificador, "objetivo": e.objetivo, "secuencia": e.secuencia,
                        "corte": e.artefacto["datos"]["corte"],
                        "generado_en": e.artefacto["generacion"]["generado_en"]}
                       for e in (self._almacen.pronosticos(guardado.juego, linea)
                                 if linea in self._almacen.lineas(guardado.juego) else [])
                       if isinstance(e, GuardadoLaboratorio)]
        return {"modelo": artefacto, "resumen": mr.resumen(artefacto), "compatibilidad": mr.compatibilidad(artefacto),
                "proyeccion": mr.proyeccion_a_tablas(artefacto), "linea": linea, "pronosticos": pronosticos,
                "base_actual": self.estado_frente_a_la_base({"juego": guardado.juego,
                                                             "datos": artefacto["datos"]})}

    def verificar_modelo(self, clave: str) -> dict:
        """Integridad, compatibilidad, carga restringida y pronostico de control
        (con la instantanea del informe de procedencia). No escribe nada."""
        guardado = self._almacen.obtener_modelo(clave)
        if guardado is None:
            raise LaboratorioError("no_encontrado", f"No existe el modelo registrado {clave}")
        if isinstance(guardado, IlegibleModelo):
            return {"modelo": clave, "integridad": "alterado", "motivo": guardado.motivo, "compatibilidad": None,
                    "carga": None, "reproduccion": None, "base_actual": None}
        artefacto = guardado.artefacto
        salida = {"modelo": clave, "numero": guardado.numero, "integridad": "correcta",
                  "estimador": {"sha256": artefacto["estimador"]["sha256"], "bytes": artefacto["estimador"]["bytes"],
                                "estado": "coincide con el manifiesto"},
                  "compatibilidad": mr.compatibilidad(artefacto), "carga": None, "reproduccion": None,
                  "base_actual": self.estado_frente_a_la_base({"juego": guardado.juego, "datos": artefacto["datos"]})}
        if not salida["compatibilidad"]["compatible"]:
            salida["carga"] = {"estado": "no_intentada", "motivo": "entorno o codigo incompatible"}
            return salida
        try:
            informe = self.experimento(artefacto["procedencia"]["experimento"]).artefacto
        except LaboratorioError as error:
            salida["carga"] = {"estado": "no_intentada", "motivo": f"informe de procedencia: {error}"}
            return salida
        try:
            inicio = time.perf_counter()
            control = self._ejecutor.control_registrado(artefacto, self._almacen.leer_estimador(guardado), informe)
        except mr.ModeloRegistradoError as error:
            salida["carga"] = {"estado": error.estado, "motivo": error.motivo}
            return salida
        except (lm.CandidatoNoDisponible, TrabajadorFallidoError, la.ArtefactoLaboratorioError) as error:
            salida["carga"] = {"estado": "fallo", "motivo": mensaje_legible(error)}
            return salida
        guardado_control = artefacto["control"]
        salida["carga"] = {"estado": "correcta", "clase": control["clase"]}
        salida["reproduccion"] = {"objetivo": control["objetivo"],
                                  "exacta": control["sha256_probabilidades"] == guardado_control["sha256_probabilidades"],
                                  "control_guardado": guardado_control["sha256_probabilidades"],
                                  "control_actual": control["sha256_probabilidades"],
                                  "segundos": round(time.perf_counter() - inicio, 3)}
        return salida

    def generar_con_modelo(self, clave: str, corte: int | None = None, origen: str = "web"):
        """Pronostico del sorteo siguiente a `corte` (por defecto el ultimo
        cargado) con la version registrada recargada, SIN reentrenar."""
        guardado = self.modelo(clave)
        artefacto = guardado.artefacto
        juego = guardado.juego
        compat = mr.compatibilidad(artefacto)
        if not compat["compatible"]:
            raise LaboratorioError("incompatible", "El modelo no se puede cargar en este entorno: "
                                                   + "; ".join(compat["motivos"]))
        try:
            historico = self._historico(juego, corte)
        except Exception as error:
            raise LaboratorioError("base_no_disponible", mensaje_legible(error)) from error
        if corte is not None and corte not in {s.numero_sorteo for s in historico}:
            raise LaboratorioError("no_valido", f"el corte {corte} no es un sorteo cargado")
        try:
            instantanea = lv.validar_instantanea(juego, historico, corte)
            mr.validar_corte_de_entrada(artefacto, instantanea)
        except lv.HistoricoNoValidoError as error:
            raise LaboratorioError("no_valido", str(error)) from error
        except mr.ModeloRegistradoError as error:
            raise LaboratorioError(error.estado, error.motivo) from error
        clave_pronostico = la.huella(mr.identidad_del_pronostico_registrado(artefacto, instantanea))
        existente = self._almacen.obtener_pronostico(clave_pronostico)
        if existente is not None:
            if not isinstance(existente, GuardadoLaboratorio):
                raise LaboratorioError("alterado", "ya existe un pronostico con la misma entrada pero esta alterado; "
                                                   "no se sobrescribe")
            return replace(existente, reutilizado=True)
        try:
            cuerpo = self._ejecutor.pronostico_registrado(artefacto, self._almacen.leer_estimador(guardado),
                                                          lv.sorteos_canonicos(instantanea))
        except mr.ModeloRegistradoError as error:
            raise LaboratorioError(error.estado, error.motivo) from error
        except lm.CandidatoNoDisponible as error:
            raise LaboratorioError(error.estado, error.motivo) from error
        except TiempoAgotadoError as error:
            raise LaboratorioError("tiempo_agotado", mensaje_legible(error)) from error
        except TrabajadorFallidoError as error:
            raise LaboratorioError("fallo_del_trabajador", f"Fallo del proceso trabajador: {error}") from error
        ahora = self._reloj()
        completo = self._historico_o_none(juego)
        generacion = {"generado_en": ahora.isoformat(),
                      "nota": "reloj local de quien genero; no prueba anterioridad frente al sorteo real",
                      "clasificacion_temporal": None, "frescura": None, "origen": origen,
                      "base": "no_disponible" if completo is None else "consultada"}
        if completo:
            sb = (cuerpo["superbalota"] or {}).get("pronostico", {}).get("sugerida")
            generacion["clasificacion_temporal"] = ro.clasificar_objetivo(juego, cuerpo["pronostico"], sb, completo)
            ultima = max(completo, key=lambda r: r.numero_sorteo).fecha
            generacion["frescura"] = evaluar_frescura(ultima, ahora.date())
        try:
            return self._almacen.guardar_pronostico(la.componer(cuerpo, "generacion", generacion))
        except FileExistsError:
            existente = self._almacen.obtener_pronostico(clave_pronostico)
            if not isinstance(existente, GuardadoLaboratorio):
                raise
            return replace(existente, reutilizado=True)

    def _reproducir_pronostico_registrado(self, artefacto: dict) -> dict:
        try:
            guardado = self.modelo(artefacto["identidad"]["modelo_registrado"]["clave"])
            compat = mr.compatibilidad(guardado.artefacto)
            if not compat["compatible"]:
                return {"estado": "no_reproducible", "motivo": "modelo incompatible: " + "; ".join(compat["motivos"])}
            corte = artefacto["datos"]["corte"]
            historico = self._historico(artefacto["juego"], corte)
            instantanea = lv.validar_instantanea(artefacto["juego"], historico, corte)
            if instantanea.huella() != artefacto["datos"]["sha256_historico"]:
                return {"estado": "no_reproducible", "motivo": "el historico de la base hasta el corte cambio"}
            recalculado = self._ejecutor.pronostico_registrado(guardado.artefacto,
                                                               self._almacen.leer_estimador(guardado),
                                                               lv.sorteos_canonicos(instantanea))
            return la.comparar_pronostico(artefacto, recalculado)
        except (LaboratorioError, mr.ModeloRegistradoError, lm.CandidatoNoDisponible, lv.HistoricoNoValidoError,
                TrabajadorFallidoError) as error:
            return {"estado": "no_reproducible", "motivo": mensaje_legible(error)}
        except Exception as error:  # base no disponible
            return {"estado": "no_reproducible", "motivo": f"base no disponible: {mensaje_legible(error)}"}


def _validar_juego(juego: str) -> None:
    if juego not in JUEGOS:
        raise LaboratorioError("no_valido", f"juego no admitido: {juego!r}; admitidos: {', '.join(JUEGOS)}")


def _resumen_de_experimento(e) -> dict:
    if not isinstance(e, GuardadoLaboratorio):
        return {"clave": e.identificador, "estado": "ilegible", "motivo": e.motivo}
    a = e.artefacto
    return {"clave": e.identificador, "estado": a["resumen"]["estado"], "corte": a["datos"]["corte"],
            "sorteos": a["datos"]["sorteos"], "terminado_en": a["ejecucion"].get("terminado_en"),
            "objetivos": a["muestra_comun"]["total_objetivos"], "perfil": a["identidad"]["protocolo"]["perfil"],
            "mejor": (a["resumen"]["ranking"] or [{}])[0].get("nombre")}


def _disponibilidad(entrada: lm.EntradaCatalogo, bloques: list[dict]) -> str:
    """Estimacion sin entrenar: si la muestra de cada bloque alcanza los
    requisitos declarados de la receta."""
    req = entrada.requisitos
    if not req:
        return "disponible"
    necesaria = req.get("sorteos_previos") or (req.get("calentamiento", 0) + req.get("objetivos_de_ajuste", 0))
    alcanza = [b["posicion_de_ajuste"] >= necesaria for b in bloques]
    return "disponible" if all(alcanza) else ("parcial" if any(alcanza) else "no_disponible")

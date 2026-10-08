"""
Casos de uso de Producto 5 (modelo combinado, carteras y simulacion),
comunes a la web, la API y el comando `python -m scripts.carteras_modelos`.

- `diagnostico`/`panel`: corte, objetivo, sorteos, frescura, modelos y
  requisitos por juego, configuracion vigente y ultima comparacion (lectura).
- Trabajos en segundo plano (`iniciar` + `ejecutar`), con las primitivas de
  Producto 3 (cerrojo del sistema operativo por juego en la carpeta de
  Producto 5, cerrojo de la ejecucion y registro de progreso persistente):
  - `comparacion`: compara el modelo combinado con los candidatos de
    Producto 4 sobre la muestra comun del protocolo de Producto 5;
  - `cartera`: genera una cartera con un modelo, cantidad, diversidad y
    semilla explicitos;
  - `simulacion`: simula una cartera guardada frente a la cartera uniforme
    guardada del mismo tamano y diversidad;
  - `carteras_configuradas`: genera, por juego, la cartera de su
    configuracion vigente (la usa el panel diario).
  Por juego: UNA lectura del historico en una transaccion de solo lectura (la
  sesion se cierra antes de entrenar, asi que una actualizacion concurrente
  no mezcla dos cortes), fases con progreso y estado final (`terminado`,
  `reutilizado`, `parcial`, `muestra_insuficiente`, `base_no_disponible`,
  `tiempo_agotado`, `sin_configuracion`, `fallo`). Si ya existe un artefacto
  con la misma clave de entrada se reutiliza sin entrenar ni simular.
- `configurar`: guarda una version nueva e inmutable de la configuracion de
  un juego. No elige el modelo con mejor perdida ni cambia Producto 3.
- `verificar_*`: integridad del archivo, reproduccion con la instantanea o
  las carteras guardadas en un entorno compatible y coincidencia del
  historico con la base actual, por separado. No guardan nada.
- `seguimiento`: resultados observados por linea (primera emision sellada).

Solo se lee PostgreSQL. Todo se escribe en el almacen de Producto 5. Nada de
esto importa sorteos ni cambia los artefactos o la operacion de Productos
1-4, el NO-GO de AE-39 o `AUTORIZA_EVALUACION`.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

from app.application.estadisticas.resumen_juego import evaluar_frescura
from app.application.exceptions import JuegoNoEncontradoError
from app.application.interfaces.carteras_store import GuardadoCarteras
from app.application.interfaces.ejecutor_carteras import EjecutorDeCarteras, TiempoAgotadoError
from app.application.interfaces.ejecutor_laboratorio import TrabajadorFallidoError
from app.application.ml import carteras_artefactos as ca
from app.application.ml import carteras_construccion as cc
from app.application.ml import carteras_ensemble as ce
from app.application.ml import carteras_simulacion as cs
from app.application.ml import laboratorio_modelos as lm
from app.application.ml import laboratorio_variables as lv
from app.application.use_cases.laboratorio import JUEGOS, NOMBRES, SLUGS, Lectura, leer_historico
from app.application.use_cases.operacion_diaria import EjecucionActivaError, mensaje_legible, nuevo_identificador

TIPOS_DE_TRABAJO = ("comparacion", "cartera", "simulacion", "carteras_configuradas")
UNIFORME = {"BALOTO": "uniforme", "BALOTO_REVANCHA": "uniforme", "MILOTO": "uniforme", "COLORLOTO": "uniforme_paleta"}
__all__ = ["CarterasDeModelos", "CarterasError", "JUEGOS", "NOMBRES", "SLUGS", "EjecutorCarterasEnEsteProceso"]


class CarterasError(Exception):
    """Error esperado con un codigo estable (`no_encontrado`, `no_valido`,
    `alterado`, `no_disponible`, `muestra_insuficiente`, `parcial`,
    `sin_configuracion`, `fallo_del_trabajador`, `tiempo_agotado`, o el estado
    de un modelo que no se pudo ajustar)."""

    def __init__(self, codigo: str, mensaje: str):
        self.codigo = codigo
        super().__init__(mensaje)


@dataclass
class Inicio:
    ejecucion: dict
    cerrojos: object
    tipo: str
    juegos: tuple[str, ...] = field(default_factory=tuple)
    parametros: dict = field(default_factory=dict)


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


class EjecutorCarterasEnEsteProceso(EjecutorDeCarteras):
    """Entrena y simula en el proceso que llama. SOLO PARA PRUEBAS: no limita
    hilos ni aisla nada; la aplicacion usa `EjecutorCarterasEnProceso`."""

    def comparar(self, instantanea, protocolo, avance=None):
        return ce.evaluar(instantanea, protocolo, avance=avance)

    def fuente(self, instantanea, modelo, perfil, avance=None):
        return ce.fuente(instantanea, modelo, perfil, avance=avance)

    def simular(self, identidad, elegida, uniforme, avance=None):
        return ca.cuerpo_de_simulacion(identidad, elegida, uniforme, avance=avance)


def _validar_juego(juego: str) -> None:
    if juego not in JUEGOS:
        raise CarterasError("no_valido", f"juego no admitido: {juego!r}; admitidos: {', '.join(JUEGOS)}")


def _requisito_de_generacion(juego: str, modelo: str) -> int:
    if modelo == ce.ID_ENSEMBLE:
        return ce.ProtocoloCarteras().minimo_para_generar
    e = lm.CATALOGO[modelo]
    r = e.requisitos
    if not r:
        return 1
    if "sorteos_previos" in r:
        return r["sorteos_previos"]
    return r["calentamiento"] + r["objetivos_de_ajuste"]


class CarterasDeModelos:
    def __init__(self, almacen, registro, cerrojo, abrir_lectura: Callable[[], AbstractContextManager[Lectura]],
                 *, ejecutor: EjecutorDeCarteras, reloj: Callable[[], datetime] = _ahora,
                 generador_de_identificador: Callable[[datetime], str] = nuevo_identificador):
        self._almacen = almacen
        self._registro = registro
        self._cerrojo = cerrojo
        self._abrir = abrir_lectura
        self._ejecutor = ejecutor
        self._reloj = reloj
        self._nuevo_identificador = generador_de_identificador

    # ------------------------------------------------------------------
    # Lectura de la base (cada llamada abre y cierra su propia sesion)
    # ------------------------------------------------------------------

    def _historico(self, juego: str) -> list:
        with self._abrir() as lectura:
            return list(leer_historico(lectura, juego))

    def _historico_o_none(self, juego: str) -> list | None:
        try:
            return self._historico(juego)
        except Exception:  # base no disponible: lo guardado se sigue consultando
            return None

    def _instantanea(self, juego: str, completo: list, corte: int | None) -> lv.Instantanea:
        if corte is not None:
            if corte not in {r.numero_sorteo for r in completo}:
                raise CarterasError("no_valido", f"el corte {corte} no es un sorteo cargado de {juego}")
            completo = [r for r in completo if r.numero_sorteo <= corte]
        if not completo:
            raise CarterasError("no_disponible", f"No hay sorteos cargados de {juego}")
        validada = lv.validar_instantanea(juego, completo, corte)
        # Se trabaja SIEMPRE con la forma canonica guardada en el artefacto (la
        # misma que recibe el proceso trabajador y la que usa la verificacion):
        # el orden de los pares de la base podria cambiar el orden de las sumas
        # y, con ello, el ultimo decimal redondeado.
        return lv.instantanea_desde_canonicos(juego, lv.sorteos_canonicos(validada))

    # ------------------------------------------------------------------
    # Catalogo y diagnostico
    # ------------------------------------------------------------------

    @staticmethod
    def catalogo(perfil: str = "predeterminado") -> dict:
        return {"juegos": {j: [*(e.como_dict(perfil) for e in lm.candidatos_del_juego(j)), ce.entrada_del_ensemble(j)]
                           for j in JUEGOS},
                "modelos_de_cartera": {j: ce.modelos_de_cartera(j) for j in JUEGOS},
                "protocolo": ce.ProtocoloCarteras(perfil=perfil).como_dict(),
                "cartera": {"cantidad": [1, cc.CANTIDAD_MAXIMA], "cantidad_predeterminada": cc.CANTIDAD_PREDETERMINADA,
                            "semilla_predeterminada": cc.SEMILLA_PREDETERMINADA, "diversidades": list(cc.DIVERSIDADES),
                            "limite_numeros_compartidos": cc.LIMITE_NUMEROS_COMPARTIDOS,
                            "limite_coincidencias_colorloto": cc.LIMITE_COINCIDENCIAS_COLORLOTO,
                            "presupuesto_de_intentos": cc.PRESUPUESTO_DE_INTENTOS, "version": cc.VERSION_CONSTRUCCION,
                            "nota": cc.NOTA_CONSTRUCCION, "uniforme": ce.MODELOS_DE_CARTERA_NOTA},
                "simulacion": {"predeterminadas": cs.SIMULACIONES_PREDETERMINADAS,
                               "rango": [cs.SIMULACIONES_MINIMAS, cs.SIMULACIONES_MAXIMAS], "lote": cs.TAMANO_DE_LOTE,
                               "escenarios": [cs.supuestos(e, "BALOTO")["escenario"] for e in cs.ESCENARIOS],
                               "version": cs.VERSION_SIMULACION},
                "implementacion": ca.VERSION_IMPLEMENTACION}

    def diagnostico(self, juego: str) -> dict:
        _validar_juego(juego)
        salida = {"juego": juego, "nombre": NOMBRES[juego], "activa": self._cerrojo.activa(juego),
                  "comparaciones": [_resumen_de_comparacion(e) for e in self._almacen.comparaciones(juego)[:10]],
                  "lineas": self._almacen.lineas(juego), "configuracion": self._configuracion_para_mostrar(juego)}
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
        n = len(instantanea)
        protocolo = ce.ProtocoloCarteras()
        exteriores = max(0, n - protocolo.primera_exterior)
        salida.update({"datos": instantanea.procedencia(), "paleta": list(instantanea.paleta()),
                       "objetivo": instantanea.corte + 1,
                       "frescura": evaluar_frescura(instantanea.sorteos[-1].fecha, self._reloj().date()),
                       "comparacion": {"disponible": exteriores >= protocolo.minimo_evaluables,
                                       "objetivos_exteriores": min(exteriores, protocolo.bloques * protocolo.tamano_bloque),
                                       "requeridos": "70 sorteos (20 de calentamiento, 30 de ajuste, 10 internos y 10 "
                                                     "exteriores)"},
                       "modelos": [{**m, "requiere_sorteos": _requisito_de_generacion(juego, m["id"]),
                                    "puede_generar": n >= _requisito_de_generacion(juego, m["id"])}
                                   for m in self.catalogo()["juegos"][juego]],
                       "estado": "disponible"})
        return salida

    def panel(self) -> list[dict]:
        return [self.diagnostico(j) for j in JUEGOS]

    # ------------------------------------------------------------------
    # Trabajos en segundo plano
    # ------------------------------------------------------------------

    def iniciar(self, tipo: str, juegos: Iterable[str], parametros: dict | None = None, origen: str = "web") -> Inicio:
        if tipo not in TIPOS_DE_TRABAJO:
            raise CarterasError("no_valido", f"trabajo no admitido: {tipo!r}")
        juegos = tuple(dict.fromkeys(juegos))
        if not juegos or any(j not in JUEGOS for j in juegos):
            raise CarterasError("no_valido", f"juegos admitidos: {', '.join(JUEGOS)}")
        parametros = dict(parametros or {})
        if parametros.get("corte") is not None and len(juegos) != 1:
            raise CarterasError("no_valido", "un corte explicito solo se admite para un juego")
        try:
            if tipo == "cartera":
                cc.validar_parametros(parametros.get("cantidad"), parametros.get("semilla"), parametros.get("diversidad"))
                if len(juegos) != 1 or parametros.get("modelo") not in ce.modelos_de_cartera(juegos[0]):
                    raise CarterasError("no_valido", f"modelo no admitido para {juegos[0]}: {parametros.get('modelo')!r}"
                                        if len(juegos) == 1 else "una cartera se genera para un solo juego")
                if parametros.get("perfil", "predeterminado") not in lm.PERFILES:
                    raise CarterasError("no_valido", f"perfil admitido: {', '.join(lm.PERFILES)}")
            if tipo == "simulacion":
                cs.validar(parametros.get("simulaciones"), parametros.get("semilla"))
                if len(juegos) != 1 or not parametros.get("cartera"):
                    raise CarterasError("no_valido", "una simulacion necesita una cartera guardada de un juego")
            if tipo == "comparacion":
                ce.ProtocoloCarteras(**parametros.get("protocolo", {}))
        except (TypeError, ValueError) as error:  # ParametrosNoValidos, SimulacionNoValida, protocolo
            raise CarterasError("no_valido", str(error)) from error
        ahora = self._reloj()
        identificador = self._nuevo_identificador(ahora)
        cerrojos = self._cerrojo.adquirir(juegos, identificador)
        if isinstance(cerrojos, dict):
            raise EjecucionActivaError(cerrojos)
        ejecucion = {"id": identificador, "tipo": tipo, "origen": origen, "estado": "en_curso", "fase": "inicio",
                     "iniciada_en": ahora.isoformat(), "finalizada_en": None, "orden": list(juegos),
                     "parametros": parametros,
                     "juegos": {j: {"juego": j, "estado": "pendiente", "fase": "inicio"} for j in juegos}}
        try:
            self._registro.guardar(ejecucion)
        except BaseException:
            cerrojos.liberar()
            raise
        return Inicio(ejecucion, cerrojos, tipo, juegos, parametros)

    def ejecutar(self, inicio: Inicio) -> dict:
        ejecucion = inicio.ejecucion
        try:
            for juego in inicio.juegos:
                ejecucion["fase"] = "trabajando"
                ejecucion["juegos"][juego] = self._procesar_juego(ejecucion, juego, inicio.tipo, inicio.parametros)
                inicio.cerrojos.liberar(juego)
                self._registro.guardar(ejecucion)
            estados = Counter(r["estado"] for r in ejecucion["juegos"].values())
            buenos = estados["terminado"] + estados["reutilizado"]
            ejecucion["estado"] = ("exito" if buenos == len(inicio.juegos) else
                                   "fallo" if not (buenos or estados["parcial"]) else "parcial")
            ejecucion["resumen"] = dict(sorted(estados.items()))
            ejecucion["fase"] = "terminado"
            ejecucion["finalizada_en"] = self._reloj().isoformat()
            self._registro.guardar(ejecucion)
            return ejecucion
        finally:
            inicio.cerrojos.liberar()

    def ahora(self, tipo: str, juegos: Iterable[str], parametros: dict | None = None, origen: str = "comando") -> dict:
        return self.ejecutar(self.iniciar(tipo, juegos, parametros, origen))

    def _avance(self, ejecucion: dict, r: dict, fase: str, **datos) -> None:
        r.update({"fase": fase, **datos})
        ejecucion["juegos"][r["juego"]] = r
        self._registro.guardar(ejecucion)

    def _cerrar(self, r: dict, estado: str, mensaje: str | None = None, **extra) -> dict:
        r.update({"estado": estado, "fase": "terminado", "fin": self._reloj().isoformat(), "mensaje": mensaje, **extra})
        for k in ("candidato", "bloque", "bloques", "posicion_de_corte", "escenario", "simulaciones", "de"):
            r.pop(k, None)
        return r

    def _procesar_juego(self, ejecucion: dict, juego: str, tipo: str, parametros: dict) -> dict:
        r = {"juego": juego, "estado": "en_curso", "fase": "inicio", "inicio": self._reloj().isoformat(), "fin": None,
             "resultado": None, "mensaje": None}
        avance = (lambda fase, **d: self._avance(ejecucion, r, fase, **d))
        try:
            if tipo == "comparacion":
                return self._comparar_juego(ejecucion, r, juego, parametros, avance)
            if tipo == "simulacion":
                return self._simular_juego(ejecucion, r, juego, parametros, avance)
            if tipo == "carteras_configuradas":
                guardada = self.configuracion_vigente(juego)
                if guardada is None:
                    return self._cerrar(r, "sin_configuracion", f"{NOMBRES[juego]} no tiene una configuracion guardada")
                c = guardada.artefacto
                parametros = {"modelo": c["modelo"]["id"], "perfil": c["perfil"], "cantidad": c["cantidad"],
                              "diversidad": c["diversidad"], "semilla": c["semilla"],
                              "configuracion": {"version": c["version"], "linea": c["linea"]}}
                r["configuracion"] = parametros["configuracion"]
            return self._generar_juego(ejecucion, r, juego, parametros, avance)
        except ce.MuestraInsuficienteCarteras as error:
            return self._cerrar(r, "muestra_insuficiente", str(error))
        except TiempoAgotadoError as error:
            return self._cerrar(r, "tiempo_agotado", f"Tiempo agotado: {mensaje_legible(error)}")
        except TrabajadorFallidoError as error:  # el proceso trabajador murio: nada se publico
            return self._cerrar(r, "fallo", f"Fallo del proceso de trabajo: {mensaje_legible(error)}")
        except (lm.CandidatoNoDisponible, ce.ComponenteNoDisponible) as error:
            return self._cerrar(r, "fallo", f"El modelo no se pudo ajustar: {error}")
        except CarterasError as error:
            estado = "base_no_disponible" if error.codigo == "base_no_disponible" else "fallo"
            return self._cerrar(r, estado, str(error))
        except (lv.HistoricoNoValidoError, JuegoNoEncontradoError, ca.ArtefactoCarterasError,
                cc.ParametrosNoValidos, cs.SimulacionNoValida) as error:
            return self._cerrar(r, "fallo", mensaje_legible(error))
        except Exception as error:  # base caida u otro fallo: el juego falla, los demas siguen
            return self._cerrar(r, "fallo", mensaje_legible(error))

    def _leer(self, r: dict, juego: str, avance) -> list:
        avance("obteniendo_datos")
        try:
            return self._historico(juego)
        except Exception as error:  # una sola lectura; sin ella no se entrena nada
            raise CarterasError("base_no_disponible", mensaje_legible(error)) from error

    def _comparar_juego(self, ejecucion, r, juego, parametros, avance) -> dict:
        completo = self._leer(r, juego, avance)
        instantanea = self._instantanea(juego, completo, parametros.get("corte"))
        protocolo = ce.ProtocoloCarteras(**parametros.get("protocolo", {}))
        identidad = ca.identidad_de_comparacion(instantanea, protocolo)
        clave = ca.huella(identidad)
        r.update({"corte": instantanea.corte, "sorteos": len(instantanea), "resultado": clave, "tipo": "comparacion"})
        existente = self._almacen.obtener_comparacion(clave)
        if existente is not None:
            return self._cerrar_con(r, existente, "comparacion", reutilizado=True)
        iniciado = self._reloj().isoformat()
        evaluacion, tiempos = self._ejecutor.comparar(instantanea, protocolo, avance=avance)
        artefacto = ca.componer(ca.cuerpo_de_comparacion(instantanea, identidad, evaluacion), "ejecucion",
                                {"iniciado_en": iniciado, "terminado_en": self._reloj().isoformat(),
                                 "segundos_por_candidato": tiempos, "origen": ejecucion["origen"],
                                 "ejecucion": ejecucion["id"],
                                 "nota": "datos volatiles: no forman parte de la huella de reproduccion"})
        try:
            guardado = self._almacen.guardar_comparacion(artefacto)
        except FileExistsError:
            return self._cerrar_con(r, self._almacen.obtener_comparacion(clave), "comparacion", reutilizado=True)
        return self._cerrar_con(r, guardado, "comparacion", reutilizado=False)

    def _cerrar_con(self, r: dict, existente, tipo: str, reutilizado: bool) -> dict:
        if not isinstance(existente, GuardadoCarteras):
            return self._cerrar(r, "fallo", f"ya existe un artefacto ({tipo}) con la misma entrada pero esta alterado o "
                                            "ilegible; no se sobrescribe")
        extra = {"resultado": existente.identificador, "tipo": tipo}
        if tipo == "comparacion":
            a = existente.artefacto
            extra["resumen"] = a["resumen"]["estado"]
            extra["incompletos"] = [c["id"] for c in a["candidatos"] if c["estado"] != "completo"]
            if not reutilizado and extra["incompletos"]:
                return self._cerrar(r, "parcial", "candidatos sin evaluacion completa: " + ", ".join(extra["incompletos"]),
                                    **extra)
        if tipo == "cartera":
            extra["linea"] = existente.linea
            extra["objetivo"] = existente.objetivo
        return self._cerrar(r, "reutilizado" if reutilizado else "terminado", None, **extra)

    def _generar_juego(self, ejecucion, r, juego, parametros, avance) -> dict:
        completo = self._leer(r, juego, avance)
        instantanea = self._instantanea(juego, completo, parametros.get("corte"))
        resultado = self._publicar_cartera(instantanea, completo, parametros, ejecucion, r, avance)
        return resultado

    def _publicar_cartera(self, instantanea: lv.Instantanea, completo: list | None, parametros: dict,
                          ejecucion: dict | None, r: dict, avance) -> dict:
        juego = instantanea.codigo
        modelo = parametros["modelo"]
        perfil = parametros.get("perfil", "predeterminado")
        identidad = ca.identidad_de_cartera(instantanea, modelo, perfil, parametros["cantidad"], parametros["semilla"],
                                            parametros["diversidad"])
        clave = ca.huella(identidad)
        r.update({"corte": instantanea.corte, "objetivo": instantanea.corte + 1, "sorteos": len(instantanea),
                  "resultado": clave, "tipo": "cartera", "modelo": modelo})
        existente = self._almacen.obtener_cartera(clave)
        if existente is not None:
            return self._cerrar_con(r, existente, "cartera", reutilizado=True)
        n = len(instantanea)
        requerido = _requisito_de_generacion(juego, modelo)
        if n < requerido and modelo != ce.ID_ENSEMBLE:
            return self._cerrar(r, "muestra_insuficiente",
                                f"Muestra insuficiente para {juego}: hay {n} sorteos y {modelo} necesita {requerido}")
        avance("fuente", modelo=modelo)
        fuente = (ce.fuente(instantanea, modelo, perfil) if ca.es_uniforme(modelo)
                  else self._ejecutor.fuente(instantanea, modelo, perfil, avance=avance))
        avance("construccion", modelo=modelo)
        cuerpo = ca.cuerpo_de_cartera(instantanea, identidad, fuente)
        construccion = cuerpo["cartera"]
        if construccion["estado"] != "completa":
            return self._cerrar(r, "parcial", construccion["motivo"], solicitadas=construccion["solicitadas"],
                                obtenidas=construccion["obtenidas"], intentos=construccion["intentos"],
                                combinaciones_no_publicadas=construccion["combinaciones"])
        ahora = self._reloj()
        generacion = {"generado_en": ahora.isoformat(),
                      "nota": "reloj local de quien genero; no prueba anterioridad frente al sorteo real",
                      "clasificacion_temporal": None, "frescura": None,
                      "base": "no_disponible" if not completo else "consultada",
                      "origen": ejecucion["origen"] if ejecucion else "simulacion",
                      "ejecucion": ejecucion["id"] if ejecucion else None,
                      "configuracion": parametros.get("configuracion")}
        if completo:
            generacion["clasificacion_temporal"] = ca.clasificar_objetivo(juego, instantanea.corte + 1, completo)
            ultima = max(completo, key=lambda x: x.numero_sorteo).fecha
            generacion["frescura"] = evaluar_frescura(ultima, ahora.date())
        artefacto = ca.componer(cuerpo, "generacion", generacion)
        try:
            guardado = self._almacen.guardar_cartera(artefacto)
        except FileExistsError:
            return self._cerrar_con(r, self._almacen.obtener_cartera(clave), "cartera", reutilizado=True)
        return self._cerrar_con(r, guardado, "cartera", reutilizado=False)

    def _cartera_uniforme(self, elegida: dict, avance) -> GuardadoCarteras:
        """La cartera uniforme de referencia (mismo juego, corte, objetivo,
        cantidad, diversidad y semilla), guardada o generada ahora."""
        juego = elegida["juego"]
        p = elegida["cartera"]["parametros"]
        perfil = elegida["identidad"]["perfil"]
        if ca.es_uniforme(elegida["modelo"]["id"]):
            return self.cartera(elegida["clave_de_entrada"])
        instantanea = ca.instantanea_de(elegida)
        parametros = {"modelo": UNIFORME[juego], "perfil": perfil, "cantidad": p["cantidad"],
                      "diversidad": p["diversidad"], "semilla": p["semilla"]}
        r = {"juego": juego}
        resultado = self._publicar_cartera(instantanea, self._historico_o_none(juego), parametros, None, r,
                                           avance or (lambda *a, **k: None))
        if resultado["estado"] not in ("terminado", "reutilizado"):
            raise CarterasError("parcial", f"la cartera uniforme de referencia no se pudo publicar: {resultado['mensaje']}")
        return self.cartera(resultado["resultado"])

    def _simular_juego(self, ejecucion, r, juego, parametros, avance) -> dict:
        elegida = self.cartera(parametros["cartera"])
        if elegida.juego != juego:
            raise CarterasError("no_valido", "la cartera no es de este juego")
        avance("cartera_uniforme")
        uniforme = self._cartera_uniforme(elegida.artefacto, None)
        identidad = ca.identidad_de_simulacion(elegida.artefacto, uniforme.artefacto, parametros["simulaciones"],
                                               parametros["semilla"])
        clave = ca.huella(identidad)
        r.update({"resultado": clave, "tipo": "simulacion", "cartera": elegida.identificador,
                  "cartera_uniforme": uniforme.identificador, "objetivo": elegida.objetivo})
        existente = self._almacen.obtener_simulacion(clave)
        if existente is not None:
            return self._cerrar_con(r, existente, "simulacion", reutilizado=True)
        iniciado = self._reloj().isoformat()
        cuerpo = self._ejecutor.simular(identidad, elegida.artefacto, uniforme.artefacto, avance=avance)
        artefacto = ca.componer(cuerpo, "ejecucion", {"iniciado_en": iniciado, "terminado_en": self._reloj().isoformat(),
                                                      "lote": cs.TAMANO_DE_LOTE, "origen": ejecucion["origen"],
                                                      "ejecucion": ejecucion["id"],
                                                      "nota": "datos volatiles; el tamano de lote no cambia el "
                                                              "resultado"})
        try:
            guardado = self._almacen.guardar_simulacion(artefacto)
        except FileExistsError:
            return self._cerrar_con(r, self._almacen.obtener_simulacion(clave), "simulacion", reutilizado=True)
        return self._cerrar_con(r, guardado, "simulacion", reutilizado=False)

    # ------------------------------------------------------------------
    # Estado de las ejecuciones
    # ------------------------------------------------------------------

    def consultar_ejecucion(self, identificador: str) -> dict | None:
        return self._derivar(self._registro.obtener(identificador))

    def recientes(self, limite: int = 20) -> list[dict]:
        return [self._derivar(e) for e in self._registro.listar(limite)]

    def _derivar(self, ejecucion: dict | None) -> dict | None:
        """En curso sin trabajador vivo -> interrumpida (solo lectura)."""
        if ejecucion is None or ejecucion.get("estado") != "en_curso":
            return ejecucion
        if not self._cerrojo.ejecucion_viva(ejecucion["id"]):
            return {**ejecucion, "estado": "interrumpida", "fase": "interrumpida",
                    "mensaje": "El proceso que la ejecutaba termino antes de acabar. Lo ya publicado se conserva; "
                               "repetir la misma entrada lo reutiliza."}
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
            derivada = self._derivar(e)
            if derivada is not e and derivada.get("estado") == "interrumpida":
                derivada = {**derivada, "juegos": {j: dict(x) for j, x in derivada.get("juegos", {}).items()},
                            "finalizada_en": self._reloj().isoformat()}
                for x in derivada["juegos"].values():
                    if x.get("estado") in ("pendiente", "en_curso"):
                        x["estado"] = "interrumpido"
                self._registro.guardar(derivada)
                marcadas.append(derivada["id"])
        return marcadas

    # ------------------------------------------------------------------
    # Artefactos guardados
    # ------------------------------------------------------------------

    def _obtener(self, tipo: str, clave: str) -> GuardadoCarteras:
        guardado = getattr(self._almacen, f"obtener_{tipo}")(clave)
        if guardado is None:
            raise CarterasError("no_encontrado", f"No existe la {tipo} {clave}")
        if not isinstance(guardado, GuardadoCarteras):
            raise CarterasError("alterado", f"La {tipo} {clave} esta alterada o ilegible ({guardado.motivo})")
        return guardado

    def comparacion(self, clave: str) -> GuardadoCarteras:
        return self._obtener("comparacion", clave)

    def cartera(self, clave: str) -> GuardadoCarteras:
        return self._obtener("cartera", clave)

    def simulacion(self, clave: str) -> GuardadoCarteras:
        return self._obtener("simulacion", clave)

    def comparaciones(self, juego: str) -> list:
        _validar_juego(juego)
        return self._almacen.comparaciones(juego)

    def lineas(self, juego: str) -> list[str]:
        _validar_juego(juego)
        return self._almacen.lineas(juego)

    def carteras_de_linea(self, juego: str, linea: str) -> list:
        _validar_juego(juego)
        if linea not in self._almacen.lineas(juego):
            raise CarterasError("no_encontrado", f"No hay carteras de la linea {linea}")
        return self._almacen.carteras(juego, linea)

    def simulaciones_de_cartera(self, clave: str) -> list[GuardadoCarteras]:
        cartera = self.cartera(clave)
        return [s for s in self._almacen.simulaciones(cartera.juego)
                if isinstance(s, GuardadoCarteras) and s.artefacto["identidad"]["cartera"] == clave]

    def estado_frente_a_la_base(self, artefacto: dict) -> dict:
        """Historico hasta el corte y base actual (lectura)."""
        completo = self._historico_o_none(artefacto["juego"])
        if completo is None:
            return {"estado": "base_no_disponible", "historico_hasta_el_corte": "no_disponible"}
        corte = artefacto["datos"]["corte"]
        hasta = [r for r in completo if r.numero_sorteo <= corte]
        try:
            actual = lv.validar_instantanea(artefacto["juego"], hasta).huella() if hasta else None
        except lv.HistoricoNoValidoError:
            actual = "no_valido"
        ultimo = max((r.numero_sorteo for r in completo), default=None)
        return {"estado": "disponible",
                "historico_hasta_el_corte": ("no_disponible" if actual is None else
                                             "coincide" if actual == artefacto["datos"]["sha256_historico"] else "cambio"),
                "ultimo_sorteo_actual": ultimo, "base_avanzo": ultimo is not None and ultimo > corte,
                "nuevos_desde_el_corte": sum(1 for r in completo if r.numero_sorteo > corte)}

    def observado_de_cartera(self, artefacto: dict) -> dict:
        return ca.estado_frente_a_la_base(artefacto, self._historico_o_none(artefacto["juego"]))

    def exportar_csv(self, clave: str) -> str:
        return ca.csv_de_cartera(self.cartera(clave).artefacto)

    # ------------------------------------------------------------------
    # Configuracion
    # ------------------------------------------------------------------

    def configurar(self, juego: str, modelo: str, cantidad: int, diversidad: str, semilla: int,
                   perfil: str = "predeterminado", origen: str = "web") -> GuardadoCarteras:
        _validar_juego(juego)
        if modelo not in ce.modelos_de_cartera(juego):
            raise CarterasError("no_valido", f"modelo no admitido para {juego}: {modelo!r}")
        if perfil not in lm.PERFILES:
            raise CarterasError("no_valido", f"perfil admitido: {', '.join(lm.PERFILES)}")
        try:
            cc.validar_parametros(cantidad, semilla, diversidad)
        except cc.ParametrosNoValidos as error:
            raise CarterasError("no_valido", str(error)) from error
        ahora = self._reloj().isoformat()

        def crear(version: int) -> dict:
            return ca.componer(ca.cuerpo_de_configuracion(juego, version, modelo, perfil, cantidad, diversidad, semilla),
                               "registro", {"guardada_en": ahora, "origen": origen,
                                            "nota": "configuracion explicita; versiones anteriores inmutables"})
        return self._almacen.guardar_configuracion(juego, crear)

    def configuraciones(self, juego: str) -> list:
        _validar_juego(juego)
        return self._almacen.configuraciones(juego)

    def configuracion_vigente(self, juego: str) -> GuardadoCarteras | None:
        """La version mas alta. Si esta alterada no se usa otra mas antigua."""
        versiones = self._almacen.configuraciones(juego)
        if not versiones:
            return None
        ultima = versiones[0]
        if not isinstance(ultima, GuardadoCarteras):
            raise CarterasError("alterado", f"la configuracion vigente de {juego} ({ultima.identificador}) esta "
                                            f"alterada o ilegible ({ultima.motivo}); no se usa una version anterior")
        return ultima

    def _configuracion_para_mostrar(self, juego: str) -> dict | None:
        try:
            g = self.configuracion_vigente(juego)
        except CarterasError as error:
            return {"estado": "alterada", "mensaje": str(error)}
        return None if g is None else {"estado": "vigente", **g.artefacto}

    # ------------------------------------------------------------------
    # Verificacion
    # ------------------------------------------------------------------

    def _base_de(self, guardado) -> dict:
        return {"integridad": "correcta" if isinstance(guardado, GuardadoCarteras) else "alterado"}

    def verificar_comparacion(self, clave: str) -> dict:
        guardado = self._almacen.obtener_comparacion(clave)
        if guardado is None:
            raise CarterasError("no_encontrado", f"No existe la comparacion {clave}")
        if not isinstance(guardado, GuardadoCarteras):
            return {"comparacion": clave, "integridad": "alterado", "motivo": guardado.motivo, "reproduccion": None,
                    "base_actual": None}
        a = guardado.artefacto
        salida = {"comparacion": clave, "integridad": "correcta", "mismo_entorno": a["identidad"]["entorno"] == ca.entorno()}
        try:
            ca.comprobar_recetas(a)
            instantanea = ca.instantanea_de(a)
            evaluacion, _ = self._ejecutor.comparar(instantanea, ca.protocolo_de(a))
            salida["reproduccion"] = ca.comparar_reproduccion(a, ca.cuerpo_de_comparacion(instantanea, a["identidad"],
                                                                                           evaluacion))
        except (ca.ArtefactoCarterasError, lv.HistoricoNoValidoError, ce.MuestraInsuficienteCarteras,
                TrabajadorFallidoError) as error:
            salida["reproduccion"] = {"estado": "no_reproducible", "motivo": str(error)}
        salida["base_actual"] = self.estado_frente_a_la_base(a)
        return salida

    def verificar_cartera(self, clave: str) -> dict:
        guardado = self._almacen.obtener_cartera(clave)
        if guardado is None:
            raise CarterasError("no_encontrado", f"No existe la cartera {clave}")
        if not isinstance(guardado, GuardadoCarteras):
            return {"cartera": clave, "integridad": "alterado", "motivo": guardado.motivo, "reproduccion": None,
                    "base_actual": None}
        a = guardado.artefacto
        salida = {"cartera": clave, "integridad": "correcta", "mismo_entorno": a["identidad"]["entorno"] == ca.entorno()}
        try:
            ca.comprobar_recetas(a)
            instantanea = ca.instantanea_de(a)
            modelo, perfil = a["identidad"]["modelo"]["id"], a["identidad"]["perfil"]
            fuente = (ce.fuente(instantanea, modelo, perfil) if ca.es_uniforme(modelo)
                      else self._ejecutor.fuente(instantanea, modelo, perfil))
            salida["reproduccion"] = ca.comparar_cartera(a, ca.cuerpo_de_cartera(instantanea, a["identidad"], fuente))
        except (ca.ArtefactoCarterasError, lv.HistoricoNoValidoError, ce.MuestraInsuficienteCarteras,
                lm.CandidatoNoDisponible, ce.ComponenteNoDisponible, TrabajadorFallidoError) as error:
            salida["reproduccion"] = {"estado": "no_reproducible", "motivo": str(error)}
        completo = self._historico_o_none(a["juego"])
        salida["base_actual"] = ca.estado_frente_a_la_base(a, completo)
        return salida

    def verificar_simulacion(self, clave: str) -> dict:
        guardado = self._almacen.obtener_simulacion(clave)
        if guardado is None:
            raise CarterasError("no_encontrado", f"No existe la simulacion {clave}")
        if not isinstance(guardado, GuardadoCarteras):
            return {"simulacion": clave, "integridad": "alterado", "motivo": guardado.motivo, "reproduccion": None}
        a = guardado.artefacto
        salida = {"simulacion": clave, "integridad": "correcta", "mismo_entorno": a["identidad"]["entorno"] == ca.entorno()}
        try:
            elegida = self.cartera(a["identidad"]["cartera"]).artefacto
            uniforme = self.cartera(a["identidad"]["cartera_uniforme"]).artefacto
            if ca.huella(elegida["fuente"]) != a["identidad"]["fuente_sha256"]:
                raise ca.ArtefactoCarterasError("el vector fuente de la cartera no coincide con el de la simulacion")
            recalculado = self._ejecutor.simular(a["identidad"], elegida, uniforme)
            salida["reproduccion"] = {"huella_exacta": ca.huella(ca.cuerpo_de(a)) == ca.huella(recalculado),
                                      "mismos_conteos": a["resultados"] == recalculado["resultados"]}
        except (CarterasError, ca.ArtefactoCarterasError, TrabajadorFallidoError, cs.SimulacionNoValida) as error:
            salida["reproduccion"] = {"estado": "no_reproducible", "motivo": str(error)}
        return salida

    # ------------------------------------------------------------------
    # Seguimiento
    # ------------------------------------------------------------------

    def seguimiento(self, juego: str, linea: str | None = None, tipo: str = "seguimiento") -> dict:
        _validar_juego(juego)
        if tipo not in ("seguimiento", "retrospectiva"):
            raise CarterasError("no_valido", "tipo admitido: seguimiento o retrospectiva")
        lineas = self._almacen.lineas(juego)
        if linea is not None:
            if linea not in lineas:
                raise CarterasError("no_encontrado", f"No hay carteras de la linea {linea}")
            lineas = [linea]
        completo = self._historico_o_none(juego)
        por_linea = {}
        for nombre in lineas:
            elementos = []
            for e in self._almacen.carteras(juego, nombre):
                if isinstance(e, GuardadoCarteras):
                    elementos.append({"objetivo": e.objetivo, "secuencia": e.secuencia, "identificador": e.identificador,
                                      "artefacto": e.artefacto})
                else:
                    elementos.append({"objetivo": e.objetivo, "secuencia": None, "identificador": e.identificador,
                                      "artefacto": None, "ilegible": e.motivo})
            por_linea[nombre] = ca.seguimiento_de_linea(elementos, completo)
        return {"juego": juego, "base": "no_disponible" if completo is None else "consultada", "lineas": por_linea,
                "comparacion": ca.comparacion_entre_lineas(por_linea, tipo) if len(por_linea) > 1 else None,
                "nota": ca.NOTA_SEGUIMIENTO}


def _resumen_de_comparacion(e) -> dict:
    if not isinstance(e, GuardadoCarteras):
        return {"clave": e.identificador, "estado": "ilegible", "motivo": e.motivo}
    a = e.artefacto
    ensemble = next(c for c in a["candidatos"] if c["id"] == ce.ID_ENSEMBLE)
    return {"clave": e.identificador, "estado": a["resumen"]["estado"], "corte": a["datos"]["corte"],
            "sorteos": a["datos"]["sorteos"], "terminado_en": a["ejecucion"].get("terminado_en"),
            "objetivos": a["muestra_comun"]["total_objetivos"], "perfil": a["identidad"]["protocolo"]["perfil"],
            "mejor": (a["resumen"]["ranking"] or [{}])[0].get("nombre"),
            "ensemble": ensemble["estado"], "bloques_que_eligieron_la_uniforme":
                a["ensemble"]["bloques_que_eligieron_la_uniforme"], "bloques": len(a["muestra_comun"]["bloques"])}


def reemplazar(guardado: GuardadoCarteras, **cambios) -> GuardadoCarteras:
    return replace(guardado, **cambios)

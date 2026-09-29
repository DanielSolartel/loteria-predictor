"""Tests de la Etapa AE-68, validada: especificacion verificable de las
ocho condiciones del protocolo que AE-66 y AE-67 dejaron sin fijar, mas los
requisitos previos R0 (raiz de confianza) y R9 (puente entre nuestras
entradas y el canal).

Separan tres planos: lo que garantiza el estandar (solo afirmaciones de
AE-67; RFC 9162 cubre certificados, no nuestras entradas), lo que tendria
que garantizar el protocolo hipotetico y lo que exigiria evidencia
operativa. Los recibos, puntos de control y firmas son modelos sinteticos
(HMAC solo modela firmas); no son una implementacion conforme a RFC 9162 ni
una decision sobre el esquema real. Las ocho condiciones, R0 y R9 siguen
`sin_fijar`.

El modulo nuevo se importa dentro de cada prueba para que, sobre la base,
cada regresion falle por separado. Todo sintetico: sin red, relojes o
servicios reales, datos reales, PostgreSQL ni predicciones reales."""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import hmac
import importlib
import inspect
import json
import re
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.application.ml import auditoria_obligaciones_de_aplicacion as ao
from app.application.ml import diseno_regla_prospectiva as dr
from app.application.ml import propuesta_evidencia_temporal_externa as pe
from app.application.ml import propuesta_inferencia_prospectiva as pi
from app.application.ml import registro_prospectivo as rp
from app.application.ml import traslado_condiciones_inferenciales as tc
from app.application.ml import verificacion_primaria_choe_ramdas as vp
from app.application.ml import verificacion_primaria_rfc_sellado_y_transparencia as vr
from app.application.ml.especificacion_evaluacion_prospectiva import ESPECIFICACION_CANDIDATA_AE53

UTC = timezone.utc
PLAZO = datetime(2021, 9, 30, 2, 0, tzinfo=UTC)
MMD = timedelta(hours=24)
CLAVE = ("p" * 64, "BALOTO", 2715)
SECRETOS = {"operador_a": b"secreto-sintetico-a", "operador_b": b"secreto-sintetico-b"}
OCHO = ("identidad_autorizada", "canal_canonico", "unicidad_por_objetivo", "regla_de_duplicados",
        "reloj_de_recepcion", "margen_de_incorporacion", "revision_completa", "calendario_oficial")


def _modulo():
    return importlib.import_module("app.application.ml.especificacion_condiciones_del_protocolo")


def _entrada(contenido, recibido, incluido=None, tipo="prediccion", clave=CLAVE):
    return pe.EntradaBitacora(clave=clave, tipo=tipo, contenido_hash=hashlib.sha256(contenido.encode()).hexdigest(),
                              recibido_en=recibido, incluido_en=incluido or recibido)


def _firmar(m, entrada, firmante, secreto=None):
    mensaje = f"{entrada.contenido_hash}|{entrada.recibido_en.isoformat()}".encode()
    firma = hmac.new(secreto or SECRETOS[firmante], mensaje, hashlib.sha256).hexdigest()
    return m.EntradaFirmada(entrada=entrada, firmante=firmante, firma=firma)


def _firma_valida_hmac(ef):
    """Verificador de prueba: HMAC solo modela firmas."""
    secreto = SECRETOS.get(ef.firmante)
    if secreto is None:
        return False
    mensaje = f"{ef.entrada.contenido_hash}|{ef.entrada.recibido_en.isoformat()}".encode()
    return hmac.compare_digest(ef.firma, hmac.new(secreto, mensaje, hashlib.sha256).hexdigest())


def _plano(valor):
    if dataclasses.is_dataclass(valor):
        return {f.name: _plano(getattr(valor, f.name)) for f in dataclasses.fields(valor)}
    if isinstance(valor, Mapping):
        return {str(k): _plano(v) for k, v in valor.items()}
    if isinstance(valor, (tuple, list)):
        return [_plano(v) for v in valor]
    return valor


def _huella(valor):
    return hashlib.sha256(json.dumps(_plano(valor), sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _todos(m):
    return {**m.REQUISITOS_PREVIOS, **m.CONDICIONES_DEL_PROTOCOLO}


# ---------------------------------------------------------------------------
# Registro, referencias y grafos
# ---------------------------------------------------------------------------

def test_ocho_condiciones_y_dos_requisitos_previos_sin_fijar():
    m = _modulo()
    assert tuple(m.CONDICIONES_DEL_PROTOCOLO) == OCHO == tuple(vr.CONDICIONES_DEL_REPOSITORIO)
    assert tuple(m.REQUISITOS_PREVIOS) == ("declaracion_previa_del_protocolo", "puente_entrada_canal")
    for id_, r in _todos(m).items():
        assert r.id == id_ and r.estado == "sin_fijar", id_
        for campo in ("definicion_verificable", "protocolo", "evidencia_operativa", "contraejemplo",
                      "criterio_para_mantener_pendiente"):
            assert getattr(r, campo), (id_, campo)
        assert r.estandar and r.decisiones_del_operador, id_
    assert set(vr.CONDICIONES_DEL_REPOSITORIO.values()) == {"sin_fijar"}


def test_referencias_al_estandar_solo_de_ae67_y_rfc_9162_solo_certificados():
    m = _modulo()
    afirmaciones = {a.id for a in (*vr.AFIRMACIONES_RFC_3161, *vr.AFIRMACIONES_RFC_9162)}
    for r in _todos(m).values():
        for ref in r.estandar:
            if ref == "ninguno":
                continue
            coincide = re.fullmatch(r"AE-67:(T\d|C\d)( solo_certificados)?", ref)
            assert coincide and coincide.group(1) in afirmaciones, (r.id, ref)
            if coincide.group(1).startswith("C"):
                assert ref.endswith("solo_certificados"), (r.id, ref)
    assert m.CONDICIONES_DEL_PROTOCOLO["calendario_oficial"].estandar == ("ninguno",)
    assert "certificados y precertificados" in m.ALCANCE_RFC_9162


def test_correspondencia_con_ae66_sin_renombrar():
    m = _modulo()
    assert set(m.CORRESPONDENCIA_CON_AE66) == set(pe.CONDICIONES_PENDIENTES_DEL_PROTOCOLO) | {
        "complemento_K_y_preguntas_abiertas"}
    cubiertas = {c for destinos in m.CORRESPONDENCIA_CON_AE66.values() for c in destinos}
    assert cubiertas == set(OCHO)
    assert m.CORRESPONDENCIA_CON_AE66["recepcion_antes_del_plazo"] == ("reloj_de_recepcion",
                                                                       "margen_de_incorporacion")


def _orden_topologico(grafo):
    pendientes, orden = dict(grafo), []
    while pendientes:
        libres = [n for n, deps in pendientes.items() if all(d in orden for d in deps)]
        if not libres:
            raise AssertionError(f"ciclo entre {sorted(pendientes)}")
        for n in sorted(libres):
            orden.append(n)
            del pendientes[n]
    return orden


def test_grafos_normativo_y_de_verificacion_aciclicos():
    m = _modulo()
    todos = set(_todos(m))
    assert set(m.DEPENDENCIAS_NORMATIVAS) == {"declaracion_previa_del_protocolo"}
    assert set(m.DEPENDENCIAS_NORMATIVAS["declaracion_previa_del_protocolo"]) == todos - {
        "declaracion_previa_del_protocolo"}
    grafo = m.DEPENDENCIAS_DE_VERIFICACION
    assert set(grafo) == todos
    orden = _orden_topologico(grafo)
    assert orden[0] == "declaracion_previa_del_protocolo"
    assert [n for n, deps in grafo.items() if not deps] == ["declaracion_previa_del_protocolo"]
    for id_ in ("identidad_autorizada", "canal_canonico", "calendario_oficial"):
        assert grafo[id_] == ("declaracion_previa_del_protocolo",), id_
    assert "canal_canonico" not in grafo["identidad_autorizada"]
    assert "identidad_autorizada" not in grafo["canal_canonico"]
    for id_, r in _todos(m).items():
        assert r.verificacion_depende_de == grafo[id_], id_


def test_autenticacion_de_r0_pendiente():
    m = _modulo()
    assert tuple(m.AUTENTICACION_DE_R0) == ("sello_externo_anterior_al_corte", "publicacion_fuera_de_banda",
                                            "reconocimiento_del_operador")
    for elemento in m.AUTENTICACION_DE_R0.values():
        assert elemento["estado"] == "pendiente" and elemento["texto"]


def test_hipotesis_temporales_como_requisitos_del_canal_sintetico():
    m = _modulo()
    h = m.HIPOTESIS_TEMPORALES
    assert tuple(h) == ("H1", "H2", "H3", "H4", "H5")
    for id_, hip in h.items():
        assert hip["origen"] == "requisito_del_canal_sintetico_no_garantia_de_rfc_9162", id_
        assert hip["estado"] == "sin_fijar", id_
    assert "todo punto de control con t_sth >= t_rec + MMD contiene" in h["H2"]["texto"]
    assert "incorporada en un instante <= t_sth" in h["H3"]["texto"]
    assert "cota declarada y comprobable del error" in h["H5"]["texto"]
    assert "formato UTC no prueba" in h["H5"]["texto"]
    assert set(m.INSTANTES) == {"t_rec", "t_sct", "t_sth", "t_consulta"}
    assert "solo para entradas de RFC 9162" in m.INSTANTES["t_sct"]


# ---------------------------------------------------------------------------
# Identidad (firma inyectada; HMAC solo en las pruebas)
# ---------------------------------------------------------------------------

def test_identidad_con_verificador_inyectado_y_revocacion():
    m = _modulo()
    antes = PLAZO - timedelta(hours=1)
    buena = _firmar(m, _entrada("a", antes), "operador_a")
    desconocida = _firmar(m, _entrada("b", antes), "intruso", secreto=b"otro")
    firma_mala = dataclasses.replace(_firmar(m, _entrada("c", antes), "operador_a"), firma="0" * 64)
    revocada = _firmar(m, _entrada("d", antes), "operador_b")
    vigencias = {"operador_a": (PLAZO - timedelta(days=30), None),
                 "operador_b": (PLAZO - timedelta(days=30), PLAZO - timedelta(hours=2))}
    admisibles = m.entradas_admisibles((buena, desconocida, firma_mala, revocada), _firma_valida_hmac, vigencias)
    assert admisibles == (buena,)
    assert "no es una decision" in m.MODELO_DE_FIRMA


# ---------------------------------------------------------------------------
# Conflictos y regla de duplicados (comportamiento observable)
# ---------------------------------------------------------------------------

def test_reintento_identico_frente_a_contenidos_incompatibles():
    m = _modulo()
    t = PLAZO - timedelta(hours=1)
    reintento = (_entrada("x", t), _entrada("x", t + timedelta(minutes=1)))
    (registro,) = m.registrar_conflictos(reintento)
    assert registro.clase == "reintento_identico" and registro.total == 2
    incompatibles = (_entrada("x", t), _entrada("y", t + timedelta(minutes=1)))
    (registro,) = m.registrar_conflictos(incompatibles)
    assert registro.clase == "contenidos_incompatibles" and len(registro.hashes) == 2
    prediccion_y_omision = (_entrada("x", t), _entrada("omision", t, tipo="omision_declarada"))
    (registro,) = m.registrar_conflictos(prediccion_y_omision)
    assert registro.clase == "contenidos_incompatibles"
    assert set(registro.tipos) == {"prediccion", "omision_declarada"}
    assert m.registrar_conflictos((_entrada("x", t),)) == ()


def test_conflicto_registrado_persiste_tras_invalidar_el_objetivo():
    m = _modulo()
    t = PLAZO - timedelta(hours=1)
    vista = (_entrada("x", t), _entrada("y", t + timedelta(minutes=1)))
    resoluciones, registro = m.aplicar_regla(vista, "invalidar_objetivo")
    (resolucion,) = resoluciones
    assert resolucion.efecto == "objetivo_invalidado" and resolucion.entrada is None
    assert len(registro) == 1 and registro[0].clase == "contenidos_incompatibles"
    assert registro == m.registrar_conflictos(vista)


def test_primera_recibida_por_t_rec_y_no_por_indice():
    m = _modulo()
    tardia = _entrada("tardia", PLAZO - timedelta(minutes=10))
    temprana = _entrada("temprana", PLAZO - timedelta(hours=3))
    vista = (tardia, temprana)  # el indice de hoja no sigue el orden cronologico
    assert m.ordenar_por_recepcion(vista) == (temprana, tardia)
    (resolucion,), registro = m.aplicar_regla(vista, "primera_recibida")
    assert resolucion.entrada == temprana and resolucion.efecto == "conservar"
    assert registro[0].clase == "contenidos_incompatibles"
    (resolucion,), _ = m.aplicar_regla((_entrada("x", temprana.recibido_en), _entrada("x", tardia.recibido_en)),
                                       "invalidar_objetivo")
    assert resolucion.efecto == "conservar"  # un reintento identico no es un conflicto


def test_reglas_candidatas_no_dependen_del_resultado():
    m = _modulo()
    assert set(m.REGLAS_DE_DUPLICADOS_CANDIDATAS) == {"primera_recibida", "invalidar_objetivo", "invalidar_protocolo"}
    t = PLAZO - timedelta(hours=1)
    vista = (_entrada("x", t), _entrada("y", t + timedelta(minutes=1)))
    for nombre, regla in m.REGLAS_DE_DUPLICADOS_CANDIDATAS.items():
        assert m.es_regla_admisible(regla), nombre
        salidas = {sorteo: m.aplicar_regla(vista, nombre) for sorteo in ((1, 2, 3, 4, 5), (39, 40, 41, 42, 43))}
        assert len({repr(s) for s in salidas.values()}) == 1, nombre
    puntuacion = {vista[0].contenido_hash: {"a": 0.1, "b": 0.9}, vista[1].contenido_hash: {"a": 0.9, "b": 0.1}}

    def elegir_la_mejor(entradas, registro, resultado):  # contraejemplo: seleccion por resultado
        return max(entradas, key=lambda e: puntuacion[e.contenido_hash][resultado])

    assert elegir_la_mejor(vista, None, "a") != elegir_la_mejor(vista, None, "b")
    assert not m.es_regla_admisible(elegir_la_mejor)
    assert m.REGLA_DE_DUPLICADOS_ELEGIDA is None


# ---------------------------------------------------------------------------
# Puntos de control: H2 (compromiso) y H3 (coherencia con la marca)
# ---------------------------------------------------------------------------

def test_punto_de_control_fechado_sobre_una_vista_antigua_incompleta_se_detecta():
    m = _modulo()
    t_rec = PLAZO - timedelta(minutes=1)
    recibo = m.ReciboSintetico(hash_entrada="h1", t_rec=t_rec)
    incorporaciones = {"h0": PLAZO - timedelta(days=2), "h1": t_rec + 0.9 * MMD}
    honesto = m.punto_de_control_coherente_sintetico(incorporaciones, PLAZO + MMD)
    assert "h1" in honesto.hashes
    assert m.punto_de_control_es_coherente(honesto, incorporaciones)
    assert m.cumple_compromiso_de_incorporacion(honesto, (recibo,), MMD)
    antiguo = m.punto_de_control_coherente_sintetico(incorporaciones, PLAZO - timedelta(days=1))
    refechado = dataclasses.replace(antiguo, t_sth=PLAZO + MMD)  # marca reciente sobre una vista antigua
    assert "h1" not in refechado.hashes
    assert not m.punto_de_control_es_coherente(refechado, incorporaciones)
    assert not m.cumple_compromiso_de_incorporacion(refechado, (recibo,), MMD)


def test_umbrales_de_incorporacion_por_marca_y_por_consulta():
    m = _modulo()
    reloj = m.RelojDeclarado(cota_error=timedelta(seconds=2), resolucion=timedelta(milliseconds=1))
    t_rec = PLAZO - timedelta(minutes=1)
    incorporaciones = {"h1": t_rec + 0.9 * MMD}
    temprano = m.punto_de_control_coherente_sintetico(incorporaciones, PLAZO + 0.5 * MMD)
    assert "h1" not in temprano.hashes
    por_marca = m.umbral_de_punto_de_control(PLAZO, MMD, "marca_de_punto_de_control", reloj)
    assert por_marca.instante == PLAZO + MMD + reloj.incertidumbre()
    assert por_marca.hipotesis == ("H1", "H2", "H3", "H5")
    assert "h1" in m.punto_de_control_coherente_sintetico(incorporaciones, por_marca.instante).hashes
    por_consulta = m.umbral_de_punto_de_control(PLAZO, MMD, "hora_de_consulta", reloj)
    assert por_consulta.instante == PLAZO + 2 * MMD + reloj.incertidumbre()
    assert por_consulta.hipotesis == ("H1", "H2", "H3", "H4", "H5")
    consulta = PLAZO + 1.5 * MMD
    servido = m.punto_de_control_coherente_sintetico(incorporaciones, consulta - MMD)  # H4: hasta un MMD antiguo
    assert "h1" not in servido.hashes and consulta < por_consulta.instante
    sin_cota = m.umbral_de_punto_de_control(PLAZO, MMD, "marca_de_punto_de_control",
                                            m.RelojDeclarado(cota_error=None, resolucion=timedelta(milliseconds=1)))
    assert sin_cota.instante is None and sin_cota.estado == "cota_de_error_sin_declarar_pendiente"


def test_envio_censurado_sin_recibo_no_aparece_en_ningun_punto_reciente():
    m = _modulo()
    incorporaciones = {"h0": PLAZO - timedelta(hours=5)}  # "h_censurado" se envio pero nunca tuvo recibo
    reciente = m.punto_de_control_coherente_sintetico(incorporaciones, PLAZO + 10 * MMD)
    assert m.punto_de_control_es_coherente(reciente, incorporaciones)
    assert m.cumple_compromiso_de_incorporacion(reciente, (), MMD)
    assert "h_censurado" not in reciente.hashes
    assert "no acredita que el canal recibiera" in m.LIMITE_DE_COMPLETITUD


def test_incorporacion_tardia_viola_h2_y_solo_se_detecta_con_el_recibo():
    m = _modulo()
    t_rec = PLAZO - timedelta(minutes=1)
    recibo = m.ReciboSintetico(hash_entrada="h1", t_rec=t_rec)
    incorporaciones = {"h1": t_rec + 1.5 * MMD}  # el canal incumple su compromiso
    punto = m.punto_de_control_coherente_sintetico(incorporaciones, t_rec + MMD + timedelta(hours=1))
    assert m.punto_de_control_es_coherente(punto, incorporaciones)
    assert not m.cumple_compromiso_de_incorporacion(punto, (recibo,), MMD)
    assert m.cumple_compromiso_de_incorporacion(punto, (), MMD)  # sin el recibo no se ve


# ---------------------------------------------------------------------------
# Reloj: cota de error, resolucion y zona
# ---------------------------------------------------------------------------

def test_desfase_de_reloj_cercano_al_limite():
    m = _modulo()
    reloj = m.RelojDeclarado(cota_error=timedelta(seconds=2), resolucion=timedelta(0))
    assert m.RESULTADOS_RELOJ == ("anterior_con_margen_de_reloj", "no_concluyente_por_error_de_reloj",
                                  "posterior_con_margen_de_reloj", "cota_de_error_sin_declarar_pendiente")
    # Marca un segundo antes del plazo, pero el reloj del canal adelanta 1,9 s dentro de su cota:
    marca = PLAZO - timedelta(seconds=1)
    instante_real = marca + timedelta(seconds=1.9)
    assert instante_real > PLAZO
    assert m.comparar_con_plazo(marca, PLAZO, reloj) == "no_concluyente_por_error_de_reloj"
    assert m.comparar_con_plazo(PLAZO - timedelta(seconds=2.1), PLAZO, reloj) == "anterior_con_margen_de_reloj"
    assert m.comparar_con_plazo(PLAZO - timedelta(seconds=2), PLAZO, reloj) == "no_concluyente_por_error_de_reloj"
    assert m.comparar_con_plazo(PLAZO + timedelta(seconds=2), PLAZO, reloj) == "posterior_con_margen_de_reloj"
    con_resolucion = m.RelojDeclarado(cota_error=timedelta(seconds=2), resolucion=timedelta(seconds=1))
    assert m.comparar_con_plazo(PLAZO - timedelta(seconds=2.5), PLAZO, con_resolucion) == \
        "no_concluyente_por_error_de_reloj"
    for resultado in m.RESULTADOS_RELOJ:
        assert "acreditad" not in resultado


def test_marca_en_formato_utc_sin_cota_no_prueba_exactitud():
    m = _modulo()
    sin_cota = m.RelojDeclarado(cota_error=None, resolucion=timedelta(milliseconds=1))
    marca_utc = datetime(2021, 9, 29, 20, 0, tzinfo=UTC)  # muy anterior, con zona UTC
    assert m.comparar_con_plazo(marca_utc, PLAZO, sin_cota) == "cota_de_error_sin_declarar_pendiente"
    with pytest.raises(ValueError):
        m.comparar_con_plazo(datetime(2021, 9, 29, 20, 0), PLAZO, m.RelojDeclarado(timedelta(seconds=1),
                                                                                  timedelta(0)))
    with pytest.raises(ValueError):
        m.RelojDeclarado(cota_error=timedelta(seconds=-1), resolucion=timedelta(0))


# ---------------------------------------------------------------------------
# Vias de ausencia en escenarios hipoteticos
# ---------------------------------------------------------------------------

def test_vias_en_escenarios_hipoteticos_sin_tocar_los_estados_reales():
    m = _modulo()
    todo = {k: True for k in m.REQUISITOS_DE_VIA["via_1_omision_declarada"]}
    assert m.estado_hipotetico_de_via("via_1_omision_declarada", todo) == \
        "hipotesis_completa_sin_evidencia_operativa_ni_resolucion_de_vistas_divididas"
    todo_2 = {k: True for k in m.REQUISITOS_DE_VIA["via_2_ausencia_inferida"]}
    assert m.estado_hipotetico_de_via("via_2_ausencia_inferida", todo_2) == \
        "hipotesis_completa_pendiente_de_envios_sin_recibo_y_vistas_divididas"
    for via, requisitos in m.REQUISITOS_DE_VIA.items():
        assert "politica_de_vistas_divididas" in requisitos, via
        for faltante in requisitos:
            escenario = {k: k != faltante for k in requisitos}
            assert m.estado_hipotetico_de_via(via, escenario) == "pendiente", (via, faltante)
        assert m.estado_hipotetico_de_via(via, {}) == "pendiente"
    assert "tratamiento_de_envios_sin_recibo" in m.REQUISITOS_DE_VIA["via_2_ausencia_inferida"]
    assert {"revision_completa", "margen_de_incorporacion", "regla_de_duplicados"} <= set(
        m.REQUISITOS_DE_VIA["via_1_omision_declarada"])
    with pytest.raises(ValueError):
        m.estado_hipotetico_de_via("via_1_omision_declarada", {"clave_inventada": True})
    assert {r.estado for r in _todos(m).values()} == {"sin_fijar"}
    for resultado in m.RESULTADOS_DE_VIA:
        assert "acreditad" not in resultado


# ---------------------------------------------------------------------------
# Estados, pureza, vocabulario e invariante
# ---------------------------------------------------------------------------

def test_estados_y_decisiones_sin_cambios():
    _modulo()
    condiciones = {c.id: c.estado for c in tc.CONDICIONES_DE_TRASLADO}
    for id_ in ("F1_anterioridad", "F2_correspondencia_de_la_filtracion", "O3_tratamiento_de_omisiones",
                "N2_inversion_para_p1b", "U1_usos_de_1_sobre_E"):
        assert condiciones[id_] == "pendiente", id_
    for id_ in ("F2_correspondencia_de_la_filtracion", "N2_inversion_para_p1b", "U1_usos_de_1_sobre_E"):
        assert vp.ESTADOS_TRAS_AE64[id_]["estado"] == "pendiente", id_
    for o in ao.OBLIGACIONES_AE65.values():
        assert o.estado == "pendiente", o.id
    (sellado,) = [d for d in pi.DECISIONES_REQUERIDAS if d.id == "mecanismo_de_sellado_temporal_externo"]
    assert sellado.valor is None and sellado.estado == "sin_decidir"
    assert pe.RECOMENDACION_CONDICIONAL["estado"] == "recomendacion_condicional_para_decision_del_operador"


def test_modulo_puro_sin_red_ni_reloj():
    m = _modulo()
    arbol = ast.parse(Path(m.__file__).read_text(encoding="utf-8"))
    prohibidos = {"socket", "urllib", "requests", "http", "time", "subprocess"}
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            assert not {a.name.split(".")[0] for a in nodo.names} & prohibidos
        if isinstance(nodo, ast.ImportFrom):
            assert (nodo.module or "").split(".")[0] not in prohibidos
        if isinstance(nodo, ast.Attribute):
            assert nodo.attr not in {"now", "utcnow", "today"}, nodo.attr
    assert inspect.signature(m.estado_hipotetico_de_via).parameters.keys() == {"via", "escenario"}


_PROHIBIDAS = {"aprobado", "aprobada", "aprobados", "aprobadas", "go", "cumplido", "cumplida", "desbloqueado",
               "desbloqueada", "autorizado", "autorizada", "recomendado", "recomendada", "elegido", "elegida"}


def test_textos_sin_aprobacion_ni_autorizacion():
    m = _modulo()
    textos = [m.ALCANCE_RFC_9162, m.LIMITE_DE_COMPLETITUD, m.MODELO_DE_FIRMA, *m.INSTANTES.values()]
    textos += [h["texto"] for h in m.HIPOTESIS_TEMPORALES.values()]
    textos += [e["texto"] for e in m.AUTENTICACION_DE_R0.values()]
    for r in _todos(m).values():
        textos += [r.definicion_verificable, r.protocolo, r.evidencia_operativa, r.contraejemplo,
                   r.criterio_para_mantener_pendiente, *r.decisiones_del_operador]
    fijos = "|".join(sorted({*OCHO, *m.REQUISITOS_PREVIOS}, key=len, reverse=True))
    textos = [re.sub(fijos, " ", t) for t in textos]
    palabras = {p.lower() for t in textos for p in re.split(r"[^A-Za-z]+", t) if p}
    assert not palabras & _PROHIBIDAS, palabras & _PROHIBIDAS


def test_estado_bloqueos_y_registros_intactos():
    assert pi.ESTADO_EXPEDIENTE == "expediente_sin_eleccion"
    assert pi.AUTORIZA_EVALUACION is False
    for decision in (*pi.DECISIONES_INFERENCIALES_ABIERTAS.values(), *pi.DECISIONES_REQUERIDAS):
        assert decision.valor is None and decision.estado == "sin_decidir"
    pi.verificar_expediente()
    assert len(rp.PENDIENTES_BORRADOR_AE52) == 7
    assert ESPECIFICACION_CANDIDATA_AE53["estado"] == "candidata_no_aprobada"
    assert dr.huella_diseno() == "6743293d4e247c17ed5f9c098824caf4f740873f00a04d4e223f334874f8de3c"
    assert _huella((tc.CONDICIONES_DE_TRASLADO, tc.DECISIONES_DEL_OPERADOR_AE63,
                    tc.ENUNCIADOS_DE_FUENTE_NECESARIOS)) == (
        "2600313c17c65eab1b6f69c5a9abe3708f87f951df57edca6266ef46bc014186")
    assert _huella((vp.PROCEDENCIA_V6, vp.LECTURA_POR_PUNTO, vp.ENUNCIADOS_NULAS_Y_E_PROCESOS, vp.DISCREPANCIAS,
                    vp.DEPENDENCIAS_DE_N2, vp.DERIVACION_1_SOBRE_E_TEOREMA_3, vp.ESTADOS_TRAS_AE64)) == (
        "631091da5a81a5097ad2d840043085fd43cec1929dcddd17644222121e91e054")
    assert _huella((ao.OBLIGACIONES_AE65, ao.EVIDENCIA_REQUERIDA_O3, ao.ASPECTOS_DE_PREDICTIBILIDAD,
                    ao.COMPONENTES_DE_F2, ao.CONSECUENCIAS, ao.OBSERVACION_DEPENDENCIA_O3_COMUN,
                    ao.HIPOTESIS_UNIFORMIDAD_CONDICIONAL, ao.NIVELES_DE_ANTERIORIDAD, ao.USOS)) == (
        "209cf5282031f5489c5f75e7497cc680dd15f73b190144491e4fbea36ea03b7f")
    assert _huella((pe.REQUISITOS, pe.COLUMNAS_DE_LA_MATRIZ, pe.ESTADOS_DE_CELDA, pe.RESULTADOS_OMISION_DECLARADA,
                    pe.RESULTADOS_AUSENCIA_INFERIDA, pe.FUENTES_PRIMARIAS, pe.ALTERNATIVAS, pe.COMPLEMENTOS,
                    pe.CONDICIONES_PENDIENTES_DEL_PROTOCOLO, pe.NO_DEMUESTRA_NINGUNA, pe.PREGUNTAS_ABIERTAS,
                    pe.RECOMENDACION_CONDICIONAL)) == (
        "17f9e0ba301092c76fc412063d5ad5f764dd6412d8feaeb76cd307ef018c639a")
    assert _huella((vr.PROCEDENCIA_RFC, vr.ESTADOS_AFIRMACION, vr.AFIRMACIONES_RFC_3161, vr.AFIRMACIONES_RFC_9162,
                    vr.CONDICIONES_DEL_REPOSITORIO, vr.DISCREPANCIAS_CON_AE66, vr.DERIVACION_MARGEN_RFC_9162,
                    vr.RESULTADOS_SELLO)) == (
        "eb094cddc0659b3b4e015922025db9ca3327116d10677677a26224270da857c5")

"""Tests de la Etapa AE-77, validada localmente como trabajo preparatorio:
expediente de recepcion por
objetivo con tiempo por acuse (C2) y conjunto esperado externo (C3).

G1  funcionalidad nueva (sobre la base falla):
    - modulo `recepcion_por_objetivo`, importado dentro de cada prueba
      (`ModuleNotFoundError`);
    - `verificar_token_sobre_bytes` de AE-75 (`AttributeError`).
G2  invariantes de AE-52 y AE-74 a AE-76: huellas, bytes, hashes y estados.
G3  premisas sobre el codigo existente.

Todo sintetico: claves, certificados, TSA y observador de fixture; ningun
resultado eleva `r0_final` ni `AUTORIZA_EVALUACION`, y la autoridad del
manifiesto y la completitud global quedan pendientes."""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import importlib
import json
import re
from collections.abc import Mapping
from pathlib import Path

import pytest

from app.application.ml import contrato_vinculo_r0 as cv
from app.application.ml import especificacion_condiciones_del_protocolo as ec
from app.application.ml import expediente_r0_recepcion as ex
from app.application.ml import propuesta_inferencia_prospectiva as pi
from app.application.ml import prototipo_vinculo_declaracion_r0 as pv
from app.application.ml import registro_prospectivo as rp
from app.application.ml import sello_temporal_r0 as st
from tests.unit.ml import fixtures_expediente_r0 as fx
from tests.unit.ml import fixtures_recepcion_por_objetivo as fo
from tests.unit.ml import fixtures_sello_temporal as fs
from tests.unit.simulaciones import sinteticos


def _m():
    return importlib.import_module("app.application.ml.recepcion_por_objetivo")


def _plano(valor):
    if dataclasses.is_dataclass(valor):
        return {f.name: _plano(getattr(valor, f.name)) for f in dataclasses.fields(valor)}
    if isinstance(valor, Mapping):
        return {str(k): _plano(v) for k, v in valor.items()}
    if isinstance(valor, (tuple, list, set, frozenset)):
        return [_plano(v) for v in (sorted(valor) if isinstance(valor, (set, frozenset)) else valor)]
    return valor


def _huella(valor):
    return hashlib.sha256(json.dumps(_plano(valor), sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _base():
    entradas, bd = fx.registro()
    return entradas, bd, fx.acuses(ex, entradas)


def _tiempo(m, evidencia, *, margen="0", entradas=None):
    entradas = entradas or fx.registro()[0]
    return m.verificar_tiempo_de_acuse(entradas, evidencia, fo.politica_sello(margen), fx.politica(ex),
                                       canal=fx.CANAL)


def _estados(informe):
    return {k: v.estado for k, v in informe.planos.items()}


# ===========================================================================
# G1: tiempo por acuse (C2)
# ===========================================================================

def test_g1_compromiso_de_acuse_canonico_e_inequivoco():
    m = _m()
    entradas, _, acuses = _base()
    c = m.construir_compromiso_de_acuse(entradas, acuses[1], plazo_utc=fo.PLAZO)
    pieza = ex.leer_acuse(acuses[1].datos)
    assert tuple(sorted(c)) == tuple(sorted(m.CLAVES_DEL_COMPROMISO_ACUSE))
    assert c["esquema"] == m.ESQUEMA_COMPROMISO_ACUSE == "compromiso-sello-acuse/1"
    assert c["hash_acuse"] == hashlib.sha256(acuses[1].datos).hexdigest()
    assert c["hash_firma_acuse"] == hashlib.sha256(acuses[1].firma).hexdigest()
    assert c["huella_de_clave_del_canal"] == ex.huella_de_clave(fx.clave_publica("canal"))
    for campo in ("canal", "protocolo_hash", "prediccion_hash", "codigo_juego", "sorteo_objetivo", "secuencia"):
        assert c[campo] == pieza[campo], campo
    assert (c["plazo_utc"], c["procedencia_del_plazo"]) == (fo.PLAZO, "sintetica_de_prueba")
    datos = m.bytes_de_compromiso(c)
    assert datos == rp.serializar_entrada(c) and m.leer_compromiso_de_acuse(datos) == c
    assert datos != m.bytes_de_compromiso(m.construir_compromiso_de_acuse(entradas, acuses[0], plazo_utc=fo.PLAZO))
    with pytest.raises(m.CompromisoDeAcuseInvalido) as error:
        m.leer_compromiso_de_acuse(rp.serializar_entrada({**c, "esquema": "compromiso-sello-acuse/2"}))
    assert error.value.motivo == "version_desconocida"
    for plazo in ("2026-10-10T00:00:00", "2026-10-09T19:00:00-05:00"):
        with pytest.raises(m.CompromisoDeAcuseInvalido) as error:
            m.construir_compromiso_de_acuse(entradas, acuses[1], plazo_utc=plazo)
        assert error.value.motivo == "plazo_sin_utc_explicito"


def test_g1_flujo_correcto_separa_sello_anterioridad_ancla_y_revocacion():
    m = _m()
    entradas, _, acuses = _base()
    informe = _tiempo(m, fo.sellar_acuse(m, entradas, acuses[0], precision=(1, 500, 100)))
    assert tuple(informe.planos) == m.PLANOS_DE_TIEMPO
    assert _estados(informe) == {
        "acuse_firmado": "superada", "vinculo_del_compromiso": "superada", "sello_criptografico": "superada",
        "impronta": "superada", "anterioridad_relativa_al_plazo": "superada", "confianza_en_el_ancla": "pendiente",
        "revocacion": "pendiente"}
    assert informe.conclusion.resultado == "anterior_al_plazo"
    assert informe.conclusion.limite_superior_utc == "2026-10-01T12:00:01.5001Z"
    assert informe.estado == "pendiente"
    assert informe.motivos == ("ancla_de_prueba_no_operativa", "revocacion_sin_comprobar",
                               "plazo_sintetico_sin_calendario_oficial")


@pytest.mark.parametrize("plazo, margen, resultado, estado", [
    ("2026-10-01T12:00:01.500101Z", "0", "anterior_al_plazo", "pendiente"),
    ("2026-10-01T12:00:01.5001Z", "0", "no_concluyente_intervalo_cruza_el_plazo", "no_concluyente"),
    ("2026-10-01T12:00:01.500101Z", "0.25", "no_concluyente_intervalo_cruza_el_plazo", "no_concluyente"),
    ("2026-10-01T11:59:58.4999Z", "0", "posterior_al_plazo", "rechazada"),
])
def test_g1_bordes_del_plazo_con_margen(plazo, margen, resultado, estado):
    m = _m()
    entradas, _, acuses = _base()
    informe = _tiempo(m, fo.sellar_acuse(m, entradas, acuses[0], plazo=plazo, precision=(1, 500, 100)), margen=margen)
    assert informe.conclusion.resultado == resultado
    assert informe.estado == estado


def test_g1_precision_ausente_queda_pendiente():
    m = _m()
    entradas, _, acuses = _base()
    informe = _tiempo(m, fo.sellar_acuse(m, entradas, acuses[0], precision=None))
    assert informe.planos["anterioridad_relativa_al_plazo"].motivos == ("precision_ausente",)
    assert informe.estado == "pendiente"


def test_g1_sello_de_r0_nunca_cuenta_como_sello_del_acuse():
    m = _m()
    entradas, bd, acuses = _base()
    compromiso = st.construir_compromiso(entradas, bd, codigo_juego="BALOTO", sorteo_objetivo=2714, plazo_utc=fo.PLAZO)
    datos = st.bytes_de_compromiso(compromiso)
    respuesta = fs.respuesta(datos, fs.Opciones(gen_time=fs.instante(fo.GEN)))
    informe = _tiempo(m, m.EvidenciaDeSelloDeAcuse(acuses[0], respuesta, datos))
    assert informe.planos["vinculo_del_compromiso"].motivos == ("sello_de_r0_no_cuenta_como_sello_de_acuse",)
    assert informe.estado == "rechazada"
    assert informe.conclusion.resultado == "no_evaluable"


def test_g1_sello_de_otro_acuse_u_otro_objetivo():
    m = _m()
    entradas, _, acuses = _base()
    ajena = fo.sellar_acuse(m, entradas, acuses[1])
    informe = _tiempo(m, m.EvidenciaDeSelloDeAcuse(acuses[0], ajena.respuesta_der, ajena.bytes_compromiso))
    assert "compromiso_de_otro_acuse" in informe.planos["vinculo_del_compromiso"].motivos
    assert informe.estado == "rechazada"
    c = m.construir_compromiso_de_acuse(entradas, acuses[0], plazo_utc=fo.PLAZO)
    c["sorteo_objetivo"] = 2715
    otro = _tiempo(m, fo.sellar_acuse(m, entradas, acuses[0], compromiso=c))
    assert "objetivo_no_coincide" in otro.planos["vinculo_del_compromiso"].motivos


def test_g1_acuse_alterado_o_con_clave_no_admitida():
    m = _m()
    entradas, _, acuses = _base()
    pieza = ex.leer_acuse(acuses[0].datos)
    alterado = fx.firmar(ex, pieza, "canal", alterar=True)
    informe = _tiempo(m, fo.sellar_acuse(m, entradas, acuses[0]))
    assert informe.planos["acuse_firmado"].estado == "superada"
    sello = fo.sellar_acuse(m, entradas, acuses[0])
    roto = m.EvidenciaDeSelloDeAcuse(alterado, sello.respuesta_der, sello.bytes_compromiso)
    assert "firma_no_coincide" in _tiempo(m, roto).planos["acuse_firmado"].motivos
    ajeno = fx.acuses(ex, entradas, clave="ajena")[0]
    r = _tiempo(m, fo.sellar_acuse(m, entradas, ajeno))
    assert "clave_no_admitida" in r.planos["acuse_firmado"].motivos and r.estado == "rechazada"


def test_g1_firma_del_token_alterada_y_impronta_de_otros_bytes():
    m = _m()
    entradas, _, acuses = _base()
    firma = _tiempo(m, fo.sellar_acuse(m, entradas, acuses[0], alterar_firma=True))
    assert firma.planos["sello_criptografico"].estado == "rechazada"
    assert "firma_del_token_no_coincide" in firma.planos["sello_criptografico"].motivos
    assert firma.conclusion.resultado == "no_evaluable"
    evidencia = fo.sellar_acuse(m, entradas, acuses[0])
    otro = m.bytes_de_compromiso(m.construir_compromiso_de_acuse(entradas, acuses[0], plazo_utc="2026-10-11T00:00:00Z"))
    cambiada = _tiempo(m, m.EvidenciaDeSelloDeAcuse(acuses[0], evidencia.respuesta_der, otro))
    assert cambiada.planos["impronta"].motivos == ("impronta_no_coincide",)
    assert cambiada.conclusion.resultado == "no_evaluable"
    politica = _tiempo(m, fo.sellar_acuse(m, entradas, acuses[0], politica=fs.POLITICA_NO_ADMITIDA))
    assert "politica_no_admitida" in politica.planos["sello_criptografico"].motivos


def test_g1_la_hora_declarada_por_el_canal_no_es_prueba():
    """Dos acuses que solo difieren en la hora declarada (1999 y 2099) dan la
    misma conclusion: solo cuentan genTime verificado, accuracy y plazo."""
    m = _m()
    entradas, _, _ = _base()
    resultados = set()
    for hora in ("1999-01-01T00:00:00Z", "2099-12-31T23:59:59Z"):
        pieza = ex.construir_acuse(entradas, canal=fx.CANAL, codigo_juego="BALOTO", sorteo_objetivo=2714,
                                   secuencia=1, acuse_anterior=None, hora_declarada_utc=hora,
                                   clave_publica=fx.clave_publica("canal"))
        informe = _tiempo(m, fo.sellar_acuse(m, entradas, fx.firmar(ex, pieza, "canal")))
        resultados.add((informe.conclusion.resultado, informe.conclusion.gen_time_utc, informe.estado))
    assert resultados == {("anterior_al_plazo", "2026-10-01T12:00:00Z", "pendiente")}


def test_g1_verificacion_criptografica_reutilizada_de_ae75_sin_cambiar_resultados():
    """El envoltorio publico de AE-75 da, para un sello de R0, las mismas
    comprobaciones y la misma impronta que `verificar_sello`."""
    entradas, bd, _ = _base()
    compromiso = st.construir_compromiso(entradas, bd, codigo_juego="BALOTO", sorteo_objetivo=2714, plazo_utc=fo.PLAZO)
    datos = st.bytes_de_compromiso(compromiso)
    for opciones in ({}, {"alterar_firma": True}, {"precision": None}, {"politica": fs.POLITICA_NO_ADMITIDA}):
        respuesta = fs.respuesta(datos, fs.Opciones(gen_time=fs.instante(fo.GEN), **opciones))
        token = st.verificar_token_sobre_bytes(respuesta, datos, fo.politica_sello())
        informe = st.verificar_sello(entradas, bd, st.EvidenciaDeSello(respuesta, datos), fo.politica_sello(),
                                     codigo_juego="BALOTO", sorteo_objetivo=2714)
        assert token.comprobaciones_criptograficas == informe.comprobaciones_criptograficas
        assert token.impronta == informe.vinculo_del_compromiso["impronta_coincide"]


# ===========================================================================
# G1: conjunto esperado externo (C3)
# ===========================================================================

def _conjunto(m, declaracion, *, acuses=None, cierre=None, corte=2716, registro=None, politica_obs=None):
    entradas = (registro or fx.registro())[0]
    acuses = acuses if acuses is not None else fx.acuses(ex, entradas)
    cierre = cierre if cierre is not None else fx.cierre(ex, entradas, acuses)
    return m.comparar_con_conjunto_esperado(entradas, declaracion, acuses, cierre, politica_obs or fo.politica_observadores(m),
                                           fx.politica(ex), canal=fx.CANAL, corte_esperado=corte)


def test_g1_conjunto_esperado_canonico_y_firmado_por_observador_independiente():
    m = _m()
    entradas, _, _ = _base()
    d = fo.declaracion(m, ex, entradas)
    pieza = m.leer_conjunto_esperado(d.datos)
    assert tuple(sorted(pieza)) == tuple(sorted(m.CLAVES_DEL_CONJUNTO))
    assert pieza["esquema"] == m.ESQUEMA_CONJUNTO == "conjunto-esperado-observador/1"
    assert pieza["objetivos_esperados"] == [["BALOTO", 2714], ["BALOTO", 2715], ["BALOTO", 2716]]
    assert pieza["protocolo_hash"] == rp.hash_entrada(entradas[0])
    informe = _conjunto(m, d)
    assert informe.estado == "superada", informe.motivos
    assert _estados(informe) == dict.fromkeys(m.PLANOS_DEL_CONJUNTO, "superada")
    with pytest.raises(ValueError):
        m.ClaveDeObservadorDePrueba(fo.clave_publica("observador"), "x", naturaleza="operativa")
    assert m.OBSERVADORES_OPERATIVOS_ADMITIDOS == ()


def test_g1_omisiones_respecto_del_conjunto_esperado():
    m = _m()
    entradas, _, acuses = _base()
    sin_prediccion = _conjunto(m, fo.declaracion(m, ex, entradas, objetivos=(("BALOTO", 2714), ("BALOTO", 2715),
                                                                            ("BALOTO", 2716), ("BALOTO", 2717)),
                                                 corte_sintetico=2717), corte=2717)
    assert "objetivo_esperado_sin_prediccion" in sin_prediccion.motivos
    dos = acuses[:2]
    cierre_dos = fx.cierre(ex, entradas, dos, conjunto=(("BALOTO", 2714), ("BALOTO", 2715)))
    sin_acuse = _conjunto(m, fo.declaracion(m, ex, entradas), acuses=dos, cierre=cierre_dos)
    assert {"objetivo_esperado_sin_acuse", "objetivo_esperado_fuera_del_cierre"} <= set(sin_acuse.motivos)
    assert sin_acuse.estado == "rechazada"


def test_g1_objetivos_extra_y_duplicados():
    m = _m()
    entradas, _, _ = _base()
    extra = _conjunto(m, fo.declaracion(m, ex, entradas, objetivos=(("BALOTO", 2714), ("BALOTO", 2715)),
                                        corte_sintetico=2716))
    assert "objetivo_no_esperado" in extra.motivos
    pieza = m.construir_conjunto_esperado(entradas, observador=fo.OBSERVADOR, corte_sintetico=2716,
                                          objetivos=(("BALOTO", 2714), ("BALOTO", 2715), ("BALOTO", 2716)),
                                          secuencia=1, anterior=None, clave_publica=fo.clave_publica("observador"))
    pieza["objetivos_esperados"] = [["BALOTO", 2714], ["BALOTO", 2714], ["BALOTO", 2715], ["BALOTO", 2716]]
    duplicado = _conjunto(m, fo.firmar(ex, pieza, "observador"))
    assert "objetivo_esperado_duplicado" in duplicado.motivos
    registro = fx.registro()
    objetos = fx.acuses(ex, registro[0])
    dobles = [objetos[0], objetos[0], *objetos[1:]]
    doble_acuse = _conjunto(m, fo.declaracion(m, ex, entradas), acuses=dobles, cierre=fx.cierre(ex, entradas, objetos))
    assert "acuse_duplicado" in doble_acuse.motivos


def test_g1_vinculos_incorrectos():
    m = _m()
    entradas, _, _ = _base()
    for cambio, motivo in (({"protocolo_hash": "0" * 64}, "protocolo_hash_no_coincide"),
                           ({"objetivos_esperados": [["MILOTO", 2714]]}, "juego_fuera_del_protocolo"),
                           ({"objetivos_esperados": [["BALOTO", 2713], ["BALOTO", 2714]]},
                            "objetivo_esperado_no_posterior_al_corte_del_protocolo")):
        informe = _conjunto(m, fo.declaracion(m, ex, entradas, **cambio))
        assert motivo in informe.motivos, (cambio, informe.motivos)
        assert informe.estado == "rechazada"


def test_g1_firmas_alteradas_y_roles_del_observador():
    m = _m()
    entradas, _, _ = _base()
    alterada = _conjunto(m, fo.declaracion(m, ex, entradas, alterar=True))
    assert "firma_no_coincide" in alterada.planos["firma_del_observador"].motivos
    ajeno = _conjunto(m, fo.declaracion(m, ex, entradas, clave="observador_ajeno"))
    assert "clave_no_admitida" in ajeno.planos["firma_del_observador"].motivos
    politica = m.PoliticaDeObservadoresDePrueba(claves=(
        m.ClaveDeObservadorDePrueba(fx.clave_publica("canal"), "clave del canal usada como observador"),))
    canal = _conjunto(m, fo.declaracion(m, ex, entradas, clave="canal"), politica_obs=politica)
    assert "observador_no_independiente_del_canal" in canal.planos["firma_del_observador"].motivos
    assert canal.estado == "rechazada"


def test_g1_cambios_de_corte():
    m = _m()
    entradas, _, _ = _base()
    distinto = _conjunto(m, fo.declaracion(m, ex, entradas), corte=2715)
    assert "corte_distinto_del_esperado" in distinto.motivos
    posterior = _conjunto(m, fo.declaracion(m, ex, entradas, corte_sintetico=2715), corte=2715)
    assert "objetivo_posterior_al_corte_declarado" in posterior.motivos


def test_g1_vistas_encadenadas_continuidad_y_contradicciones():
    m = _m()
    entradas, _, _ = _base()
    etapas = [((("BALOTO", 2714),), 2714), ((("BALOTO", 2714), ("BALOTO", 2715)), 2715),
              ((("BALOTO", 2714), ("BALOTO", 2715), ("BALOTO", 2716)), 2716)]
    completa = fo.cadena(m, ex, entradas, etapas)
    prefijo = completa[:2]
    ok = m.verificar_vistas(entradas, [completa, prefijo], fo.politica_observadores(m), fx.politica(ex))
    assert ok.estado == "superada" and ok.motivos == ()
    assert ok.no_descarta == m.LIMITES_DE_LAS_VISTAS
    rota = m.verificar_vistas(entradas, [[completa[0], completa[2]]], fo.politica_observadores(m), fx.politica(ex))
    assert "cadena_rota" in rota.motivos
    bifurcada = fo.cadena(m, ex, entradas, [etapas[0], ((("BALOTO", 2714), ("BALOTO", 2716)), 2716)])
    fork = m.verificar_vistas(entradas, [completa, bifurcada], fo.politica_observadores(m), fx.politica(ex))
    assert "vistas_contradictorias" in fork.motivos and fork.estado == "rechazada"
    retirada = fo.cadena(m, ex, entradas, [etapas[1], ((("BALOTO", 2715),), 2716)])
    assert "objetivo_retirado" in m.verificar_vistas(entradas, [retirada], fo.politica_observadores(m),
                                                     fx.politica(ex)).motivos
    retrocede = fo.cadena(m, ex, entradas, [etapas[1], (etapas[1][0], 2714)])
    assert "corte_retrocede" in m.verificar_vistas(entradas, [retrocede], fo.politica_observadores(m),
                                                   fx.politica(ex)).motivos


# ===========================================================================
# G1: informe compuesto
# ===========================================================================

def _compuesto(m, *, sellos=None, vistas=None, declaracion=None, **cambios):
    entradas, bd, acuses = _base()
    sellos = sellos if sellos is not None else [fo.sellar_acuse(m, entradas, a) for a in acuses]
    declaracion = declaracion if declaracion is not None else fo.declaracion(m, ex, entradas)
    vistas = vistas if vistas is not None else [[declaracion]]
    argumentos = dict(evidencias_de_sello={}, politica_de_sello=fo.politica_sello(), sobre=None, acuses=acuses,
                      cierre=fx.cierre(ex, entradas, acuses), politica_de_claves=fx.politica(ex), canal=fx.CANAL)
    argumentos.update(cambios)
    return m.evaluar_recepcion_por_objetivo(entradas, bd, sellos_de_acuses=sellos, declaracion=declaracion,
                                            vistas=vistas, politica_de_observadores=fo.politica_observadores(m),
                                            corte_esperado=2716, **argumentos)


def test_g1_informe_compuesto_separa_planos_y_no_promueve():
    m = _m()
    entradas, bd, acuses = _base()
    informe = _compuesto(m)
    assert tuple(informe.planos_ae77) == m.PLANOS_COMPUESTOS
    assert informe.planos_ae77 == {
        "integridad_de_bytes_de_las_piezas": "superada", "firmas_y_roles_de_prueba": "superada", "tiempo_por_acuse": "pendiente",
        "completitud_respecto_del_manifiesto_presentado": "superada", "autoridad_del_manifiesto": "pendiente",
        "completitud_global": "pendiente"}
    assert informe.motivos["autoridad_del_manifiesto"] == ("observador_de_fixture_sin_autoridad",
                                                           "decision_c3_sin_tomar")
    assert informe.motivos["completitud_global"] == ("sin_monitores_independientes", "sin_fuente_autorizada")
    solo = ex.evaluar_expediente(entradas, bd, evidencias_de_sello={}, politica_de_sello=fo.politica_sello(),
                                 sobre=None, acuses=acuses, cierre=fx.cierre(ex, entradas, acuses),
                                 politica_de_claves=fx.politica(ex), canal=fx.CANAL)
    assert _plano(informe.expediente) == _plano(solo)
    assert informe.expediente.r0_final.estado == "rechazada"
    assert informe.expediente.planos["autenticacion_de_r0"] == "sin_evidencia"
    assert informe.expediente.planos["recepcion_antes_del_plazo"] == "sin_evidencia"
    assert informe.autoriza_evaluacion is False and pi.AUTORIZA_EVALUACION is False
    assert not set(informe.planos_ae77) & (set(informe.expediente.planos) | set(informe.expediente.planos_preparatorios))


def test_g1_fallos_aislados_en_el_compuesto():
    m = _m()
    entradas, _, acuses = _base()
    firma = _compuesto(m, declaracion=fo.declaracion(m, ex, entradas, alterar=True))
    assert firma.planos_ae77["firmas_y_roles_de_prueba"] == "rechazada"
    assert firma.planos_ae77["tiempo_por_acuse"] == "pendiente"
    evidencia = fo.sellar_acuse(m, entradas, acuses[0])
    otro = m.bytes_de_compromiso(m.construir_compromiso_de_acuse(entradas, acuses[0], plazo_utc="2026-10-11T00:00:00Z"))
    sellos = [m.EvidenciaDeSelloDeAcuse(acuses[0], evidencia.respuesta_der, otro),
              *[fo.sellar_acuse(m, entradas, a) for a in acuses[1:]]]
    impronta = _compuesto(m, sellos=sellos)
    assert impronta.planos_ae77["integridad_de_bytes_de_las_piezas"] == "rechazada"
    assert impronta.planos_ae77["tiempo_por_acuse"] == "rechazada"
    assert impronta.planos_ae77["firmas_y_roles_de_prueba"] == "superada"
    falta = _compuesto(m, sellos=[fo.sellar_acuse(m, entradas, a) for a in acuses[:2]])
    assert falta.planos_ae77["tiempo_por_acuse"] == "pendiente"
    assert "acuse_sin_sello" in falta.motivos["tiempo_por_acuse"]
    omision = _compuesto(m, declaracion=fo.declaracion(m, ex, entradas, objetivos=(("BALOTO", 2714), ("BALOTO", 2715)),
                                                       corte_sintetico=2716))
    assert omision.planos_ae77["completitud_respecto_del_manifiesto_presentado"] == "rechazada"
    for informe in (firma, impronta, falta, omision):
        assert informe.planos_ae77["autoridad_del_manifiesto"] == "pendiente"
        assert informe.planos_ae77["completitud_global"] == "pendiente"
        assert informe.expediente.r0_final.estado == "rechazada"


def test_g1_decisiones_limites_vocabulario_y_pureza():
    m = _m()
    assert set(m.DECISIONES_OPERATIVAS_PENDIENTES) == {"A1", "A2", "A3", "C1", "C2", "C3"}
    assert {d["estado"] for d in m.DECISIONES_OPERATIVAS_PENDIENTES.values()} == {"sin_decidir"}
    nombres = [*m.PLANOS_DE_TIEMPO, *m.PLANOS_DEL_CONJUNTO, *m.PLANOS_COMPUESTOS, *m.MOTIVOS]
    assert len(m.MOTIVOS) == len(set(m.MOTIVOS))
    for nombre in nombres:
        assert not re.search(r"autenticad|acreditad|fijad|aprobad|(?<!in)valid|verificad|apt[ao]", nombre), nombre
    textos = " ".join((*m.LIMITES, *m.LIMITES_DE_LAS_VISTAS,
                       *(d["texto"] for d in m.DECISIONES_OPERATIVAS_PENDIENTES.values())))
    assert "9162" not in textos and "historias ocultas" in textos
    arbol = ast.parse(Path(m.__file__).read_text(encoding="utf-8"))
    prohibidos = {"socket", "urllib", "requests", "http", "time", "subprocess", "random", "os", "pathlib",
                  "sqlalchemy", "datetime", "secrets"}
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            assert not {a.name.split(".")[0] for a in nodo.names} & prohibidos
        if isinstance(nodo, ast.ImportFrom):
            assert (nodo.module or "").split(".")[0] not in prohibidos
        if isinstance(nodo, ast.Attribute):
            assert nodo.attr not in {"now", "today", "utcnow", "generate"}, nodo.attr
        if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name):
            assert nodo.func.id != "open"
        if isinstance(nodo, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            objetivos = nodo.targets if isinstance(nodo, ast.Assign) else [nodo.target]
            assert not any(isinstance(o, ast.Attribute) for o in objetivos)


# ===========================================================================
# G2: invariantes de AE-52 y AE-74 a AE-76 (pasan sobre la base)
# ===========================================================================

def test_g2_huellas_de_ae52_y_ae74_a_ae76():
    assert _huella((rp.ESQUEMA_ENTRADA, rp.TIPOS_ENTRADA, rp.REGLAS_EVALUACION_AE52, rp.PENDIENTES_BORRADOR_AE52,
                    rp.NOTA_PROTOCOLO, rp.ALCANCE_REGISTRO)) == (
        "4f31cdeb3c4d29b1740592d4d81de2f8f51305abf4a82743c49f12985621c50b")
    assert _huella((rp.ESQUEMA_ENTRADA_PROTOCOLO_CONTRATO_R0, rp.CONTRATO_VINCULO_R0, rp.REGLA_VINCULO_R0_CONTRATO,
                    rp.MOTIVOS_VINCULO_R0_CONTRATO, cv.CONTRATO, cv.ESQUEMA_DEL_PROTOCOLO, cv.REGLA, cv.PUERTAS,
                    cv.ESTADOS_DE_PUERTA, cv.RUTAS, cv.MOTIVOS_DE_PUERTA, cv.TRANSICIONES,
                    cv.ESCENARIOS_DE_DEMOSTRACION, cv.RUTAS_COMPATIBLES, cv.REQUISITOS_FALTANTES,
                    cv.COMPATIBILIDAD, cv.LIMITES)) == (
        "752c360d7dc87de0f954e4f226510bc05b0f99a50ffe05705d3ca6a12ecbb21f")
    assert _huella(cv.DECISIONES_DEL_CONTRATO) == "56cc40d8af732aea86ca88dc3a16ee64254212a1e40ae7e51a75eafe05c554ea"
    assert _huella((st.ESQUEMA_COMPROMISO, st.CLAVES_DEL_COMPROMISO, st.PROCEDENCIAS_DEL_PLAZO,
                    st.RESULTADOS_TEMPORALES, st.NATURALEZAS_DE_ANCLA, st.ANCLAS_OPERATIVAS_APROBADAS,
                    st.ESTADOS_DE_COMPROBACION, st.COMPROBACIONES_DEL_VINCULO, st.COMPROBACIONES_CRIPTOGRAFICAS,
                    st.HERRAMIENTAS, st.ESTADOS_DEL_PLANO, st.LIMITES_OPERATIVOS, st.NO_PRUEBA, st.MOTIVOS,
                    st.FUENTES_PRIMARIAS, st.POLITICA_ELEGIDA, st.REQUISITOS_PARA_USO_OPERATIVO,
                    st.PLANO_TEMPORAL)) == "155e541d1715ff9f41dfa302d97c9634eaddc27e451f3a20560a0189ab773034"
    assert _huella((ex.ESQUEMA_SOBRE, ex.ESQUEMA_ACUSE, ex.ESQUEMA_CIERRE, ex.ALCANCE_DE_LA_FIRMA, ex.ALGORITMO_DE_FIRMA,
                    ex.CLAVES_DEL_SOBRE, ex.CLAVES_DEL_ACUSE, ex.CLAVES_DEL_CIERRE, ex.ROLES_DE_CLAVE,
                    ex.NATURALEZAS_DE_CLAVE, ex.CLAVES_OPERATIVAS_ADMITIDAS, ex.PLANOS_DE_AUTENTICACION,
                    ex.PENDIENTES_DE_AUTENTICACION, ex.NIVELES_DE_COMPLETITUD, ex.EVIDENCIA_EXTERNA_FALTANTE,
                    ex.PENDIENTES_DE_RECEPCION, ex.PLANOS_PREPARATORIOS, ex.ESTADOS_PREPARATORIOS,
                    ex.DECISIONES_PENDIENTES_AE76, ex.LIMITES)) == (
        "8bd133290bec6bc4b439902109f4d7850c2b7cb4f323ff8a5fd4c042b9cba22b")


def test_g2_bytes_y_hashes_literales():
    est = fx._estrategia()
    b = rp.serializar_entrada(rp.construir_protocolo(protocolo_id="sintetico-ae73", estrategia=est, cortes=fx.CORTES,
                                                     pendientes=[], sintetico=True))
    assert rp.hash_entrada(b) == "c9e73601ac6d9668a3e50c8e76b75a130b214a68efaf5cf115b17d5a67ea3892"
    v11 = {"regla": "ae73-vinculo-r0-campo-explicito/1", "esquema_declaracion": "declaracion-r0-sintetica/1",
           "hash_declaracion": "1" * 64, "pendientes": ["regla_de_duplicados"]}
    b11 = rp.serializar_entrada(rp.construir_protocolo_con_vinculo_r0(
        protocolo_id="sintetico-ae74", estrategia=est, cortes=fx.CORTES, pendientes=[], sintetico=True,
        vinculo_r0=v11))
    assert rp.hash_entrada(b11) == "9ded8373d753fa68473b91728d900340e996c5af46ced4d2cc94ef5f56e80d0b"
    declaracion = pv.construir_declaracion(fx._elementos())
    b12 = rp.serializar_entrada(cv.construir_protocolo_del_contrato(declaracion, protocolo_id="sintetico-ae74",
                                                                    estrategia=est, cortes=fx.CORTES))
    assert rp.hash_entrada(b12) == "68e3660d19fe49c56e619d5d1b3b9260fa1cce2d53291deee2ea900c69f76c7c"
    pred12 = rp.nueva_prediccion(rp.validar_registro([b12]), "BALOTO", 2714, sinteticos.historico(2081, 2713),
                                 fx.PROBABILIDADES)
    assert rp.hash_entrada(rp.serializar_entrada(pred12)) == (
        "cd648d5cb0013b3bf5b750351c83ecce3a2436318cdb7a75c808c5e0841b36ec")
    entradas, bd = fx.registro()
    assert rp.hash_entrada(entradas[0]) == "f59365c837c52771007f71ac0ac8bd41b576cc810edbf9596b745412272fe2f6"
    sobre = fx.firmar(ex, ex.construir_sobre(entradas, bd, clave_publica=fx.clave_publica("firmante")), "firmante")
    assert hashlib.sha256(sobre.datos).hexdigest() == "9dfde652a93b9559049ef9d32a4a13407b7ec8951f4f9d18baabe87c3ea02b9f"
    assert hashlib.sha256(sobre.firma).hexdigest() == "2d2aba68d22bb019d2df3e84e23a1d37594de098eac5645378222b0232f27846"
    acuses = fx.acuses(ex, entradas)
    assert ex.hash_de_pieza(acuses[0].datos) == "f45622a4de632fe20bb811a25c1e9d087391349fc5d2449dca852c4f16d22972"
    assert ex.hash_de_pieza(fx.cierre(ex, entradas, acuses).datos) == (
        "1dfef4149723d51623965ee77689c9a1d045c169a2010fd6910283190c40abd8")


def test_g2_estados_y_puertas_sin_cambios():
    assert pi.AUTORIZA_EVALUACION is False
    assert cv.DECISIONES_DEL_CONTRATO["D8"]["estado"] == "aprobada_solo_para_el_modelo_sintetico"
    assert cv.DECISIONES_DEL_CONTRATO["D9"]["estado"] == "espera_provisional_aprobada"
    assert {r.estado for r in ec.CONDICIONES_DEL_PROTOCOLO.values()} == {"sin_fijar"}
    assert {r.estado for r in ec.REQUISITOS_PREVIOS.values()} == {"sin_fijar"}
    assert {d["estado"] for d in ex.DECISIONES_PENDIENTES_AE76.values()} == {"sin_decidir"}
    assert "superada" not in st.ESTADOS_DEL_PLANO and ex.CLAVES_OPERATIVAS_ADMITIDAS == ()
    entradas, bd, acuses = _base()
    informe = ex.evaluar_expediente(entradas, bd, evidencias_de_sello={}, politica_de_sello=fo.politica_sello(),
                                    sobre=None, acuses=acuses, cierre=fx.cierre(ex, entradas, acuses),
                                    politica_de_claves=fx.politica(ex), canal=fx.CANAL)
    assert informe.r0_final.estado == "rechazada" and informe.autoriza_evaluacion is False
    assert informe.planos_preparatorios["completitud_respecto_de_lo_que_debio_existir"] == "pendiente"
    assert informe.planos_preparatorios["recepcion_preparatoria_antes_del_plazo"] == "pendiente"


# ===========================================================================
# G3: premisas sobre el codigo existente
# ===========================================================================

def test_g3_verificar_sello_de_ae75_rechaza_bytes_que_no_son_su_compromiso():
    entradas, bd, acuses = _base()
    datos = acuses[0].datos
    respuesta = fs.respuesta(datos, fs.Opciones(gen_time=fs.instante(fo.GEN)))
    informe = st.verificar_sello(entradas, bd, st.EvidenciaDeSello(respuesta, datos), fo.politica_sello(),
                                 codigo_juego="BALOTO", sorteo_objetivo=2714)
    assert informe.vinculo_del_compromiso["compromiso_legible"].motivos == ("version_de_compromiso_desconocida",)
    assert informe.comprobaciones_criptograficas["firma_del_token"].estado == "superada"
    assert informe.estado_del_plano == "rechazada"


def test_g3_ae76_no_admite_un_rol_de_observador_y_la_hora_no_cambia_el_canal():
    with pytest.raises(ValueError):
        ex.ClaveDePrueba(fo.clave_publica("observador"), "observador", "x")
    entradas, _, acuses = _base()
    informe = ex.verificar_canal(entradas, acuses, fx.cierre(ex, entradas, acuses), fx.politica(ex), canal=fx.CANAL)
    assert informe.recepcion_antes_del_plazo.estado == "pendiente"
    assert informe.completitud["respecto_de_lo_que_debio_existir"].estado == "pendiente"


def test_g3_el_acuse_de_ae76_encadena_por_hash_y_liga_prediccion_y_objetivo():
    entradas, _, acuses = _base()
    estado = rp.validar_registro(list(entradas))
    segundo = ex.leer_acuse(acuses[1].datos)
    assert segundo["acuse_anterior"] == ex.hash_de_pieza(acuses[0].datos)
    assert segundo["prediccion_hash"] == estado.predicciones[("BALOTO", 2715)]
    assert "hora_declarada_utc" in segundo

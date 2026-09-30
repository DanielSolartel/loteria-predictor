"""Tests de la Etapa AE-76, validada localmente como trabajo preparatorio:
expediente preparatorio de
autenticacion de R0 y recepcion de predicciones.

G1  modulo nuevo `expediente_r0_recepcion`, importado dentro de cada prueba
    (sobre la base falla con `ModuleNotFoundError`):
    - sobre firmado: firma correcta, clave no admitida, firma alterada,
      R0 o protocolo equivocado;
    - acuses y cierre: acuse reutilizado en otro objetivo, duplicado,
      omision, reordenamiento, cierre manipulado y manifiesto que declara
      falsamente un conjunto completo;
    - informe conjunto sin promocion de estados.
G2  invariantes de AE-52 a AE-75: huellas, bytes y hashes de 1.0, 1.1 y
    1.2, puertas y planos de AE-74 y AE-75.
G3  premisas sobre codigo existente.

Todo sintetico: claves de fixture, registro fabricado, horas fijadas por la
prueba. Ninguna combinacion eleva `r0_final` ni `AUTORIZA_EVALUACION`."""
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
from app.application.ml import propuesta_inferencia_prospectiva as pi
from app.application.ml import prototipo_vinculo_declaracion_r0 as pv
from app.application.ml import registro_prospectivo as rp
from app.application.ml import sello_temporal_r0 as st
from app.application.ml import verificacion_primaria_rfc_sellado_y_transparencia as vr
from tests.unit.ml import fixtures_expediente_r0 as fx
from tests.unit.ml import fixtures_sello_temporal as fs
from tests.unit.simulaciones import sinteticos

def _m():
    return importlib.import_module("app.application.ml.expediente_r0_recepcion")


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


def _sobre(m, *, clave="firmante", registro=None, alterar=False, **cambios):
    entradas, bd = registro or fx.registro()
    pieza = m.construir_sobre(entradas, bd, clave_publica=fx.clave_publica(clave))
    pieza.update(cambios)
    return fx.firmar(m, pieza, clave, alterar=alterar)


def _estados(informe):
    return {k: v.estado for k, v in informe.planos.items()}


# ===========================================================================
# G1: autenticacion preparatoria de R0
# ===========================================================================

def test_g1_sobre_canonico_y_versionado():
    m = _m()
    entradas, bd = fx.registro()
    pieza = m.construir_sobre(entradas, bd, clave_publica=fx.clave_publica("firmante"))
    assert tuple(sorted(pieza)) == tuple(sorted(m.CLAVES_DEL_SOBRE))
    assert (pieza["esquema"], pieza["alcance"], pieza["algoritmo"]) == (
        "sobre-autenticacion-r0/1", "declaracion_r0_y_protocolo_1_2_del_contrato", "ed25519")
    assert (pieza["contrato"], pieza["regla"], pieza["esquema_del_protocolo"]) == (
        "contrato-vinculo-r0/1", "ae74-vinculo-r0-contrato/1", "registro-prospectivo-ml/1.2")
    assert pieza["protocolo_hash"] == rp.hash_entrada(entradas[0])
    assert pieza["hash_declaracion"] == rp.hash_entrada(bd)
    assert pieza["huella_de_clave"] == hashlib.sha256(fx.clave_publica("firmante")).hexdigest()
    datos = m.bytes_canonicos(pieza)
    assert m.leer_sobre(datos) == pieza
    for cambio, motivo in (({"esquema": "sobre-autenticacion-r0/2"}, "version_desconocida"),
                           ({"extra": 1}, "pieza_ilegible")):
        with pytest.raises(m.ExpedienteInvalido) as error:
            m.leer_sobre(rp.serializar_entrada({**pieza, **cambio}))
        assert error.value.motivo == motivo
    with pytest.raises(m.ExpedienteInvalido) as error:
        m.leer_sobre(json.dumps(pieza, indent=1).encode("utf-8"))
    assert error.value.motivo == "pieza_no_canonica"


def test_g1_firma_correcta_con_clave_admitida_queda_pendiente_de_identidad():
    m = _m()
    entradas, bd = fx.registro()
    informe = m.verificar_autenticacion(entradas, bd, _sobre(m), fx.politica(m))
    assert tuple(informe.planos) == m.PLANOS_DE_AUTENTICACION
    assert _estados(informe) == {
        "integridad_de_la_firma": "superada", "clave_admitida_de_prueba": "superada", "huella_declarada": "superada",
        "vinculo_con_el_registro": "superada", "identidad_del_firmante": "pendiente",
        "publicacion_fuera_de_banda": "pendiente", "reconocimiento_del_operador": "pendiente"}
    assert informe.estado == "pendiente"
    assert informe.motivos == ("sin_autoridad_de_firma_operativa", "sin_evidencia_de_publicacion_fuera_de_banda",
                               "sin_reconocimiento_del_operador")


def test_g1_clave_no_admitida_firma_bien_pero_se_rechaza():
    m = _m()
    entradas, bd = fx.registro()
    informe = m.verificar_autenticacion(entradas, bd, _sobre(m, clave="ajena"), fx.politica(m))
    assert informe.planos["integridad_de_la_firma"].estado == "superada"
    assert informe.planos["clave_admitida_de_prueba"].motivos == ("clave_no_admitida",)
    assert informe.estado == "rechazada" and informe.motivos == ("clave_no_admitida",)
    canal = m.verificar_autenticacion(entradas, bd, _sobre(m, clave="canal"), fx.politica(m))
    assert canal.planos["clave_admitida_de_prueba"].motivos == ("clave_no_admitida",)


def test_g1_firma_alterada_y_clave_sustituida():
    m = _m()
    entradas, bd = fx.registro()
    alterado = m.verificar_autenticacion(entradas, bd, _sobre(m, alterar=True), fx.politica(m))
    assert alterado.planos["integridad_de_la_firma"].motivos == ("firma_no_coincide",)
    assert alterado.estado == "rechazada"
    bueno = _sobre(m)
    otra_clave = m.ObjetoFirmado(bueno.datos, bueno.firma, fx.clave_publica("canal"))
    sustituida = m.verificar_autenticacion(entradas, bd, otra_clave, fx.politica(m))
    assert {"firma_no_coincide", "clave_no_admitida", "huella_de_clave_no_coincide"} <= set(sustituida.motivos)
    mal = m.verificar_autenticacion(entradas, bd, m.ObjetoFirmado(bueno.datos, bueno.firma, b"\x00" * 31),
                                    fx.politica(m))
    assert "clave_mal_formada" in mal.motivos


def test_g1_r0_o_protocolo_equivocado():
    m = _m()
    entradas, bd = fx.registro()
    casos = (({"hash_declaracion": "0" * 64}, "hash_de_declaracion_no_coincide"),
             ({"protocolo_hash": "0" * 64}, "protocolo_hash_no_coincide"),
             ({"regla": "ae73-vinculo-r0-campo-explicito/1"}, "contrato_o_regla_no_coincide"),
             ({"alcance": "solo_la_declaracion"}, "alcance_no_admitido"))
    for cambio, motivo in casos:
        informe = m.verificar_autenticacion(entradas, bd, _sobre(m, **cambio), fx.politica(m))
        assert informe.planos["integridad_de_la_firma"].estado == "superada"
        assert motivo in informe.planos["vinculo_con_el_registro"].motivos, cambio
        assert informe.estado == "rechazada"
    otro = fx.registro(valor="otra-declaracion")
    ajeno = m.verificar_autenticacion(otro[0], otro[1], _sobre(m), fx.politica(m))
    assert {"protocolo_hash_no_coincide", "hash_de_declaracion_no_coincide"} <= set(ajeno.motivos)
    sin = m.verificar_autenticacion(entradas, bd, None, fx.politica(m))
    assert sin.estado == "sin_evidencia"


def test_g1_dependencia_criptografica_ausente_deja_pendiente(monkeypatch):
    m = _m()

    def ausente():
        raise ImportError("cryptography no instalado")

    monkeypatch.setattr(m, "_ed25519", ausente)
    entradas, bd = fx.registro()
    informe = m.verificar_autenticacion(entradas, bd, _sobre(m), fx.politica(m))
    assert informe.planos["integridad_de_la_firma"].motivos == ("dependencia_criptografica_ausente",)
    assert informe.estado == "pendiente"
    assert informe.motivos[0] == "dependencia_criptografica_ausente"


def test_g1_politica_solo_de_claves_de_prueba():
    m = _m()
    assert m.NATURALEZAS_DE_CLAVE == ("fixture_de_prueba",) and m.CLAVES_OPERATIVAS_ADMITIDAS == ()
    with pytest.raises(ValueError):
        m.ClaveDePrueba(fx.clave_publica("firmante"), "firmante_r0", "x", naturaleza="operativa")
    with pytest.raises(ValueError):
        m.ClaveDePrueba(fx.clave_publica("firmante"), "autoridad", "x")
    with pytest.raises(ValueError):
        m.ClaveDePrueba(b"\x01" * 16, "canal", "x")
    assert set(m.DECISIONES_PENDIENTES_AE76) == {"A1", "A2", "A3", "C1", "C2", "C3"}
    assert {d["estado"] for d in m.DECISIONES_PENDIENTES_AE76.values()} == {"sin_decidir"}


# ===========================================================================
# G1: acuses y cierre del canal
# ===========================================================================

def _canal(m, objetos=None, cierre=None, registro=None, **kw):
    entradas, _ = registro or fx.registro()
    objetos = objetos if objetos is not None else fx.acuses(m, entradas)
    cierre = cierre if cierre is not None else fx.cierre(m, entradas, objetos)
    return m.verificar_canal(entradas, objetos, cierre, fx.politica(m), canal=fx.CANAL, **kw)


def test_g1_canal_correcto_distingue_los_tres_niveles_de_completitud():
    m = _m()
    informe = _canal(m)
    assert {k: v.estado for k, v in informe.completitud.items()} == {
        "respecto_del_manifiesto": "superada", "respecto_del_registro_presentado": "superada",
        "respecto_de_lo_que_debio_existir": "pendiente"}
    assert informe.completitud["respecto_de_lo_que_debio_existir"].motivos == (
        "sin_evidencia_externa_del_conjunto_esperado",)
    assert informe.recepcion_antes_del_plazo.estado == "pendiente"
    assert set(informe.recepcion_antes_del_plazo.motivos) == {
        "hora_declarada_por_el_canal_no_prueba_anterioridad", "sello_ae75_cubre_el_compromiso_r0_no_cada_prediccion",
        "sin_sello_independiente_de_cada_acuse"}
    assert informe.estado == "pendiente"
    assert informe.evidencia_externa_faltante == m.EVIDENCIA_EXTERNA_FALTANTE
    assert len(informe.acuses) == 3
    assert all(r.estado == "superada" for planos in informe.acuses for r in planos.values())


def test_g1_acuse_canonico_ligado_a_prediccion_protocolo_y_objetivo():
    m = _m()
    entradas, _ = fx.registro()
    estado = rp.validar_registro(list(entradas))
    pieza = m.leer_acuse(fx.acuses(m, entradas)[1].datos)
    assert tuple(sorted(pieza)) == tuple(sorted(m.CLAVES_DEL_ACUSE))
    assert (pieza["esquema"], pieza["canal"], pieza["secuencia"]) == ("acuse-recepcion-prediccion/1", fx.CANAL, 2)
    assert pieza["prediccion_hash"] == estado.predicciones[("BALOTO", 2715)]
    assert pieza["protocolo_hash"] == estado.hash_protocolo
    assert pieza["acuse_anterior"] == m.hash_de_pieza(fx.acuses(m, entradas)[0].datos)
    with pytest.raises(m.ExpedienteInvalido) as error:
        m.construir_acuse(entradas, canal=fx.CANAL, codigo_juego="BALOTO", sorteo_objetivo=2799, secuencia=1,
                          acuse_anterior=None, hora_declarada_utc="2026-10-01T12:00:00Z",
                          clave_publica=fx.clave_publica("canal"))
    assert error.value.motivo == "prediccion_desconocida"
    with pytest.raises(m.ExpedienteInvalido):
        m.construir_acuse(entradas, canal=fx.CANAL, codigo_juego="BALOTO", sorteo_objetivo=2714, secuencia=2,
                          acuse_anterior=None, hora_declarada_utc="2026-10-01T12:00:00Z",
                          clave_publica=fx.clave_publica("canal"))


def test_g1_acuse_reutilizado_en_otro_objetivo():
    m = _m()
    entradas, _ = fx.registro()
    objetos = fx.acuses(m, entradas)
    pieza = m.leer_acuse(objetos[0].datos)
    pieza["sorteo_objetivo"] = 2715
    reutilizado = fx.firmar(m, pieza, "canal")
    informe = _canal(m, [reutilizado, *objetos[1:]], fx.cierre(m, entradas, [reutilizado, *objetos[1:]]))
    assert "acuse_de_otro_objetivo" in informe.acuses[0]["vinculo_con_el_registro"].motivos
    assert informe.estado == "rechazada"
    assert informe.completitud["respecto_del_manifiesto"].estado == "rechazada"


def test_g1_acuse_duplicado():
    m = _m()
    entradas, _ = fx.registro()
    objetos = fx.acuses(m, entradas)
    dobles = [objetos[0], objetos[0], *objetos[1:]]
    informe = _canal(m, dobles, fx.cierre(m, entradas, objetos))
    assert "acuse_duplicado" in informe.motivos
    assert informe.estado == "rechazada"


def test_g1_omision_de_un_acuse_y_hueco_de_secuencia():
    m = _m()
    entradas, _ = fx.registro()
    objetos = fx.acuses(m, entradas)
    sin_segundo = [objetos[0], objetos[2]]
    informe = _canal(m, sin_segundo, fx.cierre(m, entradas, objetos))
    assert {"acuse_omitido", "secuencia_con_huecos", "omision_respecto_del_conjunto_declarado"} <= set(informe.motivos)
    assert informe.completitud["respecto_del_manifiesto"].estado == "rechazada"
    assert informe.completitud["respecto_del_registro_presentado"].motivos == ("prediccion_del_registro_sin_acuse",)


def test_g1_reordenamiento():
    m = _m()
    entradas, _ = fx.registro()
    objetos = fx.acuses(m, entradas)
    presentados = [objetos[1], objetos[0], objetos[2]]
    informe = _canal(m, presentados, fx.cierre(m, entradas, objetos))
    assert "orden_alterado" in informe.motivos
    en_cierre = _canal(m, objetos, fx.cierre(m, entradas, [objetos[1], objetos[0], objetos[2]]))
    assert "orden_alterado" in en_cierre.motivos
    pieza = m.leer_acuse(objetos[2].datos)
    pieza["acuse_anterior"] = m.hash_de_pieza(objetos[0].datos)
    roto = [objetos[0], objetos[1], fx.firmar(m, pieza, "canal")]
    assert "encadenamiento_roto" in _canal(m, roto, fx.cierre(m, entradas, roto)).motivos


def test_g1_cierre_manipulado():
    m = _m()
    entradas, _ = fx.registro()
    objetos = fx.acuses(m, entradas)
    alterado = fx.cierre(m, entradas, objetos)
    alterado = m.ObjetoFirmado(alterado.datos.replace(b'"total":3', b'"total":2'), alterado.firma,
                               alterado.clave_publica)
    informe = _canal(m, objetos, alterado)
    assert informe.cierre["integridad_de_la_firma"].motivos == ("firma_no_coincide",)
    assert informe.estado == "rechazada"
    refirmado = fx.cierre(m, entradas, objetos, total=2)
    assert "total_o_cabeza_no_coincide" in _canal(m, objetos, refirmado).motivos
    ajeno = fx.cierre(m, entradas, objetos, clave="ajena")
    assert "clave_no_admitida" in _canal(m, objetos, ajeno).motivos
    desde_firmante = fx.cierre(m, entradas, objetos, clave="firmante")
    assert "clave_no_admitida" in _canal(m, objetos, desde_firmante).motivos


def test_g1_manifiesto_que_declara_falsamente_un_conjunto_completo():
    """El canal omite 2716 del conjunto declarado y de los acuses, y aun
    asi declara completo: es completo respecto de su manifiesto, pero no
    respecto del registro presentado."""
    m = _m()
    entradas, _ = fx.registro()
    objetos = fx.acuses(m, entradas, (2714, 2715))
    cierre = fx.cierre(m, entradas, objetos, conjunto=(("BALOTO", 2714), ("BALOTO", 2715)))
    informe = _canal(m, objetos, cierre)
    assert "declaracion_de_completitud_falsa_frente_al_registro" in informe.cierre["contenido"].motivos
    assert informe.completitud["respecto_del_registro_presentado"].estado == "rechazada"
    assert informe.estado == "rechazada"
    coherente = fx.registro(objetivos=(2714, 2715))
    obj2 = fx.acuses(m, coherente[0], (2714, 2715))
    propio = _canal(m, obj2, fx.cierre(m, coherente[0], obj2, conjunto=(("BALOTO", 2714), ("BALOTO", 2715))),
                    registro=coherente)
    assert propio.completitud["respecto_del_manifiesto"].estado == "superada"
    assert propio.completitud["respecto_del_registro_presentado"].estado == "superada"
    assert propio.completitud["respecto_de_lo_que_debio_existir"].estado == "pendiente"


def test_g1_cierre_ausente_o_sin_declarar_completitud_queda_pendiente():
    m = _m()
    entradas, _ = fx.registro()
    objetos = fx.acuses(m, entradas)
    sin = m.verificar_canal(entradas, objetos, None, fx.politica(m), canal=fx.CANAL)
    assert sin.completitud["respecto_del_manifiesto"].motivos == ("sin_cierre",)
    assert sin.estado == "pendiente"
    no_declara = _canal(m, objetos, fx.cierre(m, entradas, objetos, declara_completo=False))
    assert no_declara.completitud["respecto_del_manifiesto"].motivos == ("cierre_no_declara_completitud",)


def test_g1_hora_y_secuencia_del_canal_no_prueban_recepcion():
    """Horas declaradas imposibles (posteriores a cualquier plazo) no
    cambian nada: la hora del canal no es evidencia."""
    m = _m()
    entradas, _ = fx.registro()
    objetos, anterior = [], None
    for i, objetivo in enumerate((2714, 2715, 2716), start=1):
        pieza = m.construir_acuse(entradas, canal=fx.CANAL, codigo_juego="BALOTO", sorteo_objetivo=objetivo,
                                  secuencia=i, acuse_anterior=anterior, hora_declarada_utc="2099-12-31T23:59:59Z",
                                  clave_publica=fx.clave_publica("canal"))
        objetos.append(fx.firmar(m, pieza, "canal"))
        anterior = m.hash_de_pieza(objetos[-1].datos)
    informe = _canal(m, objetos, fx.cierre(m, entradas, objetos))
    assert informe.recepcion_antes_del_plazo == _canal(m).recepcion_antes_del_plazo
    assert informe.recepcion_antes_del_plazo.estado == "pendiente"


# ===========================================================================
# G1: informe conjunto
# ===========================================================================

def _evidencia_sello(entradas, bd):
    compromiso = st.construir_compromiso(entradas, bd, codigo_juego="BALOTO", sorteo_objetivo=2714,
                                         plazo_utc="2026-10-10T00:00:00Z")
    datos = st.bytes_de_compromiso(compromiso)
    respuesta = fs.respuesta(datos, fs.Opciones(gen_time=fs.instante("2026-10-01T12:00:00Z")))
    return {("BALOTO", 2714): st.EvidenciaDeSello(respuesta, datos)}


def _politica_sello():
    return st.PoliticaDeConfianzaTemporal(anclas=(st.AnclaDePrueba(fs.der(fs.mundo().ca), "CA fixture"),),
                                          politicas_admitidas=(fs.POLITICA_DE_PRUEBA,), margen="0")


def test_g1_informe_conjunto_no_promueve_estados():
    m = _m()
    entradas, bd = fx.registro()
    objetos = fx.acuses(m, entradas)
    informe = m.evaluar_expediente(entradas, bd, evidencias_de_sello=_evidencia_sello(entradas, bd),
                                   politica_de_sello=_politica_sello(), sobre=_sobre(m), acuses=objetos,
                                   cierre=fx.cierre(m, entradas, objetos), politica_de_claves=fx.politica(m),
                                   canal=fx.CANAL)
    base = cv.evaluar_admision(entradas, bd)
    con_sello = st.evaluar_admision_con_plano_temporal(entradas, bd, _evidencia_sello(entradas, bd), _politica_sello())
    assert _plano(informe.admision.admision) == _plano(base)
    assert informe.planos == con_sello.planos
    for plano in ("autenticacion_de_r0", "recepcion_antes_del_plazo", "completitud_y_unicidad_del_canal"):
        assert informe.planos[plano] == "sin_evidencia"
    assert informe.planos["sello_temporal_de_r0"] == "pendiente"
    assert informe.r0_final.estado == "rechazada" and informe.r0_final == base.puertas["r0_final"]
    assert informe.autoriza_evaluacion is False and pi.AUTORIZA_EVALUACION is False
    assert informe.planos_preparatorios == {
        "autenticacion_preparatoria_de_r0": "pendiente", "cierre_del_canal": "pendiente",
        "completitud_respecto_del_manifiesto": "superada", "completitud_respecto_del_registro_presentado": "superada",
        "completitud_respecto_de_lo_que_debio_existir": "pendiente",
        "recepcion_preparatoria_antes_del_plazo": "pendiente"}
    assert not set(informe.planos_preparatorios) & set(informe.planos)


def test_g1_informe_conjunto_sin_piezas_y_ruta_no_admitida():
    m = _m()
    entradas, bd = fx.registro()
    vacio = m.evaluar_expediente(entradas, bd, evidencias_de_sello={}, politica_de_sello=_politica_sello(), sobre=None,
                                 acuses=(), cierre=None, politica_de_claves=fx.politica(m), canal=fx.CANAL)
    assert set(vacio.planos_preparatorios.values()) == {"sin_evidencia"}
    assert vacio.r0_final.estado == "rechazada"
    p10 = rp.construir_protocolo(protocolo_id="sintetico-ae76", estrategia=fx._estrategia(), cortes=fx.CORTES,
                                 pendientes=[], sintetico=True)
    ruta = m.evaluar_expediente([rp.serializar_entrada(p10)], bd, evidencias_de_sello={},
                                politica_de_sello=_politica_sello(), sobre=_sobre(m), acuses=(), cierre=None,
                                politica_de_claves=fx.politica(m), canal=fx.CANAL)
    assert ruta.planos_preparatorios["autenticacion_preparatoria_de_r0"] == "rechazada"
    assert ruta.canal is None and ruta.r0_final.estado == "rechazada"


def test_g1_vocabulario_limites_y_pureza():
    m = _m()
    nombres = [*m.PLANOS_DE_AUTENTICACION, *m.PENDIENTES_DE_AUTENTICACION.values(), *m.PLANOS_PREPARATORIOS,
               *m.NIVELES_DE_COMPLETITUD, *m.PENDIENTES_DE_RECEPCION, *m.ESTADOS_PREPARATORIOS, *m.ROLES_DE_CLAVE]
    for nombre in nombres:
        assert not re.search(r"autenticad|acreditad|fijad|aprobad|(?<!in)valid|verificad|apt[ao]", nombre), nombre
    texto = " ".join((*m.LIMITES, *m.EVIDENCIA_EXTERNA_FALTANTE, *(d["texto"] for d in
                                                                   m.DECISIONES_PENDIENTES_AE76.values())))
    assert "9162" not in texto and "r0_final sigue rechazada" in texto
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


def test_g1_piezas_deterministas():
    """Ed25519 es determinista y las claves de fixture derivan de etiquetas:
    los bytes y la firma del sobre son reproducibles."""
    m = _m()
    uno, dos = _sobre(m), _sobre(m)
    assert uno == dos
    assert len(uno.firma) == 64 and len(uno.clave_publica) == 32


# ===========================================================================
# G2: invariantes de AE-52 a AE-75 (pasan sobre la base)
# ===========================================================================

def test_g2_huellas_de_ae52_a_ae75():
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
    assert _huella((rp.ESQUEMA_ENTRADA, rp.TIPOS_ENTRADA, rp.REGLAS_EVALUACION_AE52, rp.PENDIENTES_BORRADOR_AE52,
                    rp.NOTA_PROTOCOLO, rp.ALCANCE_REGISTRO)) == (
        "4f31cdeb3c4d29b1740592d4d81de2f8f51305abf4a82743c49f12985621c50b")


def test_g2_bytes_y_hashes_de_1_0_1_1_y_1_2_intactos():
    est = fx._estrategia()
    b = rp.serializar_entrada(rp.construir_protocolo(protocolo_id="sintetico-ae73", estrategia=est, cortes=fx.CORTES,
                                                     pendientes=[], sintetico=True))
    assert rp.hash_entrada(b) == "c9e73601ac6d9668a3e50c8e76b75a130b214a68efaf5cf115b17d5a67ea3892"
    pred = rp.nueva_prediccion(rp.validar_registro([b]), "BALOTO", 2714, sinteticos.historico(2081, 2713),
                               fx.PROBABILIDADES)
    assert rp.hash_entrada(rp.serializar_entrada(pred)) == (
        "435918926917ea8ab712c7162eff5544998d340f3df711b1508815ce6429f2c6")
    v11 = {"regla": "ae73-vinculo-r0-campo-explicito/1", "esquema_declaracion": "declaracion-r0-sintetica/1",
           "hash_declaracion": "1" * 64, "pendientes": ["regla_de_duplicados"]}
    b11 = rp.serializar_entrada(rp.construir_protocolo_con_vinculo_r0(
        protocolo_id="sintetico-ae74", estrategia=est, cortes=fx.CORTES, pendientes=[], sintetico=True,
        vinculo_r0=v11))
    assert rp.hash_entrada(b11) == "9ded8373d753fa68473b91728d900340e996c5af46ced4d2cc94ef5f56e80d0b"
    declaracion = pv.construir_declaracion(fx._elementos())
    assert rp.hash_entrada(pv.bytes_de_declaracion(declaracion)) == (
        "5c75c5051d6343dc6463e70946d77b21db9da49b0033197ced558832933fced4")
    b12 = rp.serializar_entrada(cv.construir_protocolo_del_contrato(declaracion, protocolo_id="sintetico-ae74",
                                                                    estrategia=est, cortes=fx.CORTES))
    assert rp.hash_entrada(b12) == "68e3660d19fe49c56e619d5d1b3b9260fa1cce2d53291deee2ea900c69f76c7c"
    pred12 = rp.nueva_prediccion(rp.validar_registro([b12]), "BALOTO", 2714, sinteticos.historico(2081, 2713),
                                 fx.PROBABILIDADES)
    assert rp.hash_entrada(rp.serializar_entrada(pred12)) == (
        "cd648d5cb0013b3bf5b750351c83ecce3a2436318cdb7a75c808c5e0841b36ec")


def test_g2_estados_y_puertas_sin_cambios():
    assert pi.AUTORIZA_EVALUACION is False
    assert cv.DECISIONES_DEL_CONTRATO["D8"]["estado"] == "aprobada_solo_para_el_modelo_sintetico"
    assert cv.DECISIONES_DEL_CONTRATO["D9"]["estado"] == "espera_provisional_aprobada"
    assert {r.estado for r in ec.CONDICIONES_DEL_PROTOCOLO.values()} == {"sin_fijar"}
    assert {r.estado for r in ec.REQUISITOS_PREVIOS.values()} == {"sin_fijar"}
    assert {v["estado"] for v in ec.AUTENTICACION_DE_R0.values()} == {"pendiente"}
    assert set(vr.CONDICIONES_DEL_REPOSITORIO.values()) == {"sin_fijar"}
    assert "superada" not in st.ESTADOS_DEL_PLANO and st.ANCLAS_OPERATIVAS_APROBADAS == ()
    entradas, bd = fx.registro()
    informe = cv.evaluar_admision(entradas, bd)
    assert informe.puertas["r0_final"].estado == "rechazada"
    assert informe.planos["autenticacion_de_r0"] == "sin_evidencia"


# ===========================================================================
# G3: premisas
# ===========================================================================

def test_g3_el_registro_asocia_cada_objetivo_a_una_prediccion_del_protocolo():
    entradas, _ = fx.registro()
    estado = rp.validar_registro(list(entradas))
    assert set(estado.predicciones) == {("BALOTO", 2714), ("BALOTO", 2715), ("BALOTO", 2716)}
    for b in entradas[1:]:
        assert json.loads(b)["protocolo_hash"] == estado.hash_protocolo


def test_g3_el_sello_de_ae75_cubre_el_compromiso_por_objetivo_no_la_prediccion():
    entradas, bd = fx.registro()
    compromiso = st.construir_compromiso(entradas, bd, codigo_juego="BALOTO", sorteo_objetivo=2714,
                                         plazo_utc="2026-10-10T00:00:00Z")
    assert set(compromiso) == set(st.CLAVES_DEL_COMPROMISO)
    assert "prediccion_hash" not in compromiso
    estado = rp.validar_registro(list(entradas))
    assert estado.predicciones[("BALOTO", 2714)] not in st.bytes_de_compromiso(compromiso).decode("utf-8")


def test_g3_ed25519_de_cryptography_detecta_un_byte_alterado():
    from cryptography.exceptions import InvalidSignature
    clave = fx.clave_privada("firmante")
    firma = clave.sign(b"datos")
    clave.public_key().verify(firma, b"datos")
    with pytest.raises(InvalidSignature):
        clave.public_key().verify(firma, b"dat0s")

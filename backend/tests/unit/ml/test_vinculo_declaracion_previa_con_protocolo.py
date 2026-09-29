"""Tests de la Etapa AE-70, validada: criterios verificables de
vinculacion entre el contenido de R0 (declaracion sintetica de AE-69) y el
protocolo de AE-52.

Tres grupos:

G1  dependen del modulo nuevo, que se importa dentro de cada prueba; sobre
    la base cada una falla por separado con `ModuleNotFoundError`.
G2  invariantes sobre codigo existente (huellas de AE-52 y AE-63 a AE-69,
    estados y bloqueos); pasan sobre la base.
G3  integraciones contra la API publica real de AE-52 y AE-69 (B1 a B6);
    pasan sobre la base porque comprueban codigo que ya existe.

Supuestos del modelo: S1 (SHA-256 tratado como resistente a colisiones, no
verificado), S2 (bytes canonicos del protocolo disponibles), S3 (regla de
vinculo declarada; aqui es un parametro de prueba) y S4 (manifiesto unico,
requisito pendiente). Ninguna topologia, representacion ni campo queda
elegido; los vinculos no aportan autenticacion, anterioridad ni suficiencia.
Todo sintetico: sin red, relojes o servicios reales, datos reales, PostgreSQL
ni predicciones reales."""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import importlib
import inspect
import json
import re
from collections.abc import Mapping
from pathlib import Path

import pytest

from app.application.ml import auditoria_obligaciones_de_aplicacion as ao
from app.application.ml import diseno_regla_prospectiva as dr
from app.application.ml import especificacion_condiciones_del_protocolo as ec
from app.application.ml import inventario_declaracion_previa_del_protocolo as iv
from app.application.ml import propuesta_evidencia_temporal_externa as pe
from app.application.ml import propuesta_inferencia_prospectiva as pi
from app.application.ml import registro_prospectivo as rp
from app.application.ml import traslado_condiciones_inferenciales as tc
from app.application.ml import verificacion_primaria_choe_ramdas as vp
from app.application.ml import verificacion_primaria_rfc_sellado_y_transparencia as vr
from app.application.ml.especificacion_evaluacion_prospectiva import ESPECIFICACION_CANDIDATA_AE53
from tests.unit.simulaciones import sinteticos

BASE = "@b278d88"
PROBABILIDADES = [0.1] * 43
"""Salida fabricada: solo prueba el formato, nunca es una prediccion."""
CAMPO = ("estrategia", "parametros", "clave_de_prueba")
"""Ruta de prueba para el campo no previsto: no es una eleccion."""
TOPOLOGIAS = ("directo_en_nuevo_esquema", "directo_en_campo_existente_no_previsto", "inverso_desde_la_declaracion",
              "manifiesto_externo")
CRITERIOS = ("K1", "K2", "K3", "K4", "K5", "K6", "K7")


def _modulo():
    return importlib.import_module("app.application.ml.vinculo_declaracion_previa_con_protocolo")


def _estrategia(parametros=None):
    return {
        "nombre": "estrategia_sintetica", "descripcion": "estrategia sintetica solo para pruebas",
        "huella_codigo": "a" * 64, "archivos_codigo": ["sintetico.py"],
        "parametros": parametros if parametros is not None else {"semilla": 1},
        "entorno": {"python": "3.x", "scikit_learn": "0.0"},
    }


def _protocolo(valor_de_prueba=None):
    parametros = {"semilla": 1}
    if valor_de_prueba is not None:
        parametros["clave_de_prueba"] = valor_de_prueba
    return rp.construir_protocolo(protocolo_id="sintetico-ae70", estrategia=_estrategia(parametros),
                                  cortes={"BALOTO": 2713, "BALOTO_REVANCHA": 2713}, pendientes=[], sintetico=True)


def _registro_con_prediccion(protocolo):
    """Reconstruye el registro: bytes del protocolo, estado y una prediccion
    sintetica creada con la API de AE-52."""
    bytes_protocolo = rp.serializar_entrada(protocolo)
    estado = rp.validar_registro([bytes_protocolo])
    prediccion = rp.nueva_prediccion(estado, "BALOTO", 2714, sinteticos.historico(2081, 2713), PROBABILIDADES)
    return bytes_protocolo, estado, prediccion


def _declaracion(valor="valor-de-prueba", pendiente=None):
    """Declaracion sintetica de AE-69; los valores son datos de prueba."""
    d = {e: {"estado": "declarado_sintetico", "valor": {"sintetico": f"{valor}-{i}"}}
         for i, e in enumerate(iv.ELEMENTOS_DE_R0)}
    if pendiente:
        d[pendiente] = {"estado": "pendiente"}
    return d


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


def _segundo_protocolo(bytes_primero, protocolo):
    """Protocolo distinto encadenado como segunda entrada, para aislar la
    regla de AE-52 que rechaza un segundo protocolo."""
    segundo = {**protocolo, "secuencia": 2, "hash_anterior": rp.hash_entrada(bytes_primero)}
    return rp.serializar_entrada(segundo)


# ===========================================================================
# G1: dependen del modulo nuevo (fallan sobre la base con ModuleNotFoundError)
# ===========================================================================

def test_g1_registros_supuestos_y_matriz_completa():
    m = _modulo()
    assert tuple(m.TOPOLOGIAS_DE_VINCULO) == TOPOLOGIAS
    assert tuple(m.CRITERIOS_DE_VINCULO) == CRITERIOS
    assert tuple(m.SUPUESTOS_DEL_MODELO) == ("S1", "S2", "S3", "S4")
    assert m.SUPUESTOS_DEL_MODELO["S1"]["estado"] == "supuesto_no_verificado"
    assert m.SUPUESTOS_DEL_MODELO["S4"]["estado"] == "requisito_pendiente"
    assert m.TOPOLOGIA_ELEGIDA is None and m.REPRESENTACION_ELEGIDA is None
    ids = {a.id for a in m.CLASIFICACION_DE_AFIRMACIONES}
    for t in TOPOLOGIAS:
        assert tuple(m.MATRIZ_DE_VINCULO[t]) == CRITERIOS, t
        for k in CRITERIOS:
            c = m.celda(t, k)
            assert c.estado in m.ESTADOS_DE_CELDA, (t, k)
            assert set(c.supuestos) <= set(m.SUPUESTOS_DEL_MODELO), (t, k)
            if c.estado in ("cumple_en_modelo_bajo_supuestos", "depende_de_requisito_pendiente"):
                assert c.supuestos, (t, k)
            assert c.afirmaciones and set(c.afirmaciones) <= ids, (t, k)
            assert c.alcance.strip(), (t, k)
    with pytest.raises(KeyError):
        m.celda("topologia_inventada", "K1")


def test_g1_celdas_esperadas_de_k1_k2_k3_k4():
    m = _modulo()
    e = {(t, k): m.celda(t, k).estado for t in TOPOLOGIAS for k in CRITERIOS}
    for t in ("directo_en_nuevo_esquema", "directo_en_campo_existente_no_previsto"):
        assert e[(t, "K1")] == e[(t, "K2")] == "cumple_en_modelo_bajo_supuestos", t
        assert set(m.celda(t, "K1").supuestos) == {"S1", "S2", "S3"}, t
        assert set(m.celda(t, "K2").supuestos) == {"S2", "S3"}, t
        assert "S1" in m.celda(t, "K2").alcance, t
    assert e[("inverso_desde_la_declaracion", "K1")] == e[("inverso_desde_la_declaracion", "K2")] == \
        "no_cumple_contraejemplo"
    for k in ("K1", "K2"):
        c = m.celda("manifiesto_externo", k)
        assert c.estado == "depende_de_requisito_pendiente" and "S4" in c.supuestos, k
    assert e[("directo_en_nuevo_esquema", "K3")] == "no_cumple_por_definicion"
    assert e[("directo_en_campo_existente_no_previsto", "K4")] == "no_cumple_por_definicion"
    for t in ("directo_en_campo_existente_no_previsto", "inverso_desde_la_declaracion", "manifiesto_externo"):
        assert e[(t, "K3")] == "cumple_por_definicion", t
    for t in TOPOLOGIAS:
        assert e[(t, "K5")] == "independiente_de_la_topologia", t
        assert e[(t, "K6")] == e[(t, "K7")] == "cumple_por_definicion", t


def test_g1_k1_exige_bytes_canonicos_y_regla_no_basta_el_digest():
    m = _modulo()
    publicas = {n: f for n, f in vars(m).items() if inspect.isfunction(f) and not n.startswith("_")
                and f.__module__ == m.__name__}
    for nombre, f in publicas.items():
        assert set(inspect.signature(f).parameters) != {"protocolo_hash"}, nombre
    parametros = inspect.signature(m.hash_designado).parameters
    assert list(parametros) == ["topologia", "bytes_protocolo", "protocolo_hash", "regla"]
    assert all(p.default is inspect.Parameter.empty for p in parametros.values())
    h_decl = iv.hash_de_declaracion_sintetica(_declaracion())
    bytes_p = rp.serializar_entrada(_protocolo(h_decl))
    digest = rp.hash_entrada(bytes_p)
    regla = m.ReglaDeVinculo("directo_en_campo_existente_no_previsto", CAMPO)
    assert m.hash_designado("directo_en_campo_existente_no_previsto", bytes_p, digest, regla) == h_decl
    otros_bytes = rp.serializar_entrada(_protocolo("9" * 64))
    assert m.hash_designado("directo_en_campo_existente_no_previsto", otros_bytes, digest, regla) is None
    assert m.hash_designado("directo_en_campo_existente_no_previsto", b"no es json\n", digest, regla) is None
    regla_mala = m.ReglaDeVinculo("directo_en_campo_existente_no_previsto", ("estrategia", "parametros", "no_existe"))
    assert m.hash_designado("directo_en_campo_existente_no_previsto", bytes_p, digest, regla_mala) is None
    for t in ("inverso_desde_la_declaracion", "manifiesto_externo"):
        assert m.hash_designado(t, bytes_p, digest, m.ReglaDeVinculo(t, ())) is None, t
    modelo = rp.serializar_entrada({"campo_nuevo_de_prueba": h_decl, "tipo": "protocolo_modelo"})
    regla_nueva = m.ReglaDeVinculo("directo_en_nuevo_esquema", ("campo_nuevo_de_prueba",))
    assert m.hash_designado("directo_en_nuevo_esquema", modelo, rp.hash_entrada(modelo), regla_nueva) == h_decl
    with pytest.raises(ValueError):
        m.hash_designado("inverso_desde_la_declaracion", bytes_p, digest, regla)
    with pytest.raises(ValueError):
        m.hash_designado("directo_en_campo_existente_no_previsto", bytes_p, digest,
                         m.ReglaDeVinculo("directo_en_campo_existente_no_previsto", ("juegos",)))


def test_g1_k1_con_ae52_real_en_ejemplos_bajo_s1_s2_s3():
    m = _modulo()
    regla = m.ReglaDeVinculo("directo_en_campo_existente_no_previsto", CAMPO)
    resultados = []
    for valor in ("a", "b"):
        h_decl = iv.hash_de_declaracion_sintetica(_declaracion(valor))
        bytes_p, estado, prediccion = _registro_con_prediccion(_protocolo(h_decl))
        assert prediccion["protocolo_hash"] == estado.hash_protocolo == rp.hash_entrada(bytes_p)
        designado = m.hash_designado("directo_en_campo_existente_no_previsto", bytes_p,
                                     prediccion["protocolo_hash"], regla)
        assert designado == h_decl
        resultados.append((h_decl, prediccion["protocolo_hash"]))
    (d1, p1), (d2, p2) = resultados
    assert d1 != d2 and p1 != p2


def test_g1_k2_designacion_unica_y_contraejemplos():
    m = _modulo()
    d1, d2 = _declaracion("uno"), _declaracion("dos")
    h1, h2 = iv.hash_de_declaracion_sintetica(d1), iv.hash_de_declaracion_sintetica(d2)
    bytes_p = rp.serializar_entrada(_protocolo(h1))
    digest = rp.hash_entrada(bytes_p)
    regla = m.ReglaDeVinculo("directo_en_campo_existente_no_previsto", CAMPO)
    directas = m.declaraciones_que_verifican(
        "directo_en_campo_existente_no_previsto", digest,
        (m.CandidataDeVinculo(d1), m.CandidataDeVinculo(d2)), bytes_protocolo=bytes_p, regla=regla)
    assert directas == (h1,)
    inversas = m.declaraciones_que_verifican(
        "inverso_desde_la_declaracion", digest,
        (m.CandidataDeVinculo(d1, protocolo_hash_referenciado=digest),
         m.CandidataDeVinculo(d2, protocolo_hash_referenciado=digest)))
    assert inversas == (h1, h2)
    manifiestos = (m.ManifiestoSintetico(digest, h1), m.ManifiestoSintetico(digest, h2))
    por_manifiesto = m.declaraciones_que_verifican(
        "manifiesto_externo", digest, (m.CandidataDeVinculo(d1), m.CandidataDeVinculo(d2)), manifiestos=manifiestos)
    assert por_manifiesto == (h1, h2)
    un_manifiesto = m.declaraciones_que_verifican(
        "manifiesto_externo", digest, (m.CandidataDeVinculo(d1), m.CandidataDeVinculo(d2)),
        manifiestos=manifiestos[:1])
    assert un_manifiesto == (h1,)
    assert "no afirma unicidad" in m.CRITERIOS_DE_VINCULO["K2"]["texto"]
    assert "S1" in m.CRITERIOS_DE_VINCULO["K2"]["texto"]
    for t in ("directo_en_nuevo_esquema", "directo_en_campo_existente_no_previsto"):
        assert "no afirma unicidad" in m.celda(t, "K2").alcance, t
    assert "El protocolo_hash aislado no basta" in m.CRITERIOS_DE_VINCULO["K1"]["texto"]


def test_g1_k6_k7_ningun_vinculo_autentica_fecha_ni_valida_suficiencia():
    m = _modulo()
    h = iv.hash_de_declaracion_sintetica(_declaracion())
    bytes_p = rp.serializar_entrada(_protocolo(h))
    m.hash_designado("directo_en_campo_existente_no_previsto", bytes_p, rp.hash_entrada(bytes_p),
                     m.ReglaDeVinculo("directo_en_campo_existente_no_previsto", CAMPO))
    assert {v["estado"] for v in ec.AUTENTICACION_DE_R0.values()} == {"pendiente"}
    assert ec.REQUISITOS_PREVIOS["declaracion_previa_del_protocolo"].estado == "sin_fijar"
    for estado in m.ESTADOS_DE_CELDA:
        assert not re.search(r"autenticad|acreditad|fijad|suficien", estado), estado
    for t in TOPOLOGIAS:
        for k in CRITERIOS:
            assert not re.search(r"autenticad|acreditad|fijad", m.celda(t, k).estado)
    for frase in ("no significa", "autenticacion", "anterioridad", "suficiencia",
                  "completa_sintetica_sin_autenticar"):
        assert frase in m.ALCANCE_DEL_ANALISIS, frase


def test_g1_completar_despues_da_otro_protocolo_que_no_cabe_en_el_registro():
    m = _modulo()
    elemento = next(iter(iv.ELEMENTOS_DE_R0))
    antes = _declaracion(pendiente=elemento)
    despues = _declaracion()
    assert iv.comprobar_declaracion_sintetica(antes) == "parcial"
    assert iv.comprobar_declaracion_sintetica(despues) == "completa_sintetica_sin_autenticar"
    p1 = _protocolo(iv.hash_de_declaracion_sintetica(antes))
    p2 = _protocolo(iv.hash_de_declaracion_sintetica(despues))
    b1, b2 = rp.serializar_entrada(p1), rp.serializar_entrada(p2)
    assert rp.hash_entrada(b1) != rp.hash_entrada(b2)
    with pytest.raises(rp.EntradaRegistroInvalidaError):
        rp.validar_registro([b1, _segundo_protocolo(b1, p2)])
    assert "otro protocolo" in m.CONSECUENCIA_DE_COMPLETAR_DESPUES


def test_g1_representaciones_de_pendientes_sin_elegir():
    m = _modulo()
    assert tuple(m.REPRESENTACIONES_DE_PENDIENTES) == ("estado_pendiente_por_elemento", "ampliar_pendientes_de_ae52",
                                                      "ausencia_implicita")
    assert m.REPRESENTACION_ELEGIDA is None
    r = m.REPRESENTACIONES_DE_PENDIENTES
    assert r["estado_pendiente_por_elemento"]["K3"] == "cumple_por_definicion"
    assert r["estado_pendiente_por_elemento"]["K5"] == "cumple_en_modelo_bajo_supuestos"
    assert r["ampliar_pendientes_de_ae52"]["K3"] == "no_cumple_por_definicion"
    assert r["ausencia_implicita"]["K5"] == "no_cumple_contraejemplo"
    omision = _declaracion()
    del omision[next(iter(iv.ELEMENTOS_DE_R0))]
    assert iv.comprobar_declaracion_sintetica(omision) == "incompleta"
    with pytest.raises(rp.EntradaRegistroInvalidaError):
        rp.construir_protocolo(protocolo_id="s", estrategia=_estrategia(), cortes={"BALOTO": 2713},
                               pendientes=[next(iter(iv.ELEMENTOS_DE_R0))], sintetico=True)
    todos = {e: {"estado": "pendiente"} for e in iv.ELEMENTOS_DE_R0}
    assert re.fullmatch(r"[0-9a-f]{64}", iv.hash_de_declaracion_sintetica(todos))


def test_g1_preguntas_de_ae69_siguen_sin_respuesta():
    _modulo()
    assert set(iv.PREGUNTAS_ABIERTAS_AE69) == {"ubicacion_de_la_declaracion", "definicion_del_plazo_frente_al_corte",
                                               "expresion_de_pendientes_de_r0_en_ae52"}
    assert {p["estado"] for p in iv.PREGUNTAS_ABIERTAS_AE69.values()} == {"sin_respuesta"}
    assert set(iv.ESTADO_ACTUAL_DE_R0.values()) == {"pendiente"}


def test_g1_b14_hecho_citado_separado_de_la_derivacion():
    m = _modulo()
    a = {x.id: x for x in m.CLASIFICACION_DE_AFIRMACIONES}
    assert a["B14"].clase == "hecho_citado_de_fuente"
    assert set(a["B14"].procedencia) == {f"AE-67:C{i}" for i in range(1, 8)}
    assert "certificados y precertificados" in a["B14"].texto
    assert "manifiesto" not in a["B14"].texto
    assert a["B15"].clase == "derivacion_propia"
    assert "premisa:B14" in a["B15"].procedencia
    assert "no aporta una garantia" in a["B15"].texto
    assert "no se afirma que ese uso sea imposible" in a["B15"].texto


def test_g1_clasificacion_de_afirmaciones_con_procedencia_exacta():
    m = _modulo()
    assert m.CLASES_DE_AFIRMACION == iv.CLASES_DE_AFIRMACION
    ids = tuple(a.id for a in m.CLASIFICACION_DE_AFIRMACIONES)
    assert ids == tuple(f"B{i}" for i in range(1, 16))
    clases = {a.id: a.clase for a in m.CLASIFICACION_DE_AFIRMACIONES}
    for i in range(1, 7):
        assert clases[f"B{i}"] == "hecho_observado_en_codigo"
    for i in (7, 8, 9, 10, 11, 12, 15):
        assert clases[f"B{i}"] == "derivacion_propia"
    assert clases["B13"] == "hipotesis_de_aplicacion" and clases["B14"] == "hecho_citado_de_fuente"
    afirmaciones_67 = {a.id for a in (*vr.AFIRMACIONES_RFC_3161, *vr.AFIRMACIONES_RFC_9162)}
    pruebas = {n for n in globals() if n.startswith("test_")}
    for a in m.CLASIFICACION_DE_AFIRMACIONES:
        assert a.texto.strip() and a.evidencia.strip() and a.procedencia, a.id
        if a.clase == "hecho_observado_en_codigo":
            assert any(p.endswith(BASE) and p.startswith("backend/app/") for p in a.procedencia), a.id
            citadas = [p.removeprefix("prueba:") for p in a.procedencia if p.startswith("prueba:")]
            assert citadas and set(citadas) <= pruebas, a.id
            assert a.estado == "observado_en_pruebas", a.id
        elif a.clase == "hecho_citado_de_fuente":
            for p in a.procedencia:
                coincide = re.fullmatch(r"AE-67:(C\d|T\d)", p)
                assert coincide and coincide.group(1) in afirmaciones_67, (a.id, p)
            assert a.estado == "citado_de_ae67", a.id
        elif a.clase == "derivacion_propia":
            for p in a.procedencia:
                assert p.startswith("premisa:"), (a.id, p)
                premisa = p.removeprefix("premisa:")
                if re.fullmatch(r"B\d+", premisa):
                    assert premisa in ids and premisa != a.id
                elif premisa.startswith("supuesto:"):
                    assert premisa.removeprefix("supuesto:") in m.SUPUESTOS_DEL_MODELO
                elif premisa.startswith("AE-67:"):
                    assert premisa.removeprefix("AE-67:") in afirmaciones_67
                else:
                    modulo, simbolo = premisa.rsplit(".", 1)
                    assert hasattr(importlib.import_module(f"app.application.ml.{modulo}"), simbolo), p
            assert a.estado == "derivado", a.id
        else:
            assert a.estado == "pendiente", a.id


def test_g1_modulo_puro_sin_red_reloj_ni_archivos():
    m = _modulo()
    arbol = ast.parse(Path(m.__file__).read_text(encoding="utf-8"))
    prohibidos = {"socket", "urllib", "requests", "http", "time", "subprocess", "random", "os", "pathlib",
                  "sqlalchemy", "datetime"}
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            assert not {a.name.split(".")[0] for a in nodo.names} & prohibidos
        if isinstance(nodo, ast.ImportFrom):
            assert (nodo.module or "").split(".")[0] not in prohibidos
            assert not (nodo.module or "").startswith("app.infrastructure")
        if isinstance(nodo, ast.Attribute):
            assert nodo.attr not in {"now", "utcnow", "today"}, nodo.attr
        if isinstance(nodo, ast.Name):
            assert nodo.id not in {"open", "eval", "exec"}, nodo.id


_PROHIBIDAS = {"aprobado", "aprobada", "aprobados", "aprobadas", "go", "cumplido", "cumplida", "desbloqueado",
               "desbloqueada", "autorizado", "autorizada", "recomendado", "recomendada", "elegido", "elegida",
               "autenticado", "autenticada", "acreditado", "acreditada", "fijado", "fijada", "valido", "valida"}


def test_g1_textos_sin_aprobacion_autorizacion_ni_acreditacion():
    m = _modulo()
    textos = [m.ALCANCE_DEL_ANALISIS, m.CONSECUENCIA_DE_COMPLETAR_DESPUES, *m.ESTADOS_DE_CELDA]
    textos += [v["texto"] for v in m.TOPOLOGIAS_DE_VINCULO.values()]
    textos += [v["texto"] for v in m.CRITERIOS_DE_VINCULO.values()]
    textos += [v["texto"] for v in m.SUPUESTOS_DEL_MODELO.values()]
    textos += [v["texto"] for v in m.REPRESENTACIONES_DE_PENDIENTES.values()]
    textos += [m.celda(t, k).alcance for t in TOPOLOGIAS for k in CRITERIOS]
    for a in m.CLASIFICACION_DE_AFIRMACIONES:
        textos += [a.texto, a.evidencia]
    palabras = {p.lower() for t in textos for p in re.split(r"[^A-Za-z]+", t) if p}
    assert not palabras & _PROHIBIDAS, palabras & _PROHIBIDAS


# ===========================================================================
# G2: invariantes sobre codigo existente (pasan sobre la base)
# ===========================================================================

def test_g2_huellas_de_ae52_y_ae63_a_ae69():
    assert _huella((rp.ESQUEMA_ENTRADA, rp.TIPOS_ENTRADA, rp.REGLAS_EVALUACION_AE52, rp.PENDIENTES_BORRADOR_AE52,
                    rp.NOTA_PROTOCOLO, rp.ALCANCE_REGISTRO)) == (
        "4f31cdeb3c4d29b1740592d4d81de2f8f51305abf4a82743c49f12985621c50b")
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
    assert _huella((ec.ALCANCE_RFC_9162, ec.MODELO_DE_FIRMA, ec.AUTENTICACION_DE_R0, ec.REQUISITOS_PREVIOS,
                    ec.CONDICIONES_DEL_PROTOCOLO, ec.CORRESPONDENCIA_CON_AE66, ec.DEPENDENCIAS_NORMATIVAS,
                    ec.DEPENDENCIAS_DE_VERIFICACION, ec.INSTANTES, ec.HIPOTESIS_TEMPORALES,
                    ec.LIMITE_DE_COMPLETITUD, tuple(ec.REGLAS_DE_DUPLICADOS_CANDIDATAS),
                    ec.REGLA_DE_DUPLICADOS_ELEGIDA, ec.RESULTADOS_RELOJ, ec.REQUISITOS_DE_VIA,
                    ec.RESULTADOS_DE_VIA)) == (
        "03c83bb1719e68bc14744bde36971f92a7a0f45784512424566305c2f504b00d")
    assert _huella((iv.SITUACIONES_EN_AE52, iv.RELACION_CON_AE52, iv.ELEMENTOS_DE_R0, iv.ESTADO_ACTUAL_DE_R0,
                    iv.CORRESPONDENCIA_CON_PENDIENTES_AE52, iv.PREGUNTAS_ABIERTAS_AE69, iv.ESTADOS_DE_ELEMENTO,
                    iv.RESULTADOS_DECLARACION, iv.ALCANCE_DE_LA_COMPLETITUD, iv.TRATAMIENTO_DE_VALORES_VACIOS,
                    iv.CLASES_DE_AFIRMACION, iv.CLASIFICACION_DE_AFIRMACIONES)) == (
        "b5637fe7ee274d0a9b63d6a87837dd9d0e0a6a108772e10c26dde23c55d83a24")
    assert dr.huella_diseno() == "6743293d4e247c17ed5f9c098824caf4f740873f00a04d4e223f334874f8de3c"


def test_g2_estados_decisiones_y_bloqueos_sin_cambios():
    assert {r.estado for r in {**ec.REQUISITOS_PREVIOS, **ec.CONDICIONES_DEL_PROTOCOLO}.values()} == {"sin_fijar"}
    assert {v["estado"] for v in ec.AUTENTICACION_DE_R0.values()} == {"pendiente"}
    assert ec.REGLA_DE_DUPLICADOS_ELEGIDA is None
    assert set(vr.CONDICIONES_DEL_REPOSITORIO.values()) == {"sin_fijar"}
    assert {e.estado for e in iv.ELEMENTOS_DE_R0.values()} == {"pendiente"}
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
    assert pi.ESTADO_EXPEDIENTE == "expediente_sin_eleccion"
    assert pi.AUTORIZA_EVALUACION is False
    for decision in (*pi.DECISIONES_INFERENCIALES_ABIERTAS.values(), *pi.DECISIONES_REQUERIDAS):
        assert decision.valor is None and decision.estado == "sin_decidir"
    pi.verificar_expediente()
    assert len(rp.PENDIENTES_BORRADOR_AE52) == 7
    assert ESPECIFICACION_CANDIDATA_AE53["estado"] == "candidata_no_aprobada"


# ===========================================================================
# G3: integraciones contra la API publica real de AE-52 y AE-69 (pasan sobre la base)
# ===========================================================================

def test_g3_b1_parametros_admite_una_clave_con_un_hash():
    protocolo = _protocolo("1" * 64)
    estado = rp.validar_registro([rp.serializar_entrada(protocolo)])
    assert estado.total == 1
    assert estado.protocolo["estrategia"]["parametros"]["clave_de_prueba"] == "1" * 64


def test_g3_b2_protocolo_hash_distinto_se_rechaza_con_la_cadena_correcta():
    bytes_p, estado, prediccion = _registro_con_prediccion(_protocolo())
    assert rp.validar_registro([bytes_p, rp.serializar_entrada(prediccion)]).total == 2
    alterada = {**prediccion, "protocolo_hash": "f" * 64}
    assert alterada["hash_anterior"] == estado.cabeza and alterada["secuencia"] == 2
    with pytest.raises(rp.EntradaRegistroInvalidaError, match="protocolo distinto"):
        rp.validar_registro([bytes_p, rp.serializar_entrada(alterada)])


def test_g3_b3_cambio_en_parametros_llega_a_bytes_hash_y_prediccion():
    vistos = []
    for valor in ("1" * 64, "2" * 64):
        protocolo = _protocolo(valor)
        bytes_p, estado, prediccion = _registro_con_prediccion(protocolo)
        assert rp.leer_entrada(bytes_p)["estrategia"]["parametros"]["clave_de_prueba"] == valor
        assert estado.hash_protocolo == rp.hash_entrada(bytes_p)
        assert prediccion["protocolo_hash"] == estado.hash_protocolo
        assert rp.validar_registro([bytes_p, rp.serializar_entrada(prediccion)]).total == 2
        vistos.append((bytes_p, estado.hash_protocolo, prediccion["protocolo_hash"]))
    (b1, h1, q1), (b2, h2, q2) = vistos
    assert b1 != b2 and h1 != h2 and q1 != q2


def test_g3_b4_segundo_protocolo_en_el_registro_se_rechaza():
    b1 = rp.serializar_entrada(_protocolo("1" * 64))
    with pytest.raises(rp.EntradaRegistroInvalidaError, match="segundo protocolo"):
        rp.validar_registro([b1, _segundo_protocolo(b1, _protocolo("2" * 64))])


def test_g3_b5_protocolo_real_en_borrador_no_admite_predicciones():
    borrador = rp.construir_protocolo_borrador(_estrategia())
    assert borrador["pendientes"] == list(rp.PENDIENTES_BORRADOR_AE52) and borrador["sintetico"] is False
    estado = rp.validar_registro([rp.serializar_entrada(borrador)])
    assert estado.admite_salidas is False
    with pytest.raises(rp.EntradaRegistroInvalidaError):
        rp.nueva_prediccion(estado, "BALOTO", 2714, sinteticos.historico(2081, 2713), PROBABILIDADES)


def test_g3_b6_declaracion_con_pendientes_se_hashea_y_la_omision_es_incompleta():
    elemento = next(iter(iv.ELEMENTOS_DE_R0))
    d = _declaracion(pendiente=elemento)
    assert iv.comprobar_declaracion_sintetica(d) == "parcial"
    assert iv.hash_de_declaracion_sintetica(d) == rp.hash_entrada(rp.serializar_entrada(d))
    del d[elemento]
    assert iv.comprobar_declaracion_sintetica(d) == "incompleta"
    with pytest.raises(iv.DeclaracionSinteticaInvalidaError):
        iv.hash_de_declaracion_sintetica(d)
